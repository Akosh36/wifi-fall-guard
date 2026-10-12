# Diplom ishining yozma qismi: reja

**Mavzu:** WiFi CSI asosida turli xonalarga moslasha oladigan, keksalar uchun kamerasiz yiqilishni aniqlash tizimi

Taxminiy hajm: 60–80 bet. Har bir bob uchun repozitoriyda qaysi material tayyor ekani ko'rsatilgan.

## Kirish (3–4 bet)
- Mavzuning dolzarbligi: keksalar orasida yiqilish statistikasi (JSST), O'zbekistonda yolg'iz yashovchi keksalar.
- Mavjud yechimlar va ularning kamchiligi: kamera (maxfiylik), bilakuzuk (taqishni unutish, quvvatlash).
- Ishning maqsadi va vazifalari, ob'ekt va predmet, ilmiy yangiligi, amaliy ahamiyati.
- **Ilmiy yangilik:** arzon ESP32-S3 da mutlaqo yangi xonaga ko'chirish (cross-room) sinovi va kalibrlash usullarini solishtirish.

## 1-bob. Adabiyotlar tahlili (12–15 bet)
1.1. Yiqilishni aniqlash usullari: kamera, kiyiladigan sensorlar, radar, WiFi.
1.2. WiFi CSI asoslari: OFDM, subcarrier, ko'p yo'llilik, Doppler (`docs/architecture.md`, `wfg/csi/simulator.py` dagi formula).
1.3. WiFi orqali yiqilishni aniqlash ishlari: WiFall, RT-Fall, FallDeFi, DeFall, ENetFall, RuView. Jadval: qurilma, usul, aniqlik, yangi muhitdagi aniqlik.
1.4. Domain adaptation: MMD, CORAL, DANN, few-shot, KNN-MMD.
1.5. Xulosa: bo'shliq — ESP32 da yangi xona sinovi yo'q.

## 2-bob. Tizim arxitekturasi va loyihalash (12–15 bet)
2.1. Talablar (funksional va nofunksional: kechikish < 5 s, narx < $100, maxfiylik).
2.2. Umumiy arxitektura (`docs/architecture.md` sxemasi).
2.3. Qurilma qismi: ESP32-S3, TX/RX rejimi, joylashtirish (`docs/hardware.md`), narx jadvali.
2.4. Proshivka: CSI olish, paket formati (`firmware/`).
2.5. Signalni qayta ishlash: Hampel, Butterworth, nisbiy amplituda, PCA, Doppler spektrogrammasi (formulalar bilan).
2.6. Modellar: klassik asos, CNN-1D, CNN-2D, Transformer (sxemalar).
2.7. Xonaga moslashish usullari (formulalar: MMD, CORAL, DANN yo'qotish funksiyalari).
2.8. Hodisa mantiqi: holatlar diagrammasi (`wfg/inference/events.py`).
2.9. Dasturiy ta'minot: server, veb panel, Telegram bot.

## 3-bob. Tajriba va natijalar (15–20 bet)
3.1. Dataset: xonalar, ishtirokchilar, harakatlar, kliplar soni (`docs/dataset_protocol.md`).
3.2. Sinov metodikasi: bir xonada, leave-one-room-out, k-shot, metrikalar (`docs/experiments.md`).
3.3. Natijalar:
   - Jadval 1: bir xonadagi aniqlik (barcha modellar).
   - Jadval 2: yangi xonadagi aniqlik, k = 0, 1, 5 (barcha usullar).
   - Grafik: k ga qarab aniqlik o'zgarishi.
   - Chalkashlik matritsalari: qaysi harakatlar bir-biri bilan adashtiriladi.
   - Real vaqt sinovi: recall, kechikish, soatiga yolg'on signal.
3.4. WiFall va RuView natijalari bilan solishtirish.
3.5. Muhokama: nima uchun yangi xonada aniqlik tushadi, qaysi usul nima uchun yordam berdi.

## 4-bob. Iqtisodiy qism va hayot xavfsizligi (universitet talabiga qarab, 6–8 bet)
- Tannarx hisobi (`docs/hardware.md`), mavjud tijoriy yechimlar bilan solishtirish.
- Elektr xavfsizligi, radiochastota nurlanishi (ESP32 quvvati 20 dBm dan past).

## Xulosa (2–3 bet)
- Erishilgan natijalar raqamlarda.
- Cheklovlar: bitta odam, yoshlar taqlid qilgan yiqilishlar, bitta antenna.
- Kelajakdagi ishlar: TinyML (model ESP32 ichida), faza ma'lumoti, ko'p odam, mmWave radar bilan birlashtirish.

## Ilovalar
- Proshivka va asosiy kod parchalari, rozilik shakli namunasi, to'liq natija jadvallari.

## Himoya uchun
- 12–15 slaydli taqdimot.
- Jonli namoyish: `wfg serve --source udp`, xonada yurish, matrasga yiqilish, telefonga Telegram xabari kelishi.
- Zaxira: `wfg demo` (simulyator) internet yoki qurilma ishlamay qolsa.
