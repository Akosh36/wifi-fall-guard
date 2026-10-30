# WiFi Fall Guard

**WiFi CSI asosida turli xonalarga moslasha oladigan, keksalar uchun kamerasiz yiqilishni aniqlash tizimi.**

WiFi Fall Guard uyda yolg'iz yashaydigan keksa odamni kamerasiz kuzatadi. Xonaga bir nechta arzon ESP32-S3 platasi qo'yiladi. Ular Wi-Fi signalining har bir subcarrier bo'yicha qanday o'zgarayotganini (Channel State Information, CSI) o'lchaydi. Odam yurganda, o'tirganda yoki yiqilganda signal har xil o'zgaradi. Server shu o'zgarishdan odam nima qilayotganini aniqlaydi va yiqilish bo'lsa yaqinlariga Android ilova hamda Telegram orqali darhol xabar beradi.

Kamera ham, odamga taqiladigan qurilma ham yo'q. Shuning uchun tizim hammom va yotoqxonada ham maxfiylikni buzmasdan ishlaydi, keksa odam esa biror narsani taqib yurishni yoki zaryadlashni unutib qo'ymaydi.

Bu bakalavr diplom ishi loyihasi.

## Tizim nima qiladi

- **Yiqilishni aniqlaydi.** Model 6 ta holatni ajratadi: xona bo'sh, qimirlamay turish, yurish, o'tirish, yotish va yiqilish. Bitta bashorat bilan signal berilmaydi: yiqilish ketma-ket ikki oynada ko'rinishi, keyin odam 20 soniya turmasligi kerak. Odam turib yursa, xavf bekor qilinadi.
- **Yiqilishdan keyin qaror qiladi.** Tizim 3 daqiqa kuzatadi va nafas hamda yurak urishini o'lchaydi. Ko'rsatkichlar xavfli bo'lsa, 30 soniyalik bekor qilinadigan sanoqdan keyin tez yordam (103) chaqiriladi. Ko'rsatkichlar normal bo'lsa yoki o'lchab bo'lmasa, egasidan "Tez yordam chaqirilsinmi?" deb so'raladi, 10 daqiqa javob bo'lmasa chaqiriladi. Batafsil: [docs/escalation.md](docs/escalation.md).
- **Uyni qo'riqlaydi.** Egasi uydan chiqqanda qo'riqlash rejimini yoqadi. Shundan keyin uyda paydo bo'lgan har qanday harakat xavf signalini beradi va egasidan "Politsiya (102) chaqirilsinmi?" deb so'raladi. Harakat davom etsa, politsiya avtomatik chaqiriladi. Batafsil: [docs/security_mode.md](docs/security_mode.md).
- **Nafas va yurak urishini kuzatadi.** Nafas soni odam tinch turganda o'lchanadi. Yurak urishi eksperimental.
- **Odam xonaning qaysi qismida ekanini taxminan ko'rsatadi.** Bu zona darajasidagi baho, aniq koordinata emas.
- **Yangi xonaga moslashadi.** Bir xonada o'qitilgan model boshqa xonada yomonroq ishlaydi, chunki devorlar, mebel va masofalar signalni o'zgartiradi. Tizim yangi xonaga kalibrlashsiz yoki bir necha qisqa klip bilan moslashish usullarini o'z ichiga oladi. Bu diplomning ilmiy qismi.

## Qanday ishlaydi

```
 ESP32-S3 TX (access point)
     │ Wi-Fi, 100 Hz
     ▼
 ESP32-S3 RX ×3..6 ──UDP──► Server (wfg)
                             │ platalarni sinxronlash, 4 s oyna
                             │ tozalash va belgilar (Hampel, low-pass, PCA, Doppler)
                             │ model → 6 holat ehtimoli
                             │ hodisa mantiqi → yiqilish, kuzatuv, qaror
                             ▼
              ┌──────────────┼──────────────┐
         Android ilova    Veb panel     Telegram bot
         (3D xona, alarm)               (xabar, /arm, /status)
```

ESP32 platalari faqat o'lchaydi, barcha hisoblash serverda bajariladi. Server noutbukda yoki Raspberry Pi'da ishlaydi. Arxitektura va asosiy qarorlar: [docs/architecture.md](docs/architecture.md).

## Tarkibiy qismlar

| Qism | Nima qiladi | Hujjat |
|---|---|---|
| **ESP32-S3 proshivkasi** (`firmware/`) | Bitta uzatuvchi (TX) Wi-Fi tarmog'ini ochadi, qabul qiluvchilar (RX) CSI ni o'lchab serverga UDP orqali yuboradi | [firmware/README.md](firmware/README.md), [docs/hardware.md](docs/hardware.md) |
| **Server** (`wfg/`, `wfg` buyrug'i) | Paketlarni qabul qiladi, signalni tozalaydi, modelni ishlatadi, hodisalarni boshqaradi, tarixni SQLite'da saqlaydi | [docs/architecture.md](docs/architecture.md) |
| **Modellar va moslashish** (`wfg/models`, `wfg/adapt`, `wfg/train`) | Klassik model (NumPy), CNN-1D, CNN-2D, Transformer; moslashish usullari MMD, CORAL, DANN, fine-tuning, KNN-MMD | [docs/experiments.md](docs/experiments.md) |
| **Simulyator** (`wfg/csi/simulator.py`) | Fizik CSI simulyatori: har xil xonalar, harakatlar va shovqin. Qurilmasiz sinash va dasturni tekshirish uchun | [docs/architecture.md](docs/architecture.md) |
| **Veb panel** | Brauzerda jonli holat, ehtimollar va hodisalar tarixi | |
| **Telegram bot** | Yaqinlarga xabar, tez yordam/politsiya savoliga tugmalar, `/status`, `/arm`, `/disarm` | [docs/security_mode.md](docs/security_mode.md) |
| **FallGuard Android ilova** (`android/`) | Xonaning jonli 3D ko'rinishi: yashil (normal), qizil (yiqilish), kulrang (aloqa yo'q). To'liq ekranli alarm, yiqilishdan keyingi vaqt chizig'i, qo'riqlash rejimi, telefonda saqlanadigan oflayn tarix | [docs/android.md](docs/android.md) |

Uydan tashqaridan ulanish uchun Tailscale va API paroli (`WFG_TOKEN`) tavsiya etiladi: [docs/security_mode.md](docs/security_mode.md#uydan-tashqaridan-ulanish).

## Ilmiy qism

> Arzon ESP32-S3 platalarida o'qitilgan yiqilishni aniqlash modeli **hech qachon ko'rmagan xonada** qanchalik yaxshi ishlaydi, va bir necha kalibrlash klipi bu farqni qanchalik yopadi?

Ochiq maqolalarda ESP32 bilan "yangi odam" sinovi bor (WiFall), lekin "yangi xona" sinovi yo'q. `wfg experiment` buyrug'i leave-one-room-out sxemasida barcha modellar va moslashish usullarini kalibrlashsiz (k = 0) va bir necha klip bilan (k = 1, 5) solishtiradi. Dataset o'zbek uy sharoitida yoziladi: [docs/dataset_protocol.md](docs/dataset_protocol.md). Tajriba sxemasi va usullar: [docs/experiments.md](docs/experiments.md).

## Tez sinab ko'rish (qurilmasiz)

```bash
git clone https://github.com/Akosh36/wifi-fall-guard && cd wifi-fall-guard
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
wfg demo
```

Brauzerda http://localhost:8000 ni oching. Simulyator taxminan 100 soniyalik ssenariyni takrorlaydi: xona bo'sh, odam kiradi, yuradi, o'tiradi, yotadi, **yiqiladi**, 20 soniya turmaydi va **XAVF** chiqadi, keyin turib yuradi va xavf bekor qilinadi. Birinchi ishga tushishda asos model simulyatsiya ma'lumotida o'qitiladi (1–2 daqiqa).

Android ilovani [android-latest](https://github.com/Akosh36/wifi-fall-guard/releases/tag/android-latest) dan o'rnatish mumkin. Unda serversiz ishlaydigan Demo rejimi bor, serverga ulash esa [docs/android.md](docs/android.md) da.

## Haqiqiy qurilmalar bilan

Minimal to'plam 4 ta ESP32-S3 platasi (1 TX + 3 RX), taxminan $85. Ro'yxat va joylashtirish: [docs/hardware.md](docs/hardware.md). To'liq o'rnatish tartibi: [docs/ornatish.md](docs/ornatish.md).

```bash
wfg nodes                                                    # platalardan paket kelayotganini tekshirish
wfg record --room xona1 --subject s01 --protocol configs/protocol.yaml   # dataset yozish
pip install -e ".[ml]"
wfg train --data data/raw --arch cnn1d --out models/cnn1d   # modelni o'qitish
export WFG_TELEGRAM_TOKEN=123456:ABC...                      # @BotFather dan
wfg serve --source udp --model models/cnn1d.pt               # tizimni ishga tushirish
```

Yaqinlar botga `/start` yozadi va shundan keyin ogohlantirishlarni oladi. Sozlamalar `configs/default.yaml` da, 6 ta plata uchun namuna `configs/room_6nodes.yaml` da.

## Buyruqlar

| Buyruq | Vazifasi |
|---|---|
| `wfg demo` | Simulyator bilan veb panel |
| `wfg serve` | Haqiqiy tizim (`--source udp`) |
| `wfg nodes` | ESP32 platalaridan paketlar kelayotganini tekshirish |
| `wfg record` | Belgilangan dataset yozish |
| `wfg simulate` | Simulyatsiya qilingan dataset yaratish |
| `wfg train` | Bitta modelni o'qitish va saqlash |
| `wfg experiment` | Leave-one-room-out tajribasi va few-shot kalibrlash |
| `wfg stream-eval` | Uzluksiz ssenariylarda baholash (recall, kechikish, soatiga yolg'on signal) |

## Repozitoriy tuzilmasi

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
wfg/inference        real vaqt dvigateli, yiqilish, kuzatuv va qo'riqlash mantiqi
wfg/server           FastAPI, veb panel, 3D xona sahifasi, SQLite, Telegram bot
android/             FallGuard Android ilova
configs/             sozlamalar, dataset protokoli, 6 platali xona namunasi
docs/                batafsil hujjatlar (o'zbek tilida)
results/simulated/   simulyatsiya natijalari (real natija emas)
tests/               avtomatik testlar
```

## Hujjatlar

Barcha hujjatlar o'zbek tilida.

**Hamma uchun.** Loyiha haqida texnik bilimsiz tushunarli, rasmlar va sxemalar bilan: [WiFi-Fall-Guard-oddiy-tilda.docx](docs/WiFi-Fall-Guard-oddiy-tilda.docx) (Word, 5 bet).

**O'rnatish va foydalanish**

| Hujjat | Mavzu |
|---|---|
| [ornatish.md](docs/ornatish.md) | **Qurilmalarga o'rnatish: qadamma-qadam, xariddan to'liq sinovgacha** |
| [hardware.md](docs/hardware.md) | Xarid ro'yxati, platalarni joylashtirish, tarmoq |
| [firmware/README.md](firmware/README.md) | ESP32-S3 platalariga proshivka yozish |
| [android.md](docs/android.md) | Android ilovani o'rnatish va ishlatish |
| [escalation.md](docs/escalation.md) | Yiqilishdan keyingi kuzatuv, tez yordam va politsiya chaqiruvi |
| [security_mode.md](docs/security_mode.md) | Qo'riqlash rejimi, joylashuv, nafas va yurak urishi, masofadan ulanish |

**Texnik va ilmiy qism**

| Hujjat | Mavzu |
|---|---|
| [architecture.md](docs/architecture.md) | Tizim arxitekturasi, modullar, asosiy qarorlar |
| [dataset_protocol.md](docs/dataset_protocol.md) | Dataset yozish protokoli va xavfsizlik |
| [experiments.md](docs/experiments.md) | Tajribalar, usullar, baholash |
| [thesis_outline.md](docs/thesis_outline.md) | Diplomning yozma qismi rejasi |

## Holat va cheklovlar

| Qism | Holat |
|---|---|
| Python tizimi (yig'ish, DSP, modellar, moslashish, server, Telegram, veb panel) | Tayyor, testlar bilan |
| Yiqilishdan keyingi qaror (103) va qo'riqlashdagi politsiya qarori (102) | Tayyor, testlar bilan |
| ESP32-S3 proshivkasi | CI'da ESP-IDF v5.3 bilan kompilyatsiya qilinadi, **haqiqiy platalarda hali sinalmagan** |
| Android ilova | APK CI'da yig'iladi, **haqiqiy telefonda hali sinalmagan** |
| Real dataset va natijalar | Qurilmalar olingandan keyin yoziladi |

- `results/simulated/` dagi raqamlar **faqat simulyator natijasi**. Ular dastur zanjiri ishlashini ko'rsatadi, tizimning haqiqiy aniqligi emas.
- Joylashuv 3 ta plata bilan faqat zona darajasida, yurak urishi esa ESP32 bilan ishonchsiz, shuning uchun noaniq yurak urishi hech qachon avtomatik chaqiruvga olib kelmaydi.
- Android tez yordam yoki politsiya raqamiga o'zi qo'ng'iroq qila olmaydi, faqat raqamni terilgan holda ochadi. To'liq avtomatik chaqiruv uchun server `call_webhook` orqali tashqi qurilma yoki xizmatga murojaat qiladi ([docs/escalation.md](docs/escalation.md#4-tez-yordam-qanday-chaqiriladi)).

## Manbalar

- Zhao va boshq., *KNN-MMD: Cross Domain Wireless Sensing via Local Distribution Alignment* (WiFall dataseti), arXiv:2412.04783
- *Robust Cross-Domain WiFi Fall Detection via Physics-Driven Attention-Enhanced Transformers*, arXiv:2605.00869
- *Towards a Robust WiFi-based Fall Detection with Adversarial Data Augmentation*, arXiv:2005.11932
- RuView: https://github.com/ruvnet/RuView
- Espressif ESP-CSI: https://github.com/espressif/esp-csi

Litsenziya: MIT.
