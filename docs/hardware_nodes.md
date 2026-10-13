# 4–6 tugunli qurilma rejasi: xarid, ulash, proshivka, joylashtirish, tekshirish

Bu hujjat [hardware.md](hardware.md) ning davomi: bitta xonada 4 tadan 6 tagacha sensor plata, shuningdek qo'shimcha GSM (avtomatik qo'ng'iroq) va kamera platalari bilan ishlash bo'yicha amaliy qo'llanma. Yiqilishdan keyingi qaror mantiqi: [escalation.md](escalation.md).

## 1. Qaysi variant

| Variant | Platalar | Qachon |
|---|---|---|
| **Minimal (4)** | 1 TX + 3 RX | Birinchi sinov, dataset yozishni boshlash. Hozirgi `configs/default.yaml` shunga sozlangan |
| **Tavsiya (6)** | 1 TX + 5 RX | Asosiy tajribalar. Ko'proq RX = xonaning ko'proq qismi "ko'rinadi", yiqilishni aniqlash barqarorroq va bitta plata o'chsa ham tizim ishlaydi |
| **Maksimal** | 1 TX + 6 RX | Tayyor sozlama bor: [`configs/room_6nodes.yaml`](../configs/room_6nodes.yaml) (2 tasi polga yaqin, 0.4 m). Diplomda "3 RX va 6 RX ni solishtirish" alohida tajriba bo'la oladi |
| + GSM plata | +1 ESP32 + SIM800L | Telefon va internetsiz avtomatik qo'ng'iroq va SMS (7-bo'lim) |
| + Kamera (ixtiyoriy) | +1 ESP32-S3 CAM | Faqat yiqilishda bitta surat (8-bo'lim) |

Server avtomatik qaror qilishi uchun kamida 2 ta plata onlayn bo'lishi kerak (`escalation.min_nodes_online`, 6 tali sozlamada 4).

Har doim **1 ta zaxira plata** oling: bittasi kuyishi yoki USB ulagichi sinishi mumkin.

Cheklovlar: `csi_tx` 10 tagacha ulanishni qabul qiladi (6 RX + GSM + kamera + noutbuk = 9, yetadi; telefonni uy routeriga ulang yoki kamerasiz ishlating). 5–6 ta RX har biri 100 Hz da ishlasa, efirda sekundiga ~1000 ta kichik kadr bo'ladi. Bu ESP32-S3 uchun normal, lekin `wfg nodes` da tezlik 90 Hz dan tushib ketsa, barcha RX larni 50 Hz ga o'tkazing (`--hz 50`, pastga qarang) va `configs/default.yaml` dagi `fs` ni ham 50 qiling.

## 2. Xarid ro'yxati

Narxlar 2026-yil oktabr holatiga taxminiy. O'zbekistonda: [OLX.uz](https://www.olx.uz/elektronika/q-esp32-s/) va Toshkentdagi elektronika do'konlari / Telegram kanallari (tez, lekin qimmatroq), AliExpress (arzon, yetkazish odatda 2–4 hafta). Shoshilinch bo'lsa 1–2 ta platani mahalliy olib proshivkani sinab ko'ring, qolganini AliExpress dan buyurtma qiling.

### Asosiy (majburiy)

| Qism | Soni (4 / 6 variant) | Taxminiy narx | Nimaga e'tibor berish |
|---|---|---|---|
| **ESP32-S3-DevKitC-1** (N8R2, N16R8 ham bo'ladi) | 5 / 7 (zaxira bilan) | $7–12 dona | Nomida aniq **S3** bo'lsin (oddiy ESP32 yoki C3 emas). Ikkita USB-C ulagichli (USB va UART/COM) variant qulay. Klonlar ham ishlaydi |
| ↳ yoki **DevKitC-1U** + 2.4 GHz IPEX antenna | xuddi shuncha | +$2 antenna | Tashqi antenna signalni barqarorroq qiladi. **Antennasiz yoqmang** |
| USB-C kabel (**ma'lumot uzatadigan**, faqat zaryad emas) | 5 / 7 | $1.5–3 | Proshivka uchun kamida 1 tasi aniq "data" kabel bo'lsin. 1.5–2 m uzunlik joylashtirishni osonlashtiradi |
| 5 V USB adapter, kamida **1 A** | 4 / 6 | $2–4 | Yoki bitta ko'p portli USB zaryadlovchi (4–6 port, jami 3 A+) va uzun kabellar. 0.5 A li eski adapterlar WiFi paytida qayta yuklanishga olib keladi |
| Shtativ (telefon shtativi, 1 m gacha) yoki devor tagligi | 4 / 6 | $3–7 | Hamma platalar **bir xil balandlikda** turishi kerak |
| Sport matrasi | 1 | ~$25–30 | Yiqilishlarni xavfsiz yozish uchun |
| Ruletka (5 m) va stikerlar | 1 | ~$3 | Plata joylarini o'lchash, platalarni "TX", "RX0"... deb belgilash |

### Haqiqiy qiymat (ground truth) uchun

| Qism | Soni | Narx | Vazifasi |
|---|---|---|---|
| **Barmoq pulsoksimetri** | 1 | $10–20 | Yurak urishi va SpO2 ni ko'z bilan tekshirish. Arzonlari ma'lumot saqlamaydi, shuning uchun 30 s da bir qiymatni yozib borasiz |
| **MAX30102** puls sensori moduli | 1–2 | $2–4 | Zaxira ESP32-S3 ga ulanadi va yurak urishini avtomatik yozadi (pastda ulash sxemasi). Diplomda "CSI dan olingan puls vs sensor" grafigi uchun eng arzon yo'l |
| Polar H10 ko'krak kamari (ixtiyoriy) | 1 | ~$90 | Eng aniq variant (BLE). Byudjet bo'lsa, ilmiy jihatdan eng kuchli dalil |

Nafas uchun alohida sensor shart emas: ko'ngilli metronom ostida nafas oladi (masalan, minutiga 12 va 20), yoki ko'krak harakatini qo'lda sanaysiz.

### Ixtiyoriy: kamera

Loyihaning asosiy g'oyasi **kamerasiz** kuzatuv, shuning uchun kamera tizimning bir qismi emas. U faqat ikkita joyda foydali:

1. **Dataset belgilash (tavsiya).** Yozish paytida telefonni shtativga qo'yib video oling. Keyin yiqilish qachon bo'lganini video bo'yicha aniq belgilaysiz. Qo'shimcha xarid kerak emas; USB veb-kamera ($12–20) ham bo'ladi. Ko'ngillidan yozma rozilik oling.
2. **Yiqilishdan keyin bitta surat (ixtiyoriy).** ESP32-S3 kamerali plata, **PSRAM li** (N8R8 yoki N16R8) va OV2640 bilan: ESP32-S3-EYE, Freenove ESP32-S3-WROOM CAM yoki "ESP32-S3 CAM" klonlari ($12–20), yoki Seeed XIAO ESP32S3 Sense (~$15). Surat faqat yiqilish holatida olinib Telegram va ilovaga yuboriladi. Proshivka: `firmware/camera` (8-bo'lim). Bu shaxsiy hayot daxlsizligi bilan bog'liq, shuning uchun diplomda "o'chirib qo'yiladigan qo'shimcha" deb ko'rsating.

### Avtomatik qo'ng'iroq uchun GSM plata

Android ilova 103 ga o'zi qo'ng'iroq qila olmaydi (telefon terish oynasini ochadi, bitta tugmani odam bosishi kerak). To'liq avtomatik qo'ng'iroq uchun alohida GSM plata kerak:

| Qism | Soni | Narx | Izoh |
|---|---|---|---|
| **SIM800L** moduli (spiral antenna bilan) | 1 | $3–6 | 2G (GSM). Arzon va hamma joyda bor. Operatoringizda 2G hali ishlashini SIM kartani oddiy eski telefonga qo'yib tekshiring |
| ↳ yoki **A7670E** / **SIM7600** (4G LTE) | 1 | $20–35 | 2G o'chirilgan bo'lsa yoki ishonchliroq variant kerak bo'lsa. Proshivka bir xil |
| ESP32-S3 (zaxira platadan) | 1 | — | |
| 18650 Li-ion akkumulyator + TP4056 zaryad moduli (himoyali) | 1 | $4–6 | SIM800L ga 3.7–4.2 V va **2 A gacha cho'qqi tok** kerak. Akkumulyator elektr o'chganda ham ishlashini ta'minlaydi |
| ↳ yoki MP1584 / LM2596 pasaytiruvchi modul (4.0 V ga sozlanadi) | 1 | $1–2 | Akkumulyatorsiz variant |
| 1000 µF 10 V kondensator | 1 | $0.3 | SIM800L VCC yoniga, tok cho'qqilari uchun |
| 10 kΩ va 20 kΩ rezistor | 1+1 | — | ESP32 TX → SIM800L RX kuchlanish bo'luvchisi |
| 8 Ω kichik dinamik + elektret mikrofon | 1+1 | $1–2 | Ixtiyoriy: yerdagi odam dispetcher bilan gaplasha olishi uchun |
| SIM karta (PIN kodsiz, balansli) | 1 | — | |

### Jami

| | 4 tugun | 6 tugun |
|---|---|---|
| Platalar (zaxira bilan), kabel, adapter, shtativ | ~$85 | ~$125 |
| Matras, ruletka | ~$30 | ~$30 |
| Pulsoksimetr + MAX30102 | ~$20 | ~$20 |
| **Jami (kamera va GSM siz)** | **~$135** | **~$175** |
| GSM plata (SIM800L, akkumulyator, mayda qismlar) | +$12 | +$12 |
| Kamera plata | +$15 | +$15 |

Raspberry Pi (~$90) shart emas: dataset yozish va tajribalar uchun noutbuk yetadi.

## 3. Ulash va quvvat

Har bir plata faqat **USB-C orqali 5 V** oladi, boshqa sim kerak emas.

- DevKitC-1 da ikkita USB-C bo'lsa: proshivka uchun **"UART"** (yoki "COM") deb yozilganidan foydalaning. Ishlash vaqtida quvvat uchun istalgani bo'ladi.
- Bitta plata WiFi bilan 0.1–0.35 A oladi (qisqa cho'qqilar 0.5 A gacha). 1 A li adapter yetadi.
- Quvvatsiz (tashqi adaptersiz) USB hub dan 5–6 platani oziqlantirmang.
- Uzun sinovlarda powerbank ishlatsangiz, ba'zi powerbanklar kam tok olinganda o'zi o'chadi. Shu sababli doimiy ishlash uchun devor adapteri yaxshiroq.
- DevKitC-1**U** bo'lsa, antennani **quvvat berishdan oldin** ulang.

### MAX30102 ni zaxira ESP32-S3 ga ulash

```
MAX30102      ESP32-S3-DevKitC-1
  VIN  ----->  3V3
  GND  ----->  GND
  SDA  ----->  GPIO 8
  SCL  ----->  GPIO 9
  INT  ----->  (ulanmasa ham bo'ladi)
```

Bu plata uchun proshivka (pulsni server vaqti bilan birga yozib boradigan) hali yo'q, keyingi bosqichda qo'shiladi.

## 4. Proshivka (bir marta sozlash, keyin har bir plata 1 buyruq)

1. [ESP-IDF v5.3](https://docs.espressif.com/projects/esp-idf/en/v5.3/esp32s3/get-started/) ni o'rnating (Windows: "ESP-IDF Tools Installer", keyin "ESP-IDF 5.3 PowerShell" ni oching).
2. Platani "UART" porti orqali ulang. Windows "Device Manager → Ports" da COM port paydo bo'lishi kerak. Paydo bo'lmasa, platadagi USB-UART chip drayverini o'rnating: plata ustida **CP2102** yozilgan bo'lsa Silicon Labs CP210x drayveri, **CH343/CH340** bo'lsa WCH drayveri.
3. Repo ichida `firmware/` papkasiga o'ting va har bir platani bitta buyruq bilan yozing. `menuconfig` ni qo'lda ochish shart emas:

   ```bash
   cd firmware
   python flash_node.py tx --port COM3          # uzatuvchi
   python flash_node.py rx 0 --port COM4        # qabul qiluvchilar
   python flash_node.py rx 1 --port COM4        # plata almashtirilgandan keyin
   python flash_node.py rx 2 --port COM4
   python flash_node.py rx 3 --port COM4        # 6 tugunli variant uchun
   python flash_node.py rx 4 --port COM4
   ```

   Qo'shimcha sozlamalar: `--server-ip 192.168.4.2` (noutbuk manzili), `--hz 50` (tezlik), `--ssid`, `--password`, `--channel` (faqat tx). Har bir plata uchun alohida `firmware/build/rx0`, `build/rx1`... papkasi yaratiladi, shuning uchun sozlamalar aralashib ketmaydi.

4. Yozib bo'lgach monitor ochiladi (chiqish: `Ctrl+]`). Har bir platani darhol **stiker** bilan belgilang: "TX", "RX0", "RX1"...

Agar `Failed to connect to ESP32-S3` chiqsa: platadagi **BOOT** tugmasini bosib turing, **RST** ni bir marta bosing, BOOT ni qo'yib yuboring va buyruqni qaytaring.

## 5. Xonaga joylashtirish (5–6 RX)

```
   +---------------------------------------------------+
   | RX1 (burchak, 1 m)        RX2 (devor o'rtasi)  RX3 |
   |                                                   |
   |            [ yurish va yiqilish zonasi ]          |
   |                 matras shu yerda                  |
   |                                                   |
   | TX (burchak, 1.2 m)         RX4            RX0     |
   +---------------------------------------------------+
```

Qoidalar ([hardware.md](hardware.md) dagilarga qo'shimcha):

1. TX bitta burchakda, RX lar qolgan burchaklarda va uzun devorlarning o'rtasida. Har bir TX→RX chizig'i xonaning boshqa qismini kesib o'tsin.
2. RX lar odatda 1.0 m, TX 1.2 m balandlikda. `room_6nodes.yaml` dagidek 1–2 ta RX ni polga yaqin (0.4 m) qo'yish yerda yotgan odamni yaxshiroq ko'radi. Qaysi variantni tanlasangiz ham, **hamma xonalarda bir xil sxema** ishlating: shunda xonalar o'rtasidagi solishtirish adolatli bo'ladi.
3. Plata va devor orasida 10–20 cm bo'lsin, metall buyumlar (muzlatgich, radiator) yoniga qo'ymang.
4. Har bir plataning koordinatasini ruletka bilan o'lchang (xonaning chap pastki burchagi = 0, 0) va `configs/default.yaml` ga yozing:

   ```yaml
   nodes: [0, 1, 2, 3, 4]
   room:
     name: Yotoqxona
     size: [4.5, 3.6, 2.7]        # eni, chuqurligi, balandligi (m)
     tx: [0.2, 0.2, 1.2]
     rx:
       "0": [4.3, 0.2, 1.0]
       "1": [0.2, 3.4, 1.0]
       "2": [2.25, 3.4, 1.0]
       "3": [4.3, 3.4, 1.0]
       "4": [2.25, 0.2, 1.0]
   ```

5. Joylashuvni yuqoridan rasmga oling. Bu diplomdagi "tajriba sharoitlari" bo'limiga kiradi.

## 6. Ishlayotganini tekshirish (ketma-ketlik)

Har bir qadam o'tmaguncha keyingisiga o'tmang:

| # | Nima qilish | Kutilgan natija |
|---|---|---|
| 1 | Faqat TX ni yoqing, monitorni oching | `access point "WFG-NET" on channel 6 is up` |
| 2 | RX0 ni yoqing, monitorni oching | `connected to WFG-NET`, so'ng har 5 s da `CSI rate 99.x Hz` |
| 3 | Qolgan RX larni birma-bir yoqing | TX monitorida `N station(s) connected` soni ortib boradi |
| 4 | Noutbukni `WFG-NET` ga ulang (parol `wfg12345`), `wfg nodes` | Hamma tugun `ON`, ~100 Hz, `loss` 5% dan kam |
| 5 | Xonadan chiqing, 1 daqiqa kuting, keyin kirib yuring | `wfg serve` panelida holat "bo'sh"dan "yurish"ga o'zgaradi (model hali simulyatsiyada o'rgatilgan, shuning uchun bu bosqichda faqat signal o'zgarishiga qarang) |
| 6 | Matrasga sekin yiqilib, 30 s yoting | "yiqilish ehtimoli" ko'tariladi. Aniq ishlashi uchun model o'zingizning datasetingizda qayta o'rgatilishi kerak ([dataset_protocol.md](dataset_protocol.md)) |
| 7 | 1 m masofada 2 daqiqa tinch o'tiring, barmoqda pulsoksimetr | Nafas tezligi metronomga ±2/min ichida yaqin bo'lsa yaxshi. Yurak urishi tajribaviy, uni pulsoksimetr bilan solishtirib yozing |

Muammolar jadvali: [firmware/README.md](../firmware/README.md#muammolar).

## 7. GSM plata: ulash, proshivka, tekshirish

Server qo'ng'iroq qarorini qabul qilganda ([escalation.md](escalation.md)) `call_webhook` manziliga so'rov yuboradi. Qo'riqlash rejimida begona odam aniqlanganda ham (politsiya, 102) xuddi shu manzilga so'rov keladi: unda SMS "QO'RIQLASH, uyda begona odam!" bilan boshlanadi va qo'ng'iroq **Police number** sozlamasidagi raqamga (bo'sh bo'lsa serverdan kelgan 102 ga) ketadi. Bu plata uni qabul qilib: (1) qarindoshlarga SMS (sabab, yerda qancha vaqt, yurak/nafas, manzil) yuboradi, (2) raqamga qo'ng'iroq qiladi va liniyani 3 daqiqa ochiq ushlaydi. Internet ham, telefon ham kerak emas, faqat uydagi WiFi va GSM tarmoq.

### Ulash

```
 18650 (+) ──┬──────────────► SIM800L VCC      (3.7–4.2 V, 1000 µF kondensator VCC–GND ga)
 (TP4056 OUT)│
 18650 (−) ──┴──── GND ─────► SIM800L GND ─── ESP32-S3 GND   (umumiy GND shart!)

 ESP32-S3 GPIO17 ──[10 kΩ]──┬──► SIM800L RXD
                            └──[20 kΩ]── GND       (3.3 V -> ~2.2 V)
 ESP32-S3 GPIO18 ◄────────────── SIM800L TXD
 ESP32-S3 5V/USB ◄── 5 V adapter

 Ixtiyoriy ovoz:  SIM800L SPK+ / SPK− ── 8 Ω dinamik
                  SIM800L MIC+ / MIC− ── elektret mikrofon
```

- SIM800L ni **hech qachon** ESP32 ning 3V3 yoki to'g'ridan-to'g'ri 5V piniga ulamang: kuchlanish noto'g'ri, tok yetmaydi, modul qayta yuklanaveradi. ("SIM800L V2 / 5V" deb sotiladigan platalar 5 V qabul qiladi, ularda bo'luvchi ham bor.)
- A7670E/SIM7600 platalarining ko'pchiligi 5 V va 3.3 V mantiq bilan ishlaydi: rezistorlarsiz to'g'ridan-to'g'ri ulanadi, quvvatni modul tavsifidan tekshiring.
- SIM800L dagi chiroq: tez-tez (1 s) yonib-o'chsa tarmoq qidirmoqda, **3 s da bir** marta bo'lsa tarmoqqa ulangan.

### Proshivka

```bash
cd firmware/gsm_call
idf.py set-target esp32s3
idf.py menuconfig      # "WiFi Fall Guard GSM caller"
idf.py build flash monitor
```

`menuconfig` da: **Secret key** (o'zingizniki), **SMS recipients** (`+998901234567,+998931234567`), **Number to call** (yiqilish uchun, sinovda o'z raqamingiz), **Police number** (qo'riqlash uchun, sinovda ham o'z raqamingiz). **Allow calling emergency numbers** standart holatda **o'chiq**: sinov paytida 103 ga tasodifan qo'ng'iroq ketmaydi. Uni faqat hammasi sinalgandan keyin yoqing. Plata `192.168.4.30` manzilida ishlaydi (o'zgartirish mumkin).

Server sozlamasi (`configs/default.yaml`):

```yaml
escalation:
  call_webhook: http://192.168.4.30/call?key=SIZNING_KALIT
  address: "Toshkent, ... ko'chasi, ...-uy"
```

### Tekshirish

| # | Nima qilish | Kutilgan natija |
|---|---|---|
| 1 | Monitor | `modem ready`, keyin har 15 s da `network OK, signal 10..31/31`. `NOT REGISTERED` bo'lsa SIM karta, antenna yoki 2G qamrovini tekshiring |
| 2 | `curl http://192.168.4.30/status` | `{"registered":true,"signal":18,...}` |
| 3 | `curl -X POST "http://192.168.4.30/test?key=KALIT&to=%2B998901234567"` | O'z telefoningizga sinov SMS keladi |
| 4 | **Number to call** = o'z raqamingiz, keyin `curl -X POST "http://192.168.4.30/call?key=KALIT" -d '{"number":"103","reason":"sinov","address":"uy"}'` | SMS keladi, keyin o'z raqamingizga qo'ng'iroq (103 ga emas) |
| 5 | `wfg demo` da yiqilishni oxirigacha o'tkazing | Server webhook yuboradi, 4-qadamdagidek SMS va qo'ng'iroq |

## 8. Kamera plata (ixtiyoriy)

Kamera faqat so'ralganda bitta JPEG surat beradi (`/snapshot.jpg`). Doimiy video yo'q, platada hech narsa saqlanmaydi.

```bash
cd firmware/camera
idf.py set-target esp32s3
idf.py menuconfig      # "WiFi Fall Guard camera": plata turi va kalit
idf.py build flash monitor
```

Birinchi yig'ishda `esp32-camera` kutubxonasi internetdan avtomatik yuklanadi. Server sozlamasi:

```yaml
camera:
  snapshot_url: http://192.168.4.31/snapshot.jpg?key=SIZNING_KALIT
```

Tekshirish: brauzerda `http://192.168.4.31/snapshot.jpg?key=...` ni oching, rasm chiqishi kerak. `camera init failed` bo'lsa: kamera lentasi to'liq kirmagan yoki menuconfig dagi plata turi noto'g'ri.

## 9. Eskalatsiya va qurilma

Qaror mantiqi serverda ([escalation.md](escalation.md)). Qurilma tomoni uchun ikkita eslatma:

- Android telefon 103 ni faqat terib beradi, qo'ng'iroq tugmasini odam bosadi. To'liq avtomatik qo'ng'iroq faqat GSM plata bilan (7-bo'lim).
- WiFi CSI dan yurak urishini aniqlash hozircha **tajribaviy**. Shuning uchun "puls topilmadi" faqat o'zi tez yordam chaqirish uchun sabab bo'lmasligi kerak: avval yaqinlarga qo'ng'iroq va xabar, javob bo'lmasa 103. Noto'g'ri chaqiruvlar real tizimda katta muammo, buni diplomda ham alohida ko'rsating.
