# ESP32-S3 proshivkasi

Ikki loyiha bor:

| Papka | Vazifasi | Nechta plata |
|---|---|---|
| `csi_tx` | Uzatuvchi. `WFG-NET` nomli Wi-Fi tarmog'ini (access point) ochadi, 6-kanalda ishlaydi | 1 |
| `csi_rx` | Qabul qiluvchi. `WFG-NET` ga ulanadi, sekundiga 100 marta ping yuboradi, javob kadrlaridan CSI o'lchab serverga UDP orqali yuboradi | 3 (yoki ko'proq) |

Uy routeridan ham foydalanish mumkin: unda `csi_tx` kerak emas, `csi_rx` sozlamasida routerning SSID va parolini yozing. Lekin har bir xonada o'z TX platangizni ishlatish tajribalarni solishtirishni osonlashtiradi (kanal va quvvat bir xil bo'ladi).

## O'rnatish

1. [ESP-IDF v5.3](https://docs.espressif.com/projects/esp-idf/en/v5.3/esp32s3/get-started/) o'rnating (Windows uchun "ESP-IDF Tools Installer").
2. Uzatuvchi:
   ```bash
   cd firmware/csi_tx
   idf.py set-target esp32s3
   idf.py build flash monitor
   ```
3. Har bir qabul qiluvchi uchun (`WFG_NODE_ID` ni 0, 1, 2 qilib o'zgartiring):
   ```bash
   cd firmware/csi_rx
   idf.py set-target esp32s3
   idf.py menuconfig      # "WiFi Fall Guard receiver" bo'limi
   idf.py build flash monitor
   ```
   `menuconfig` sozlamalari:
   - **Server IP**: noutbukingiz `WFG-NET` ga ulangandan keyingi IP manzili (odatda `192.168.4.2`). Bilmasangiz `255.255.255.255` yozing, paketlar butun tarmoqqa yuboriladi.
   - **Node id**: har bir platada boshqacha: 0, 1, 2.
   - **CSI sampling rate**: 100 Hz.

4. Noutbukni `WFG-NET` tarmog'iga ulang (parol `wfg12345`) va tekshiring:
   ```bash
   wfg nodes
   # #0: ON  99.8 Hz loss 0.2% rssi -41  #1: ON 100.1 Hz ...
   ```
   Har bir plata taxminan 100 Hz ko'rsatishi kerak.

## Paket formati

`csi_rx` har bir CSI o'lchovini 148 baytli UDP paket qilib yuboradi: 20 bayt sarlavha (magic `0xC51A`, node id, tartib raqami, vaqt, RSSI, shovqin, kanal) va 64 juft `int8 (imag, real)`. Python tomonidagi tavsif: `wfg/csi/packet.py`. Ikkala tomon bir-biriga mos bo'lishi shart.

## Muammolar

| Belgi | Sabab va yechim |
|---|---|
| `wfg nodes` da paket yo'q | Server IP noto'g'ri yoki noutbukning firewall'i UDP 5500 portini yopgan |
| Rate 100 Hz dan ancha past | Plata routerdan uzoq, yoki tarmoqda boshqa trafik ko'p. `csi_tx` dan foydalaning |
| `loss` 5% dan yuqori | Antennani tekshiring, platalarni bir-biriga juda yaqin qo'ymang |
