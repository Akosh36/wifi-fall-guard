# 4–6 tugunli qurilma rejasi: xarid, ulash, proshivka, joylashtirish, tekshirish

Bu hujjat [hardware.md](hardware.md) ning davomi: bitta xonada 4 tadan 6 tagacha ESP32-S3 platasi bilan ishlash bo'yicha amaliy qo'llanma.

## 1. Qaysi variant

| Variant | Platalar | Qachon |
|---|---|---|
| **Minimal (4)** | 1 TX + 3 RX | Birinchi sinov, dataset yozishni boshlash. Hozirgi `configs/default.yaml` shunga sozlangan |
| **Tavsiya (6)** | 1 TX + 5 RX | Asosiy tajribalar. Ko'proq RX = xonaning ko'proq qismi "ko'rinadi", zona aniqligi va yiqilishni aniqlash barqarorroq. Diplomda "3 RX va 5 RX ni solishtirish" alohida tajriba bo'la oladi |

Har doim **1 ta zaxira plata** oling: bittasi kuyishi yoki USB ulagichi sinishi mumkin.

Cheklovlar: `csi_tx` 8 tagacha ulanishni qabul qiladi (5 RX + noutbuk + telefon = 7, yetadi). 5 ta RX har biri 100 Hz da ishlasa, efirda sekundiga ~1000 ta kichik kadr bo'ladi. Bu ESP32-S3 uchun normal, lekin `wfg nodes` da tezlik 90 Hz dan tushib ketsa, barcha RX larni 50 Hz ga o'tkazing (`--hz 50`, pastga qarang) va `configs/default.yaml` dagi `fs` ni ham 50 qiling.

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
2. **Signalizatsiyadan keyin tasdiq (ixtiyoriy).** ESP32-S3 kamerali plata (OV2640 bilan, masalan ESP32-S3-EYE yoki "ESP32-S3 CAM" klonlari, $12–20) faqat yiqilish signalidan keyin bitta rasm olib yuboradi. Bu shaxsiy hayot daxlsizligi bilan bog'liq, shuning uchun diplomda "o'chirib qo'yiladigan qo'shimcha" deb ko'rsating. Uning proshivkasi hali yozilmagan.

### Ixtiyoriy: avtomatik qo'ng'iroq uchun GSM moduli

Avtomatik qo'ng'iroq uchun eng oddiy yo'l Android telefonning o'zi: qo'shimcha qurilma kerak emas. Agar telefonga bog'liq bo'lmaslik kerak bo'lsa: **SIM7600** yoki **A7670E** (4G LTE) moduli, $20–35, alohida SIM karta bilan. Arzon SIM800L faqat 2G da ishlaydi, operatoringizda 2G qo'llab-quvvatlanishini oldindan tekshiring.

### Jami

| | 4 tugun | 6 tugun |
|---|---|---|
| Platalar (zaxira bilan), kabel, adapter, shtativ | ~$85 | ~$125 |
| Matras, ruletka | ~$30 | ~$30 |
| Pulsoksimetr + MAX30102 | ~$20 | ~$20 |
| **Jami (kamera va GSM siz)** | **~$135** | **~$175** |

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

## 5. Xonaga joylashtirish (5 RX)

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
2. Hamma RX bir xil balandlikda (1.0 m ± 5 cm), TX 1.2 m. Bu xonalar o'rtasidagi solishtirishni adolatli qiladi.
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

## 7. Eskalatsiya (3 daqiqa, puls tekshiruvi, tez yordam) va qurilma

Bu asosan server va ilova mantiqi. Qurilma tomoni uchun ikkita eslatma:

- Qo'ng'iroqni Android telefon qilsa, qo'shimcha qurilma kerak emas. Telefonsiz ishlash kerak bo'lsa, 2-bo'limdagi GSM moduli.
- WiFi CSI dan yurak urishini aniqlash hozircha **tajribaviy**. Shuning uchun "puls topilmadi" faqat o'zi tez yordam chaqirish uchun sabab bo'lmasligi kerak: avval yaqinlarga qo'ng'iroq va xabar, javob bo'lmasa 103. Noto'g'ri chaqiruvlar real tizimda katta muammo, buni diplomda ham alohida ko'rsating.
