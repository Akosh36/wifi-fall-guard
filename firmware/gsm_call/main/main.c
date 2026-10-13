/*
 * WiFi Fall Guard - GSM caller (ESP32-S3 + SIM800L / A7670 / SIM7600)
 *
 * The server decides when help must be called (docs/escalation.md) and POSTs
 * its emergency_call event to escalation.call_webhook. Point that at this board:
 *
 *     call_webhook: http://192.168.4.30/call?key=<CONFIG_WFG_KEY>
 *
 * The board then
 *   1. sends an SMS with the reason and the home address to every number in
 *      CONFIG_WFG_SMS_NUMBERS (relatives), and
 *   2. dials the number (CONFIG_WFG_CALL_NUMBER, else the one in the request)
 *      and keeps the line open, so with a speaker and microphone on the modem
 *      the person on the floor can talk to the dispatcher.
 *
 * It works without the phone app and without internet: only the local WiFi
 * between server and board, and the GSM network.
 *
 * Emergency numbers are blocked unless CONFIG_WFG_ALLOW_EMERGENCY is on, so a
 * test can never reach a real dispatcher.
 *
 * Endpoints:  POST /call?key=..   GET /status   POST /test?key=..&to=+998...
 */
#include <ctype.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/queue.h"
#include "esp_wifi.h"
#include "esp_event.h"
#include "esp_log.h"
#include "esp_netif.h"
#include "esp_http_server.h"
#include "esp_timer.h"
#include "nvs_flash.h"
#include "driver/uart.h"
#include "lwip/inet.h"
#include "cJSON.h"
#include "sdkconfig.h"

#define MODEM_UART UART_NUM_1
#define SMS_MAX    160

#ifdef CONFIG_WFG_ALLOW_EMERGENCY
static const bool ALLOW_EMERGENCY = true;
#else
static const bool ALLOW_EMERGENCY = false;
#endif

static const char *TAG = "gsm_call";

typedef struct {
    bool sms_only;          /* /test: SMS to one number, no call */
    char number[24];        /* number to dial (or the test SMS recipient) */
    char text[SMS_MAX + 1];
} job_t;

static QueueHandle_t s_jobs;
static volatile int s_csq = -1;          /* signal quality 0..31, 99 = unknown */
static volatile bool s_registered;
static char s_last[96] = "none";
static int64_t s_last_job_us = -1000000000LL;

/* ---------- modem (AT commands) ---------- */

static void modem_flush(void)
{
    uart_flush_input(MODEM_UART);
}

/* Send cmd (may be NULL) and collect the answer until `expect` or ERROR appears.
 * Returns true when `expect` was seen. */
static bool at(const char *cmd, const char *expect, int timeout_ms, char *out, size_t out_len)
{
    static char buf[512];
    size_t n = 0;
    buf[0] = 0;
    if (cmd) {
        modem_flush();
        uart_write_bytes(MODEM_UART, cmd, strlen(cmd));
        uart_write_bytes(MODEM_UART, "\r", 1);
    }
    int64_t end = esp_timer_get_time() + (int64_t)timeout_ms * 1000;
    bool ok = false;
    while (esp_timer_get_time() < end) {
        int r = uart_read_bytes(MODEM_UART, (uint8_t *)buf + n, sizeof(buf) - 1 - n, pdMS_TO_TICKS(50));
        if (r > 0) {
            n += r;
            buf[n] = 0;
            if (strstr(buf, expect)) {
                ok = true;
                break;
            }
            if (strstr(buf, "ERROR")) {
                break;
            }
            if (n >= sizeof(buf) - 1) {
                n = 0; /* keep reading, drop old text */
            }
        }
    }
    if (out) {
        strlcpy(out, buf, out_len);
    }
    ESP_LOGD(TAG, "%s -> %s", cmd ? cmd : "(wait)", buf);
    return ok;
}

static bool modem_init(void)
{
    for (int i = 0; i < 20; i++) { /* SIM800L autobauds on the first "AT"s */
        if (at("AT", "OK", 500, NULL, 0)) {
            at("ATE0", "OK", 1000, NULL, 0);          /* no echo */
            at("AT+CMEE=2", "OK", 1000, NULL, 0);     /* readable errors */
            at("AT+CMGF=1", "OK", 2000, NULL, 0);     /* SMS text mode */
            at("AT+CSCS=\"GSM\"", "OK", 2000, NULL, 0);
            at("AT+CLIP=1", "OK", 1000, NULL, 0);
            return true;
        }
        vTaskDelay(pdMS_TO_TICKS(500));
    }
    return false;
}

static void modem_poll(void)
{
    char resp[128];
    if (at("AT+CSQ", "OK", 2000, resp, sizeof(resp))) {
        char *p = strstr(resp, "+CSQ:");
        if (p) {
            s_csq = atoi(p + 5);
        }
    }
    /* 2G (CREG) or LTE (CEREG): ",1" = home, ",5" = roaming */
    bool reg = false;
    if (at("AT+CREG?", "OK", 2000, resp, sizeof(resp))) {
        reg = strstr(resp, ",1") || strstr(resp, ",5");
    }
    if (!reg && at("AT+CEREG?", "OK", 2000, resp, sizeof(resp))) {
        reg = strstr(resp, ",1") || strstr(resp, ",5");
    }
    s_registered = reg;
}

static bool send_sms(const char *to, const char *text)
{
    char cmd[48];
    snprintf(cmd, sizeof(cmd), "AT+CMGS=\"%s\"", to);
    if (!at(cmd, ">", 5000, NULL, 0)) {
        ESP_LOGE(TAG, "SMS to %s: no prompt", to);
        uart_write_bytes(MODEM_UART, "\x1b", 1); /* cancel */
        return false;
    }
    uart_write_bytes(MODEM_UART, text, strlen(text));
    uart_write_bytes(MODEM_UART, "\x1a", 1); /* Ctrl+Z sends */
    bool ok = at(NULL, "+CMGS", 60000, NULL, 0);
    ESP_LOGI(TAG, "SMS to %s: %s", to, ok ? "sent" : "FAILED");
    return ok;
}

static bool is_emergency(const char *num)
{
    static const char *list[] = {"101", "102", "103", "104", "112", "911"};
    for (size_t i = 0; i < sizeof(list) / sizeof(list[0]); i++) {
        if (strcmp(num, list[i]) == 0) {
            return true;
        }
    }
    return false;
}

static void call(const char *num)
{
    if (is_emergency(num) && !ALLOW_EMERGENCY) {
        ESP_LOGW(TAG, "not calling %s: emergency numbers are disabled (CONFIG_WFG_ALLOW_EMERGENCY)", num);
        snprintf(s_last, sizeof(s_last), "call %s blocked (emergency numbers off)", num);
        return;
    }
    char cmd[40], resp[128];
    at("AT+CHFA=0", "OK", 1000, NULL, 0); /* SIM800: main audio channel (ignored by others) */
    at("AT+CLVL=90", "OK", 1000, NULL, 0);
    snprintf(cmd, sizeof(cmd), "ATD%s;", num);
    if (!at(cmd, "OK", 10000, resp, sizeof(resp))) {
        ESP_LOGE(TAG, "dial %s failed: %s", num, resp);
        snprintf(s_last, sizeof(s_last), "call %s failed", num);
        return;
    }
    ESP_LOGI(TAG, "calling %s, line open for %d s", num, CONFIG_WFG_CALL_SECONDS);
    snprintf(s_last, sizeof(s_last), "called %s", num);
    /* keep the line open; stop early if the other side hangs up */
    if (at(NULL, "NO CARRIER", CONFIG_WFG_CALL_SECONDS * 1000, resp, sizeof(resp)) ||
        strstr(resp, "BUSY") || strstr(resp, "NO ANSWER")) {
        ESP_LOGI(TAG, "call ended by the network: %s", resp);
    }
    at("ATH", "OK", 5000, NULL, 0);
}

static void modem_task(void *arg)
{
    uart_config_t cfg = {
        .baud_rate = CONFIG_WFG_MODEM_BAUD,
        .data_bits = UART_DATA_8_BITS,
        .parity = UART_PARITY_DISABLE,
        .stop_bits = UART_STOP_BITS_1,
        .flow_ctrl = UART_HW_FLOWCTRL_DISABLE,
        .source_clk = UART_SCLK_DEFAULT,
    };
    ESP_ERROR_CHECK(uart_driver_install(MODEM_UART, 2048, 0, 0, NULL, 0));
    ESP_ERROR_CHECK(uart_param_config(MODEM_UART, &cfg));
    ESP_ERROR_CHECK(uart_set_pin(MODEM_UART, CONFIG_WFG_MODEM_TX_GPIO, CONFIG_WFG_MODEM_RX_GPIO,
                                 UART_PIN_NO_CHANGE, UART_PIN_NO_CHANGE));
    while (!modem_init()) {
        ESP_LOGE(TAG, "modem does not answer AT: check power (3.7-4.2 V, 2 A), wiring TX<->RX, GND");
        snprintf(s_last, sizeof(s_last), "modem not answering");
        vTaskDelay(pdMS_TO_TICKS(5000));
    }
    ESP_LOGI(TAG, "modem ready");
    job_t job;
    for (;;) {
        if (xQueueReceive(s_jobs, &job, pdMS_TO_TICKS(15000)) != pdTRUE) {
            modem_poll();
            ESP_LOGI(TAG, "network %s, signal %d/31", s_registered ? "OK" : "NOT REGISTERED", s_csq);
            continue;
        }
        if (job.sms_only) {
            bool ok = send_sms(job.number, job.text);
            snprintf(s_last, sizeof(s_last), "test SMS to %s %s", job.number, ok ? "sent" : "failed");
            continue;
        }
        /* SMS first: it reaches relatives even if the call cannot be made */
        char list[sizeof(CONFIG_WFG_SMS_NUMBERS)];
        strlcpy(list, CONFIG_WFG_SMS_NUMBERS, sizeof(list));
        for (char *save, *num = strtok_r(list, ", ", &save); num; num = strtok_r(NULL, ", ", &save)) {
            send_sms(num, job.text);
        }
        if (job.number[0]) {
            call(job.number);
        }
    }
}

/* ---------- HTTP ---------- */

/* SMS in GSM text mode: keep printable ASCII, map Uzbek apostrophes, cut to 160. */
static void sms_append(char *dst, const char *src)
{
    size_t n = strlen(dst);
    for (const unsigned char *p = (const unsigned char *)src; p && *p && n < SMS_MAX; p++) {
        if (*p >= 0x20 && *p < 0x7f) {
            dst[n++] = (char)*p;
        } else if (*p == 0xCA || *p == 0xE2) { /* start of ʻ ʼ ‘ ’ */
            dst[n++] = '\'';
            p += (*p == 0xCA) ? 1 : 2;
        }
    }
    dst[n] = 0;
}

static bool key_ok(httpd_req_t *req)
{
    char q[128], key[64];
    return httpd_req_get_url_query_str(req, q, sizeof(q)) == ESP_OK &&
           httpd_query_key_value(q, "key", key, sizeof(key)) == ESP_OK && strcmp(key, CONFIG_WFG_KEY) == 0;
}

static esp_err_t call_post(httpd_req_t *req)
{
    if (!key_ok(req)) {
        httpd_resp_send_err(req, HTTPD_403_FORBIDDEN, "bad key");
        return ESP_OK;
    }
    char body[1024];
    int len = req->content_len < sizeof(body) - 1 ? req->content_len : sizeof(body) - 1;
    int got = 0;
    while (got < len) {
        int r = httpd_req_recv(req, body + got, len - got);
        if (r <= 0) {
            return ESP_FAIL;
        }
        got += r;
    }
    body[got] = 0;

    /* the server re-sends on retries: one call per 2 minutes is enough */
    if (esp_timer_get_time() - s_last_job_us < 120LL * 1000000) {
        httpd_resp_sendstr(req, "{\"ok\":true,\"duplicate\":true}");
        return ESP_OK;
    }

    job_t job = {0};
    cJSON *j = cJSON_Parse(body);
    const char *num = cJSON_GetStringValue(cJSON_GetObjectItem(j, "number"));
    const char *reason = cJSON_GetStringValue(cJSON_GetObjectItem(j, "reason"));
    const char *address = cJSON_GetStringValue(cJSON_GetObjectItem(j, "address"));
    const char *vitals = cJSON_GetStringValue(cJSON_GetObjectItem(j, "vitals"));
    double down = cJSON_GetNumberValue(cJSON_GetObjectItem(j, "down_min"));

    strlcpy(job.number, CONFIG_WFG_CALL_NUMBER[0] ? CONFIG_WFG_CALL_NUMBER : (num ? num : ""), sizeof(job.number));
    sms_append(job.text, "WiFi Fall Guard: YIQILISH, yordam kerak! ");
    sms_append(job.text, reason);
    if (!isnan(down)) {
        char tmp[32];
        snprintf(tmp, sizeof(tmp), ". Yerda %.0f daq", down);
        sms_append(job.text, tmp);
    }
    if (vitals && vitals[0]) {
        sms_append(job.text, ". ");
        sms_append(job.text, vitals);
    }
    if (address && address[0]) {
        sms_append(job.text, ". Manzil: ");
        sms_append(job.text, address);
    }
    cJSON_Delete(j);

    if (xQueueSend(s_jobs, &job, 0) != pdTRUE) {
        httpd_resp_send_err(req, HTTPD_500_INTERNAL_SERVER_ERROR, "busy");
        return ESP_OK;
    }
    s_last_job_us = esp_timer_get_time();
    ESP_LOGW(TAG, "EMERGENCY request: call %s, SMS \"%s\"", job.number, job.text);
    httpd_resp_set_type(req, "application/json");
    httpd_resp_sendstr(req, "{\"ok\":true}");
    return ESP_OK;
}

static esp_err_t test_post(httpd_req_t *req)
{
    char q[128];
    job_t job = {.sms_only = true};
    if (!key_ok(req) || httpd_req_get_url_query_str(req, q, sizeof(q)) != ESP_OK ||
        httpd_query_key_value(q, "to", job.number, sizeof(job.number)) != ESP_OK) {
        httpd_resp_send_err(req, HTTPD_400_BAD_REQUEST, "need ?key=..&to=%2B998...");
        return ESP_OK;
    }
    /* '+' arrives URL-encoded as %2B */
    if (strncmp(job.number, "%2B", 3) == 0) {
        memmove(job.number + 1, job.number + 3, strlen(job.number + 3) + 1);
        job.number[0] = '+';
    }
    strlcpy(job.text, "WiFi Fall Guard: sinov SMS. GSM plata ishlayapti.", sizeof(job.text));
    xQueueSend(s_jobs, &job, 0);
    httpd_resp_sendstr(req, "{\"ok\":true}");
    return ESP_OK;
}

static esp_err_t status_get(httpd_req_t *req)
{
    char out[256];
    snprintf(out, sizeof(out),
             "{\"registered\":%s,\"signal\":%d,\"emergency_allowed\":%s,\"last\":\"%s\"}",
             s_registered ? "true" : "false", s_csq, ALLOW_EMERGENCY ? "true" : "false", s_last);
    httpd_resp_set_type(req, "application/json");
    httpd_resp_sendstr(req, out);
    return ESP_OK;
}

static void http_start(void)
{
    httpd_config_t cfg = HTTPD_DEFAULT_CONFIG();
    cfg.stack_size = 8192;
    httpd_handle_t h;
    ESP_ERROR_CHECK(httpd_start(&h, &cfg));
    httpd_uri_t uris[] = {
        {.uri = "/call", .method = HTTP_POST, .handler = call_post},
        {.uri = "/test", .method = HTTP_POST, .handler = test_post},
        {.uri = "/status", .method = HTTP_GET, .handler = status_get},
    };
    for (size_t i = 0; i < sizeof(uris) / sizeof(uris[0]); i++) {
        httpd_register_uri_handler(h, &uris[i]);
    }
}

/* ---------- WiFi ---------- */

static void wifi_event_handler(void *arg, esp_event_base_t base, int32_t id, void *data)
{
    if (base == WIFI_EVENT && (id == WIFI_EVENT_STA_START || id == WIFI_EVENT_STA_DISCONNECTED)) {
        esp_wifi_connect();
    } else if (base == IP_EVENT && id == IP_EVENT_STA_GOT_IP) {
        ip_event_got_ip_t *e = (ip_event_got_ip_t *)data;
        ESP_LOGI(TAG, "ready: http://" IPSTR "/status  (call_webhook: http://" IPSTR "/call?key=...)",
                 IP2STR(&e->ip_info.ip), IP2STR(&e->ip_info.ip));
    }
}

static void wifi_init(void)
{
    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());
    esp_netif_t *netif = esp_netif_create_default_wifi_sta();
    if (strlen(CONFIG_WFG_STATIC_IP) > 0) {
        esp_netif_ip_info_t ip = {0};
        ip.ip.addr = ipaddr_addr(CONFIG_WFG_STATIC_IP);
        ip.gw.addr = ipaddr_addr(CONFIG_WFG_GATEWAY);
        ip.netmask.addr = ipaddr_addr("255.255.255.0");
        ESP_ERROR_CHECK(esp_netif_dhcpc_stop(netif));
        ESP_ERROR_CHECK(esp_netif_set_ip_info(netif, &ip));
    }
    wifi_init_config_t init = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&init));
    ESP_ERROR_CHECK(esp_event_handler_register(WIFI_EVENT, ESP_EVENT_ANY_ID, wifi_event_handler, NULL));
    ESP_ERROR_CHECK(esp_event_handler_register(IP_EVENT, IP_EVENT_STA_GOT_IP, wifi_event_handler, NULL));
    wifi_config_t cfg = {0};
    strlcpy((char *)cfg.sta.ssid, CONFIG_WFG_WIFI_SSID, sizeof(cfg.sta.ssid));
    strlcpy((char *)cfg.sta.password, CONFIG_WFG_WIFI_PASSWORD, sizeof(cfg.sta.password));
    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));
    ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_STA, &cfg));
    ESP_ERROR_CHECK(esp_wifi_start());
}

void app_main(void)
{
    esp_err_t err = nvs_flash_init();
    if (err == ESP_ERR_NVS_NO_FREE_PAGES || err == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        err = nvs_flash_init();
    }
    ESP_ERROR_CHECK(err);
    if (strcmp(CONFIG_WFG_KEY, "change-me") == 0) {
        ESP_LOGW(TAG, "CONFIG_WFG_KEY is still \"change-me\": set your own key");
    }
    s_jobs = xQueueCreate(4, sizeof(job_t));
    xTaskCreate(modem_task, "modem", 6144, NULL, 5, NULL);
    wifi_init();
    http_start();
}
