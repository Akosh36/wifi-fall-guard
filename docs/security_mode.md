# Qo'riqlash rejimi, joylashuv, nafas va yurak urishi

Bu hujjatda yiqilishni aniqlashdan tashqari qo'shilgan to'rtta imkoniyat tasvirlangan. Har birida u qanchalik ishonchli ekani ham yozilgan.

| Imkoniyat | Holati | Ishonchlilik |
|---|---|---|
| Qo'riqlash rejimi (uyda begona harakat) | Tayyor | Yuqori: WiFi CSI odam bor-yo'qligini yaxshi aniqlaydi |
| Ilovada uzluksiz ma'lumot va oflayn tarix | Tayyor | Dasturiy, ishonchli |
| Nafas soni | Tayyor | O'rtacha: faqat odam tinch tursa ishlaydi |
| Harakat joylashuvi (koordinata) | Eksperimental | Past: 3 ta plata bilan faqat zona darajasida |
| Yurak urishi | Eksperimental | Past: ESP32 bilan ishonchli emas, tadqiqot savoli |

## 1. Qo'riqlash rejimi

Uy egasi uydan chiqib ketganda rejimni yoqadi. Shundan keyin xonada **har qanday** odam paydo bo'lishi xavf deb hisoblanadi.

**Yoqish usullari:**

- ilovadagi 🛡 tugmasi;
- Telegram botda `/arm` buyrug'i (o'chirish uchun `/disarm`);
- API: `POST /api/security {"armed": true}`.

**Holatlar:**

1. **Yoqilmoqda** — 30 soniya uydan chiqish uchun beriladi (`security.exit_delay`).
2. **Qo'riqlanmoqda** — yashil rangda, "Uyda harakat yo'q" yozuvi chiqadi.
3. **XAVF: uyda harakat** — 1.5 soniya davomida odam aniqlansa, holat qizilga o'tadi. Ilovada signal chalinadi, telefonda to'liq ekranli bildirishnoma chiqadi va Telegramga xabar boradi.
4. 60 soniya xona bo'sh tursa, holat yana "Qo'riqlanmoqda"ga qaytadi. Keyingi harakat yana xavf signalini beradi.

Rejim holati serverda saqlanadi, shuning uchun server qayta ishga tushganda ham yoqilgan bo'lib qoladi.

**Telegram xavfsizligi:** botni topgan har kim `/start` yuborishi mumkin. Shuning uchun `configs/default.yaml` dagi `telegram.chat_ids` ga o'z chat ID'ingizni yozing. Ro'yxat to'ldirilgan bo'lsa, `/arm` va `/disarm` buyruqlarini faqat shu ID'lar ishlata oladi.

## 2. Uzluksiz ma'lumot va oflayn tarix

- Server har 0.5 soniyada holatni WebSocket (`/ws`) orqali yuboradi va uni SQLite bazasiga yozadi. Tarix 7 kun saqlanadi (`history_days`).
- Ilovadagi fon xizmati ilova yopiq bo'lsa ham shu oqimni qabul qiladi va har 5 soniyada telefonning o'z bazasiga yozadi. Telefonda tarix 30 kun saqlanadi.
- Aloqa uzilsa, ilova oxirgi ma'lumot vaqtini ko'rsatadi. **Tarix** (🕘) oynasida oldingi ma'lumotlar ko'rinaveradi: harakat grafigi, qizil oraliqlar va hodisalar ro'yxati.
- Aloqa tiklanganda ilova uzilish paytida server yozib qo'ygan ma'lumotlarni `GET /api/history?since=...` orqali yuklab oladi. Natijada telefondagi tarixda bo'shliq qolmaydi.

### Uydan tashqaridan ulanish

Uy egasi uyda bo'lmaganda telefon uy WiFi'sida bo'lmaydi. Ulanishning ikki yo'li bor:

1. **Tailscale (tavsiya etiladi).** Bepul, port ochish shart emas va trafik shifrlangan.
   - Kompyuterga (serverga) va telefonga Tailscale o'rnating va bitta akkauntga kiring.
   - Ilovada server manzili sifatida kompyuterning Tailscale IP'sini kiriting, masalan `http://100.x.y.z:8000`.
2. **Routerda port ochish.** Bu tavsiya etilmaydi: trafik shifrlanmaydi.

Har ikki holatda ham serverga token qo'ying: `WFG_TOKEN=uzun-maxfiy-so'z wfg serve --source udp`. Xuddi shu tokenni ilova sozlamalaridagi "Token" maydoniga kiriting. Tokensiz so'rovlar `401` javobini oladi.

Telegram bot internet orqali ishlaydi, shuning uchun alertlar har qanday holatda yetib boradi.

## 3. Harakat joylashuvi (eksperimental)

**Usul** (`wfg/inference/localize.py`):

- har bir TX→RX WiFi yo'lining so'nggi 1 soniyadagi harakat energiyasi o'lchanadi;
- odam qaysi yo'lga yaqin bo'lsa, o'sha yo'l kuchliroq buziladi (Fresnel zonasi modeli, `wfg/geometry.py`);
- xona poli 10 sm li to'rga bo'linadi va har nuqta uchun ehtimollik hisoblanadi;
- Bayes filtri vaqt bo'yicha kuzatib boradi: odam bir qadamda uzoqqa "sakray" olmaydi.

Natija `{x, y, r}` ko'rinishida chiqadi: koordinata metrda va noaniqlik radiusi. Ilovada bu polda ko'k doira va iz chizig'i bilan ko'rsatiladi.

**Halol baho (simulyatsiya):**

| Sharoit | O'rtacha xato |
|---|---|
| Ideal energiyalar (model aniq) | ~0.4 m |
| Simulyatsiya qilingan CSI, 3 ta RX | ~0.75 m |
| Doim xona markazini taxmin qilish (solishtirish uchun) | ~0.77 m |

Demak, 3 ta plata bilan 4×3.5 m xonada joylashuv amalda **zona darajasida**: "karavot tomonda" yoki "eshik tomonda". Simulyatsiyada 6 ta RX qo'yish ham natijani yaxshilamadi, chunki asosiy cheklov yo'llarning sezgirligini aniq bilmaslikda.

Aniq koordinata uchun ikki yo'l bor:

- har bir xonada **kalibrlash yurishi** qilish: belgilangan nuqtalarda turib, har yo'lning sezgirligini o'lchash;
- platalar orasida ko'proq yo'l hosil qilish: har bir ESP32 ham uzatadi, ham qabul qiladi, 4 plata bilan 6 ta yo'l.

Bu diplomda "kelgusi ish" yoki qo'shimcha tajriba bo'lishi mumkin.

> RuView haqida: u ham kamera emas, CSI bilan ishlaydi. Uning README'sida bitta ESP32 bilan jonli poza yoki joylashuv kuchsiz ekani yozilgan. Aniq koordinata uchun ko'p antenna yoki ko'p plata kerak.

## 4. Nafas va yurak urishi

**Usul** (`wfg/inference/vitals.py`):

- odam kamida 20 soniya tinch tursa (o'tirgan, yotgan yoki qimirlamayotgan), so'nggi 30 soniyalik CSI amplitudasi olinadi;
- signal nafas (0.1–0.6 Hz) va yurak (0.8–2.2 Hz) chastota oraliqlariga filtrlanadi;
- eng kuchli subtashuvchilar PCA bilan birlashtiriladi;
- spektrdagi eng baland cho'qqi tezlikni, uning medianaga nisbati esa sifatni beradi;
- sifat past bo'lsa, natija ko'rsatilmaydi ("—").

**Simulyatsiya natijasi:**

- **Nafas:** haqiqiy qiymatdan ±1 marta/daqiqa farq bilan topiladi.
- **Yurak urishi:** ko'krak qafasining yurak tufayli siljishi taxminan 0.3 mm. Bu ESP32 ning int8 o'lchov aniqligiga yaqin. Simulyatsiyada yurak urishi ba'zi xonalarda topildi, ba'zilarida topilmadi; sifat chegarasi noto'g'ri qiymatlarni ko'p hollarda yashiradi.

**Real sinov (diplom uchun):** yurak urishini barmoqqa taqiladigan pulsoksimetr yoki aqlli soat bilan bir vaqtda yozib solishtiring. Natijani MAE (o'rtacha absolyut xato) bilan bering. Agar xato katta chiqsa, bu ham ilmiy natija: "ESP32 amplituda bilan yurak urishini o'lchash chegarasi".

## API qisqacha

| So'rov | Vazifasi |
|---|---|
| `GET /api/status` | Joriy holat: `location`, `vitals`, `security` qo'shilgan |
| `GET /api/security`, `POST /api/security {"armed": bool}` | Qo'riqlash rejimi |
| `GET /api/history?since=<unix>&limit=` | Saqlangan tarix, eskisidan boshlab |
| `GET /api/events?since=&limit=` | Hodisalar: `fall_suspected`, `alert`, `intrusion`, `armed` va boshqalar |
| `?token=` yoki `Authorization: Bearer` | Server tokeni o'rnatilgan bo'lsa majburiy |
