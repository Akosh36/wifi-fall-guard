/*
 * WiFi Fall Guard - transmitter node (ESP32-S3)
 *
 * A dedicated access point on a fixed channel. Receiver nodes and the server
 * laptop join it; the receivers ping it ~100 times per second, and every
 * ping reply it sends is the frame whose CSI the receivers measure.
 *
 * Using our own transmitter instead of the home router keeps the channel,
 * transmit power and traffic identical in every room, which makes recordings
 * from different rooms comparable. 802.11b is disabled so every frame uses
 * OFDM (only OFDM frames carry the LTF that CSI is estimated from).
 */
#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_wifi.h"
#include "esp_event.h"
#include "esp_log.h"
#include "esp_netif.h"
#include "nvs_flash.h"
#include "sdkconfig.h"

static const char *TAG = "csi_tx";

static void wifi_event_handler(void *arg, esp_event_base_t base, int32_t id, void *data)
{
    if (id == WIFI_EVENT_AP_STACONNECTED) {
        wifi_event_ap_staconnected_t *e = (wifi_event_ap_staconnected_t *)data;
        ESP_LOGI(TAG, "station " MACSTR " joined (aid %d)", MAC2STR(e->mac), e->aid);
    } else if (id == WIFI_EVENT_AP_STADISCONNECTED) {
        wifi_event_ap_stadisconnected_t *e = (wifi_event_ap_stadisconnected_t *)data;
        ESP_LOGI(TAG, "station " MACSTR " left", MAC2STR(e->mac));
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
    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());
    esp_netif_create_default_wifi_ap();

    wifi_init_config_t init = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&init));
    ESP_ERROR_CHECK(esp_event_handler_register(WIFI_EVENT, ESP_EVENT_ANY_ID, wifi_event_handler, NULL));
    ESP_ERROR_CHECK(esp_wifi_set_storage(WIFI_STORAGE_RAM));

    wifi_config_t cfg = {0};
    strlcpy((char *)cfg.ap.ssid, CONFIG_WFG_AP_SSID, sizeof(cfg.ap.ssid));
    strlcpy((char *)cfg.ap.password, CONFIG_WFG_AP_PASSWORD, sizeof(cfg.ap.password));
    cfg.ap.ssid_len = strlen(CONFIG_WFG_AP_SSID);
    cfg.ap.channel = CONFIG_WFG_AP_CHANNEL;
    cfg.ap.max_connection = 8;
    cfg.ap.authmode = strlen(CONFIG_WFG_AP_PASSWORD) >= 8 ? WIFI_AUTH_WPA2_PSK : WIFI_AUTH_OPEN;
    cfg.ap.beacon_interval = 100;

    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_AP));
    ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_AP, &cfg));
    ESP_ERROR_CHECK(esp_wifi_set_protocol(WIFI_IF_AP, WIFI_PROTOCOL_11G | WIFI_PROTOCOL_11N));
    ESP_ERROR_CHECK(esp_wifi_set_bandwidth(WIFI_IF_AP, WIFI_BW_HT20));
    ESP_ERROR_CHECK(esp_wifi_start());
    ESP_ERROR_CHECK(esp_wifi_set_ps(WIFI_PS_NONE));
    ESP_ERROR_CHECK(esp_wifi_set_max_tx_power(CONFIG_WFG_TX_POWER_QDBM));

    ESP_LOGI(TAG, "access point \"%s\" on channel %d is up (gateway 192.168.4.1)", CONFIG_WFG_AP_SSID,
             CONFIG_WFG_AP_CHANNEL);
    for (;;) {
        wifi_sta_list_t list;
        if (esp_wifi_ap_get_sta_list(&list) == ESP_OK) {
            ESP_LOGI(TAG, "%d station(s) connected", list.num);
        }
        vTaskDelay(pdMS_TO_TICKS(10000));
    }
}
