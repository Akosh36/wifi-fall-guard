# WiFi Fall Guard

**WiFi CSI asosida turli xonalarga moslasha oladigan, keksalar uchun kamerasiz yiqilishni aniqlash tizimi.**
Bakalavr diplom ishi loyihasi.

Arzon ESP32-S3 platalari Wi-Fi signalining har bir subcarrier bo'yicha o'zgarishini (Channel State Information, CSI) o'lchaydi. Odam yiqilganda signal o'ziga xos tarzda o'zgaradi: qisqa, tez harakat (yuqori Doppler) va undan keyin harakatsizlik. Tizim buni aniqlaydi, odam 20 soniya ichida turmasa qarindoshlarga Telegram orqali xabar yuboradi. Kamera yo'q, shuning uchun hammom va yotoqxonada ham maxfiylik saqlanadi.

Ilmiy qism: model **hech qachon ko'rmagan xonada** qanchalik ishlashi va bir necha kalibrlash klipi bilan qanchalik tiklanishi (MMD, CORAL, DANN, fine-tuning, KNN-MMD).

```
ESP32-S3 TX ──WiFi──► ESP32-S3 RX ×3 ──UDP──► Server: tozalash → model → hodisa mantiqi ──► Veb panel
                                                                                      └────► Telegram
```

## Tez boshlash (qurilmasiz, simulyator bilan)

```bash
git clone https://github.com/Akosh36/wifi-fall-guard && cd wifi-fall-guard
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
wfg demo
```

Brauzerda http://localhost:8000 oching. Simulyator taxminan 100 soniyalik ssenariyni takrorlaydi: xona bo'sh, odam kiradi, yuradi, o'tiradi, yotadi, **yiqiladi**, 20 soniya turmaydi → **XAVF**, keyin turib yuradi → bekor qilinadi. Birinchi ishga tushishda asos model simulyatsiya ma'lumotida o'qitiladi (taxminan 1–2 daqiqa).

## Android ilova

Jonli 3D xona ko'rinishi: normal holatda yashil, yiqilishda qizil va xavf alerti chiqadi. APK: [android-latest](https://github.com/Akosh36/wifi-fall-guard/releases/tag/android-latest). O'rnatish va ulash: [docs/android.md](docs/android.md).

## Haqiqiy qurilmalar bilan

1. Qurilmalarni sotib oling va joylashtiring: [docs/hardware.md](docs/hardware.md)
2. Proshivkani yozing: [firmware/README.md](firmware/README.md)
3. Platalarni tekshiring: `wfg nodes`
4. Dataset yozing: [docs/dataset_protocol.md](docs/dataset_protocol.md)
   ```bash
   wfg record --room xona1_gisht --subject s01 --protocol configs/protocol.yaml
   ```
5. Tajriba va diplom jadvallari: [docs/experiments.md](docs/experiments.md)
   ```bash
   pip install -e ".[ml]"
   wfg experiment --data data/raw --methods classic cnn1d cnn1d+dann cnn1d+knnmmd --shots 0 1 5 --seeds 0 1 2
   ```
6. Modelni o'qitib, tizimni ishga tushiring:
   ```bash
   wfg train --data data/raw --arch cnn1d --out models/cnn1d
   export WFG_TELEGRAM_TOKEN=123456:ABC...        # @BotFather dan
   wfg serve --source udp --model models/cnn1d.pt
   ```
   Qarindoshlar botga `/start` yozadi, shundan keyin ogohlantirishlarni oladi. `/status` joriy holatni ko'rsatadi.

## Buyruqlar

| Buyruq | Vazifasi |
|---|---|
| `wfg demo` | Simulyator bilan veb panel |
| `wfg serve` | Haqiqiy tizim (`--source udp`) |
| `wfg nodes` | ESP32 platalaridan paketlar kelayotganini tekshirish |
| `wfg record` | Belgilangan dataset yozish |
| `wfg simulate` | Simulyatsiya qilingan dataset yaratish |
| `wfg train` | Bitta modelni o'qitish va saqlash |
| `wfg experiment` | Leave-one-room-out tajribasi + few-shot kalibrlash |
| `wfg stream-eval` | Uzluksiz ssenariylarda real vaqt baholash (recall, kechikish, yolg'on signal/soat) |

## Loyiha tuzilmasi

```
firmware/csi_tx      ESP32-S3 uzatuvchi (access point)
firmware/csi_rx      ESP32-S3 qabul qiluvchi (CSI → UDP)
wfg/csi              paket formati, fizik CSI simulyatori
wfg/collector        UDP qabul qilish, platalarni sinxronlash, dataset yozish
wfg/dsp              signalni tozalash va belgilar
wfg/baseline         NumPy asos model
wfg/models           CNN-1D, CNN-2D, Transformer (PyTorch)
wfg/adapt            MMD, CORAL, DANN
wfg/train            o'qitish, few-shot, tajribalar, metrikalar
wfg/inference        real vaqt dvigateli, hodisa mantiqi
wfg/server           FastAPI, veb panel, 3D xona sahifasi (/app/), SQLite, Telegram bot
android/             Android ilova: jonli 3D xona, yashil/qizil holat, yiqilish alerti
docs/                arxitektura, qurilmalar, dataset protokoli, tajribalar, diplom rejasi
```

Batafsil: [docs/architecture.md](docs/architecture.md). Diplomning yozma qismi rejasi: [docs/thesis_outline.md](docs/thesis_outline.md).

## Holat

| Qism | Holat |
|---|---|
| Python tizimi (yig'ish, DSP, modellar, moslashish, server, Telegram, veb panel) | Tayyor, testlar bilan |
| ESP32-S3 proshivkasi | Yozilgan, CI'da ESP-IDF v5.3 bilan kompilyatsiya qilinadi. Haqiqiy platalarda hali sinalmagan |
| Android ilova (3D xona, alert) | Yozilgan, APK CI'da yig'iladi: [docs/android.md](docs/android.md) |
| Simulyatsiya natijalari | `results/simulated/` (faqat zanjir ishlashini ko'rsatadi, diplom uchun real natija emas) |
| Real dataset va natijalar | Qurilmalar kelgandan keyin |

## Manbalar

- Zhao va boshq., *KNN-MMD: Cross Domain Wireless Sensing via Local Distribution Alignment* (WiFall dataseti), arXiv:2412.04783
- *Robust Cross-Domain WiFi Fall Detection via Physics-Driven Attention-Enhanced Transformers*, arXiv:2605.00869
- *Towards a Robust WiFi-based Fall Detection with Adversarial Data Augmentation*, arXiv:2005.11932
- RuView: https://github.com/ruvnet/RuView
- Espressif ESP-CSI: https://github.com/espressif/esp-csi

Litsenziya: MIT.
