# Qurilmalar va o'rnatish

4–6 tugunli to'liq qo'llanma (xarid, ulash, `flash_node.py` bilan proshivka, 5 RX joylashuvi, tekshirish ketma-ketligi): [hardware_nodes.md](hardware_nodes.md).

## Xarid ro'yxati

Narxlar 2026-yil oktabr holatiga taxminiy (AliExpress va mahalliy do'konlar), 1$ ≈ 12 500 so'm deb olingan.

| Qism | Soni | Taxminiy narx | Izoh |
|---|---|---|---|
| ESP32-S3-DevKitC-1**U** (tashqi antenna ulagichi bor) | 4 (minimal) / 6 (tavsiya) | ~$10 dona | "1U" varianti antenna ulash uchun. Oddiy "1" variant ham ishlaydi, lekin signal barqarorligi pastroq |
| 2.4 GHz IPEX antenna (3 dBi) | 4–6 | ~$2 dona | Faqat 1U variant uchun |
| USB-C kabel va 5V/1A adapter yoki powerbank | 4–6 | ~$4 dona | |
| Kichik shtativ yoki tagliklar | 4 | ~$7 dona | Platalarni har bir xonada **bir xil balandlikda** (taxminan 1 m) qo'yish uchun |
| Sport matrasi | 1 | ~$30 | Yiqilishlarni xavfsiz yozish uchun |
| Raspberry Pi 5 (4 GB) to'plami | 1 (ixtiyoriy) | ~$90 | Doimiy ishlaydigan server. Dataset yozish va tajribalar uchun noutbuk yetarli |

**Jami:** minimal taxminan $85, tavsiya etilgan to'plam taxminan $290.

## Xonaga joylashtirish

```
   +-----------------------------------------+
   |  RX0 (burchakda, 1 m)        RX1        |
   |                                         |
   |              [ yurish va                |
   |                yiqilish zonasi ]        |
   |                                         |
   |  TX (qarama-qarshi devor, 1 m)    RX2   |
   +-----------------------------------------+
```

Qoidalar:

1. **TX va RX lar orasida odam harakat qiladigan zona bo'lsin.** Signal tanadan qaytganda o'zgaradi, shuning uchun odam "yo'l ustida" bo'lishi kerak.
2. Qabul qiluvchilarni **turli burchaklarga** qo'ying, bir qatorga emas. Har biri harakatni boshqa tomondan "ko'radi".
3. Platalar orasidagi masofa 2–5 m. Juda yaqin (0.5 m dan kam) bo'lsa signal to'yinadi.
4. Har bir xonada joylashuvni **rasmga oling** va o'lchab yozing (`session.json` ning `notes` maydoniga). Bu diplomdagi "tajriba sharoitlari" bo'limi uchun kerak.
5. Yozish paytida xonada boshqa odam yurmasin. Ventilyator va konditsionerni o'chiring yoki buni ham yozib qo'ying.

## Tarmoq sxemasi

```
 [csi_tx AP "WFG-NET", 192.168.4.1]
        |  ping javoblari (100 Hz)  -> har bir RX shu kadrlardan CSI o'lchaydi
   +----+-----+-----------+
 [RX0]     [RX1]       [RX2]   -- UDP 5500 -->  [Noutbuk / RPi, 192.168.4.2]
                                                  wfg record / wfg serve
```

Noutbuk `WFG-NET` ga ulanganda internet bo'lmaydi. Telegram ogohlantirishlari uchun serverga ikkinchi tarmoq (Ethernet yoki ikkinchi Wi-Fi adapter) kerak, yoki uy routeri rejimidan foydalaning (`csi_rx` ni uy routeriga ulang).
