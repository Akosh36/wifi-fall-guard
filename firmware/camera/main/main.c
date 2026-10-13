/*
 * WiFi Fall Guard - optional snapshot camera (ESP32-S3 + OV2640/OV5640)
 *
 * The main system is camera-free. This board only answers
 *     GET /snapshot.jpg?key=...
 * with one JPEG frame. The server asks for a frame only during a fall
 * episode (docs/escalation.md, camera.snapshot_url); nothing is streamed or
 * stored on the board.
 *
 *     camera:
 *       snapshot_url: http://192.168.4.31/snapshot.jpg?key=<CONFIG_WFG_KEY>
 */
#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_wifi.h"
#include "esp_event.h"
#include "esp_log.h"
#include "esp_netif.h"
#include "esp_http_server.h"
#include "nvs_flash.h"
#include "lwip/inet.h"
#include "esp_camera.h"
#include "sdkconfig.h"

static const char *TAG = "camera";

#if CONFIG_WFG_CAM_XIAO_S3
/* Seeed XIAO ESP32S3 Sense */
#define PIN_XCLK 10
#define PIN_SIOD 40
#define PIN_SIOC 39
#define PIN_D7 48
#define PIN_D6 11
#define PIN_D5 12
#define PIN_D4 14
#define PIN_D3 16
#define PIN_D2 18
#define PIN_D1 17
#define PIN_D0 15
#define PIN_VSYNC 38
#define PIN_HREF 47
#define PIN_PCLK 13
#else
/* ESP32-S3-EYE layout, also used by Freenove ESP32-S3-WROOM CAM and most clones */
#define PIN_XCLK 15
#define PIN_SIOD 4
#define PIN_SIOC 5
#define PIN_D7 16
#define PIN_D6 17
#define PIN_D5 18
#define PIN_D4 12
#define PIN_D3 10
#define PIN_D2 8
#define PIN_D1 9
#define PIN_D0 11
#define PIN_VSYNC 6
#define PIN_HREF 7
#define PIN_PCLK 13
#endif

static esp_err_t camera_init(void)
{
    camera_config_t c = {
        .pin_pwdn = -1,
        .pin_reset = -1,
        .pin_xclk = PIN_XCLK,
        .pin_sccb_sda = PIN_SIOD,
        .pin_sccb_scl = PIN_SIOC,
        .pin_d7 = PIN_D7, .pin_d6 = PIN_D6, .pin_d5 = PIN_D5, .pin_d4 = PIN_D4,
        .pin_d3 = PIN_D3, .pin_d2 = PIN_D2, .pin_d1 = PIN_D1, .pin_d0 = PIN_D0,
        .pin_vsync = PIN_VSYNC,
        .pin_href = PIN_HREF,
        .pin_pclk = PIN_PCLK,
        .xclk_freq_hz = 20000000,
        .ledc_timer = LEDC_TIMER_0,
        .ledc_channel = LEDC_CHANNEL_0,
        .pixel_format = PIXFORMAT_JPEG,
        .frame_size = FRAMESIZE_VGA,   /* 640x480 is enough to see a person on the floor */
        .jpeg_quality = 12,
        .fb_count = 2,
        .fb_location = CAMERA_FB_IN_PSRAM,
        .grab_mode = CAMERA_GRAB_LATEST, /* always the newest frame, not a stale one */
    };
    return esp_camera_init(&c);
}

static esp_err_t snapshot_get(httpd_req_t *req)
{
    if (strlen(CONFIG_WFG_KEY) > 0) {
        char q[96], key[64];
        if (httpd_req_get_url_query_str(req, q, sizeof(q)) != ESP_OK ||
            httpd_query_key_value(q, "key", key, sizeof(key)) != ESP_OK || strcmp(key, CONFIG_WFG_KEY) != 0) {
            httpd_resp_send_err(req, HTTPD_403_FORBIDDEN, "bad key");
            return ESP_OK;
        }
    }
    camera_fb_t *fb = esp_camera_fb_get();
    if (!fb) {
        httpd_resp_send_err(req, HTTPD_500_INTERNAL_SERVER_ERROR, "no frame");
        return ESP_OK;
    }
    httpd_resp_set_type(req, "image/jpeg");
    httpd_resp_set_hdr(req, "Cache-Control", "no-store");
    esp_err_t r = httpd_resp_send(req, (const char *)fb->buf, fb->len);
    ESP_LOGI(TAG, "snapshot sent (%u bytes)", (unsigned)fb->len);
    esp_camera_fb_return(fb);
    return r;
}

static esp_netif_t *s_netif;

static void wifi_event_handler(void *arg, esp_event_base_t base, int32_t id, void *data)
{
    if (base == WIFI_EVENT && (id == WIFI_EVENT_STA_START || id == WIFI_EVENT_STA_DISCONNECTED)) {
        esp_wifi_connect();
    } else if (base == WIFI_EVENT && id == WIFI_EVENT_STA_CONNECTED && strlen(CONFIG_WFG_STATIC_IP) > 0) {
        /* fixed address, so the server's URL for this board never changes */
        esp_netif_dhcpc_stop(s_netif);
        esp_netif_ip_info_t ip = {0};
        ip.ip.addr = ipaddr_addr(CONFIG_WFG_STATIC_IP);
        ip.gw.addr = ipaddr_addr(CONFIG_WFG_GATEWAY);
        ip.netmask.addr = ipaddr_addr("255.255.255.0");
        ESP_ERROR_CHECK(esp_netif_set_ip_info(s_netif, &ip));
    } else if (base == IP_EVENT && id == IP_EVENT_STA_GOT_IP) {
        ip_event_got_ip_t *e = (ip_event_got_ip_t *)data;
        ESP_LOGI(TAG, "ready: http://" IPSTR "/snapshot.jpg", IP2STR(&e->ip_info.ip));
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
    while ((err = camera_init()) != ESP_OK) {
        ESP_LOGE(TAG, "camera init failed (%s): check the ribbon cable and the board pinout in menuconfig",
                 esp_err_to_name(err));
        vTaskDelay(pdMS_TO_TICKS(5000));
    }
    wifi_init();
    httpd_config_t cfg = HTTPD_DEFAULT_CONFIG();
    httpd_handle_t h;
    ESP_ERROR_CHECK(httpd_start(&h, &cfg));
    httpd_uri_t snap = {.uri = "/snapshot.jpg", .method = HTTP_GET, .handler = snapshot_get};
    httpd_register_uri_handler(h, &snap);
}
