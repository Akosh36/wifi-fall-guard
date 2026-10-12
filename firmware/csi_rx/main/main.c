/*
 * WiFi Fall Guard - CSI receiver node (ESP32-S3)
 *
 * 1. Joins the WiFi network of the transmitter (firmware/csi_tx softAP or a home router).
 * 2. Pings the gateway CONFIG_WFG_PING_HZ times per second; every ping reply
 *    is an OFDM frame from the gateway, and the WiFi driver hands us its
 *    Channel State Information (CSI).
 * 3. Sends each CSI measurement to the server as one UDP packet.
 *
 * The packet layout must match wfg/csi/packet.py (20-byte header + 64 int8 (imag, real) pairs).
 */
#include <string.h>
#include <inttypes.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/queue.h"
#include "freertos/event_groups.h"
#include "esp_wifi.h"
#include "esp_event.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "esp_netif.h"
#include "nvs_flash.h"
#include "lwip/sockets.h"
#include "lwip/inet.h"
#include "ping/ping_sock.h"
#include "sdkconfig.h"

#define WFG_MAGIC   0xC51A
#define WFG_VERSION 1
#define RAW_BINS    64              /* legacy LTF, 20 MHz: 64 FFT bins */
#define QUEUE_LEN   64
#define CONNECTED_BIT BIT0

static const char *TAG = "csi_rx";

typedef struct __attribute__((packed)) {
    uint16_t magic;
    uint8_t  version;
    uint8_t  node_id;
    uint32_t seq;
    uint64_t esp_time_us;
    int8_t   rssi;
    int8_t   noise_floor;
    uint8_t  channel;
    uint8_t  n_raw;
} csi_header_t;

_Static_assert(sizeof(csi_header_t) == 20, "header must be 20 bytes");

typedef struct {
    csi_header_t hdr;
    int8_t buf[RAW_BINS * 2];
} csi_msg_t;

static QueueHandle_t s_queue;
static EventGroupHandle_t s_wifi_events;
static esp_netif_t *s_netif;
static uint8_t s_gateway_mac[6];
static volatile uint32_t s_seq;
static volatile uint32_t s_dropped;
static volatile uint32_t s_sent;
static esp_ping_handle_t s_ping;

/* Called by the WiFi driver for every received frame with CSI. Keep it short. */
static void csi_rx_cb(void *ctx, wifi_csi_info_t *info)
{
    if (!info || !info->buf || info->len < RAW_BINS * 2) {
        return;
    }
    if (memcmp(info->mac, s_gateway_mac, 6) != 0) {
        return; /* only frames sent by the transmitter, not by other devices */
    }
    csi_msg_t msg;
    msg.hdr.magic = WFG_MAGIC;
    msg.hdr.version = WFG_VERSION;
    msg.hdr.node_id = CONFIG_WFG_NODE_ID;
    msg.hdr.seq = s_seq++;
    msg.hdr.esp_time_us = (uint64_t)esp_timer_get_time();
    msg.hdr.rssi = info->rx_ctrl.rssi;
    msg.hdr.noise_floor = info->rx_ctrl.noise_floor;
    msg.hdr.channel = info->rx_ctrl.channel;
    msg.hdr.n_raw = RAW_BINS;
    memcpy(msg.buf, info->buf, RAW_BINS * 2);
    if (info->first_word_invalid) {
        /* the first 4 bytes (bins 0 and 1) are garbage on some frames: copy bin 2 */
        msg.buf[0] = msg.buf[2] = msg.buf[4];
        msg.buf[1] = msg.buf[3] = msg.buf[5];
    }
    if (xQueueSend(s_queue, &msg, 0) != pdTRUE) {
        s_dropped++;
    }
}

static void start_ping(void)
{
    esp_netif_ip_info_t ip;
    ESP_ERROR_CHECK(esp_netif_get_ip_info(s_netif, &ip));
    esp_ping_config_t cfg = ESP_PING_DEFAULT_CONFIG();
    cfg.count = ESP_PING_COUNT_INFINITE;
    cfg.interval_ms = 1000 / CONFIG_WFG_PING_HZ;
    cfg.timeout_ms = 1000;
    cfg.data_size = 1;
    cfg.task_stack_size = 3072;
    cfg.target_addr.type = IPADDR_TYPE_V4;
    cfg.target_addr.u_addr.ip4.addr = ip.gw.addr;
    esp_ping_callbacks_t cbs = {0};
    if (s_ping) {
        esp_ping_stop(s_ping);
        esp_ping_delete_session(s_ping);
        s_ping = NULL;
    }
    ESP_ERROR_CHECK(esp_ping_new_session(&cfg, &cbs, &s_ping));
    ESP_ERROR_CHECK(esp_ping_start(s_ping));
    ESP_LOGI(TAG, "pinging gateway " IPSTR " at %d Hz", IP2STR(&ip.gw), CONFIG_WFG_PING_HZ);
}

static void wifi_event_handler(void *arg, esp_event_base_t base, int32_t id, void *data)
{
    if (base == WIFI_EVENT && id == WIFI_EVENT_STA_START) {
        esp_wifi_connect();
    } else if (base == WIFI_EVENT && id == WIFI_EVENT_STA_DISCONNECTED) {
        xEventGroupClearBits(s_wifi_events, CONNECTED_BIT);
        ESP_LOGW(TAG, "disconnected, reconnecting");
        esp_wifi_connect();
    } else if (base == IP_EVENT && id == IP_EVENT_STA_GOT_IP) {
        wifi_ap_record_t ap;
        if (esp_wifi_sta_get_ap_info(&ap) == ESP_OK) {
            memcpy(s_gateway_mac, ap.bssid, 6);
            ESP_LOGI(TAG, "connected to %s, BSSID " MACSTR ", channel %d", (char *)ap.ssid,
                     MAC2STR(ap.bssid), ap.primary);
        }
        start_ping();
        xEventGroupSetBits(s_wifi_events, CONNECTED_BIT);
    }
}

static void wifi_init(void)
{
    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());
    s_netif = esp_netif_create_default_wifi_sta();

    wifi_init_config_t init = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&init));
    ESP_ERROR_CHECK(esp_event_handler_register(WIFI_EVENT, ESP_EVENT_ANY_ID, wifi_event_handler, NULL));
    ESP_ERROR_CHECK(esp_event_handler_register(IP_EVENT, IP_EVENT_STA_GOT_IP, wifi_event_handler, NULL));
    ESP_ERROR_CHECK(esp_wifi_set_storage(WIFI_STORAGE_RAM));

    wifi_config_t cfg = {0};
    strlcpy((char *)cfg.sta.ssid, CONFIG_WFG_WIFI_SSID, sizeof(cfg.sta.ssid));
    strlcpy((char *)cfg.sta.password, CONFIG_WFG_WIFI_PASSWORD, sizeof(cfg.sta.password));
    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));
    ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_STA, &cfg));
    ESP_ERROR_CHECK(esp_wifi_start());
    ESP_ERROR_CHECK(esp_wifi_set_ps(WIFI_PS_NONE)); /* power save would drop most frames */

    wifi_csi_config_t csi = {
        .lltf_en = true,           /* legacy long training field: 64 bins, present in every OFDM frame */
        .htltf_en = false,
        .stbc_htltf2_en = false,
        .ltf_merge_en = true,
        .channel_filter_en = false, /* raw per-subcarrier values, no smoothing */
        .manu_scale = false,
        .shift = 0,
    };
    ESP_ERROR_CHECK(esp_wifi_set_csi_config(&csi));
    ESP_ERROR_CHECK(esp_wifi_set_csi_rx_cb(csi_rx_cb, NULL));
    ESP_ERROR_CHECK(esp_wifi_set_csi(true));
}

static void udp_sender_task(void *arg)
{
    xEventGroupWaitBits(s_wifi_events, CONNECTED_BIT, pdFALSE, pdTRUE, portMAX_DELAY);
    int sock = socket(AF_INET, SOCK_DGRAM, IPPROTO_IP);
    int yes = 1;
    setsockopt(sock, SOL_SOCKET, SO_BROADCAST, &yes, sizeof(yes));
    struct sockaddr_in dest = {
        .sin_family = AF_INET,
        .sin_port = htons(CONFIG_WFG_SERVER_PORT),
    };
    inet_pton(AF_INET, CONFIG_WFG_SERVER_IP, &dest.sin_addr);
    ESP_LOGI(TAG, "node %d sending CSI to %s:%d", CONFIG_WFG_NODE_ID, CONFIG_WFG_SERVER_IP, CONFIG_WFG_SERVER_PORT);

    csi_msg_t msg;
    for (;;) {
        if (xQueueReceive(s_queue, &msg, portMAX_DELAY) != pdTRUE) {
            continue;
        }
        size_t len = sizeof(csi_header_t) + (size_t)msg.hdr.n_raw * 2;
        if (sendto(sock, &msg, len, 0, (struct sockaddr *)&dest, sizeof(dest)) > 0) {
            s_sent++;
        }
    }
}

static void stats_task(void *arg)
{
    uint32_t last_sent = 0;
    for (;;) {
        vTaskDelay(pdMS_TO_TICKS(5000));
        uint32_t sent = s_sent;
        ESP_LOGI(TAG, "CSI rate %.1f Hz, sent %" PRIu32 ", dropped %" PRIu32,
                 (sent - last_sent) / 5.0, sent, (uint32_t)s_dropped);
        last_sent = sent;
    }
}

void app_main(void)
{
    esp_err_t err = nvs_flash_init();
    if (err == ESP_ERR_NVS_NO_FREE_PAGES || err == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        err = nvs_flash_init();
    }
    ESP_ERROR_CHECK(err);

    s_queue = xQueueCreate(QUEUE_LEN, sizeof(csi_msg_t));
    s_wifi_events = xEventGroupCreate();
    wifi_init();
    xTaskCreate(udp_sender_task, "udp_sender", 4096, NULL, 5, NULL);
    xTaskCreate(stats_task, "stats", 3072, NULL, 1, NULL);
}
