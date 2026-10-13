# Android ilova: jonli 3D xona va yiqilish alerti

Ilova xonaning 3D modelini ko'rsatadi: devorlar, mebel, TX va RX platalar, ular orasidagi WiFi yo'llari va odam figurasi.

- **Yashil** — normal holat. Odam figurasi aniqlangan faoliyatni ko'rsatadi: yuryapti, o'tiribdi, yotibdi, qimirlamayapti yoki xona bo'sh.
- **Qizil** — yiqilish aniqlandi. Ekranda "XAVF" oynasi chiqadi, signal chalinadi va telefon titraydi. 20 soniya ichida odam turmasa, holat "XAVF: turmayapti" ga o'tadi.
- **Kulrang** — server yoki platalar bilan aloqa yo'q.

Ilova yopiq bo'lsa ham fon xizmati serverni kuzatadi. Yiqilishda to'liq ekranli bildirishnoma keladi, signal to'xtovsiz chalinadi va "Tasdiqlash" tugmasi chiqadi.

> **Muhim:** WiFi CSI odamning **faoliyatini** aniqlaydi, uning xonadagi aniq **joyini** emas. Shuning uchun 3D figuraning joylashuvi taxminiy: u yurganda yo'lak bo'ylab yuradi, o'tirganda stulga, yotganda karavotga boradi. Diplomda buni shunday yozing: "vizualizatsiya klassifikator natijasini ko'rsatadi". Aniq joylashuvni aniqlash alohida tadqiqot vazifasi (localization).

## APK ni yuklab olish va o'rnatish

1. Telefonda oching: https://github.com/Akosh36/wifi-fall-guard/releases/tag/android-latest
2. `FallGuard.apk` ni yuklab oling.
3. Faylni oching. Android "noma'lum manbadan o'rnatish"ga ruxsat so'rasa, brauzerga ruxsat bering.
4. Birinchi ochilishda bildirishnomalarga ruxsat bering. Ruxsatsiz fon alerti ishlamaydi.

APK har safar `main` ga `android/` yoki `wfg/server/static/app/` o'zgarishi push qilinganda GitHub Actions'da avtomatik yig'iladi.

## Serverga ulash

1. Kompyuterda serverni ishga tushiring:
   - platalarsiz sinash uchun: `wfg demo`
   - real ESP32-S3 platalar bilan: `wfg serve --source udp`
2. Kompyuterning lokal IP manzilini toping. Windows'da `ipconfig`, Linux/macOS'da `ip a` yoki `ifconfig` buyrug'i bilan, masalan `192.168.1.10`.
3. Telefon kompyuter bilan **bitta WiFi tarmog'ida** bo'lsin.
4. Ilovada ⚙ tugmasini bosing va `http://192.168.1.10:8000` ni kiritib, "Saqlash"ni bosing.

Serverni ishga tushirmasdan ilovani ko'rsatish uchun sozlamalarda **Demo rejimi**ni yoqing. Ilova o'zi sun'iy kunni o'ynaydi: yurish, o'tirish, yotish, yiqilish va alert.

Xuddi shu 3D sahifa kompyuter brauzerida ham ochiladi: `http://localhost:8000/app/`.

## Xonani o'z xonangizga moslash

`configs/default.yaml` dagi `room` bo'limini tahrir qiling. Hamma o'lchovlar metrda.

```yaml
room:
  name: Yotoqxona
  size: [4.0, 3.5, 2.7]      # eni (x), bo'yi (y), balandligi (z)
  tx: [0.3, 0.3, 1.2]        # csi_tx (router) platasi
  rx:                        # csi_rx platalar, kalit = CONFIG_WFG_NODE_ID
    "0": [3.7, 0.4, 1.0]
    "1": [3.7, 3.1, 1.0]
    "2": [0.3, 3.1, 1.0]
  furniture:                 # bed | chair | table | sofa
    - {kind: bed, pos: [3.0, 2.4], size: [1.0, 2.0], rot: 0}
```

Serverni qayta ishga tushirgach, ilova yangi xonani avtomatik chizadi.

## Tuzilishi

| Qism | Fayl |
|---|---|
| 3D sahifa (three.js), ilova va server uchun umumiy | `wfg/server/static/app/` |
| Xona tuzilishi API | `GET /api/room` (`wfg/server/app.py`) |
| Holat oqimi | WebSocket `/ws`, har 0.5 soniyada |
| Android WebView va JS ko'prigi (`window.WFG`) | `android/app/src/main/java/uz/akosh/fallguard/MainActivity.kt` |
| Fon kuzatuvi va alert bildirishnomasi | `AlertService.kt` |
| Signal ovozi va titrash | `Alarm.kt` |
| Telefon qayta yonganda kuzatuvni tiklash | `BootReceiver.kt` |

Android Studio'da ochish uchun `android/` papkasini oching. JDK 17 va Android SDK 35 kerak.

## Cheklovlar

- Ulanish lokal tarmoqda oddiy HTTP orqali ishlaydi, shifrlash yo'q. Uydan tashqarida alert olish uchun Telegram bot ishlatiladi (`docs/architecture.md`).
- APK test kaliti bilan imzolangan. U Play Store uchun emas, faqat to'g'ridan-to'g'ri o'rnatish uchun.
- Ba'zi telefonlar (Xiaomi, Huawei, Samsung) fon ilovalarini o'chirib qo'yadi. Sozlamalarda Fall Guard uchun "Batareya cheklovi yo'q" ni tanlang.
