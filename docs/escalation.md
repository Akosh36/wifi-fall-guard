# Yiqilishdan keyin: kuzatuv, qaror va tez yordam

Keksa odam yerga yotib, bir daqiqadan keyin o'zi turib ketishi mumkin. Har bunday holatda tez yordam chaqirish qo'pol xato bo'lardi. Shuning uchun server yiqilishni aniqlagani bilan darhol hech kimni chaqirmaydi. Har bir yiqilish **vaqt chizig'i** (timeline) bo'yicha boradi.

```
yiqilish ─► 3 daqiqa kuzatuv ─┬─ odam turdi ─────────────────────────► xavf bekor
                               │
                               ├─ turmadi + yurak/nafas ANOMAL ────────► 30 s sanoq ─► tez yordam (103)
                               │                                           (har kim bekor qila oladi)
                               │
                               └─ turmadi + yurak/nafas NORMAL ────────► egasidan so'rash:
                                  yoki o'lchab bo'lmadi                    "Tez yordam chaqirilsinmi?"
                                                                           Ha ─► 103 · Yo'q ─► kuzatuv
                                                                           10 daqiqa javob yo'q ─► 103
```

## 1. Kuzatuv (3 daqiqa)

- Yiqilish aniqlangach, ilova va Telegramga "Yiqilish aniqlandi" xabari boradi. Ilovada kuzatuv chizig'i chiqadi: `Kuzatuv: 1:12 / 3:00`.
- Shu vaqt ichida tizim odam turib yurishini kutadi va har 5 soniyada nafas hamda yurak urishini o'lchaydi.
- Odam turib yursa, holat yopiladi va tez yordam masalasi umuman ko'tarilmaydi.

## 2. Qaror

3 daqiqa o'tib odam hali ham yerda bo'lsa, o'lchovlar qaror qiladi.

| Holat | Nima bo'ladi |
|---|---|
| Yurak urishi 45–130/daq dan tashqarida yoki nafas 8–30/daq dan tashqarida (kamida 2 ta o'lchovda) | **XAVFLI.** 30 soniyalik sanoq boshlanadi, keyin tez yordam avtomatik chaqiriladi. Sanoq paytida ilovada yoki Telegramda "Bekor qilish" yoki "Hozir chaqirish" tugmasini bosish mumkin. |
| Yurak urishi va nafas normal | Egasiga savol boradi: **"Tez yordam (103) chaqirilsinmi?"** Ilovada, telefon bildirishnomasida va Telegramda "Ha, chaqiring" va "Kerak emas" tugmalari chiqadi. |
| Yurak urishini o'lchab bo'lmadi | Xuddi normal holatdagidek: qarorni odam qiladi. |

Savol paytida yurak urishi anomal bo'lib qolsa, tizim avtomatik sanoqqa o'tadi. Hech kim **10 daqiqa** javob bermasa, tez yordam chaqiriladi, chunki keksa odamning uzoq vaqt yerda yotishi o'zi xavfli.

### Nega "o'lchab bo'lmadi" hech qachon avtomatik chaqiruvga olib kelmaydi

ESP32 bilan yurak urishini o'lchash eksperimental ([security_mode.md](security_mode.md#4-nafas-va-yurak-urishi)). Ko'pincha natija chiqmaydi. Agar "natija yo'q" holati xavfli deb hisoblansa, tizim har yiqilishda tez yordam chaqirib yuborardi. Shuning uchun avtomatik chaqiruv faqat **aniq anomal raqam** bo'lganda, ishonchsiz holatda esa odam qaror qiladi.

## 3. Bir nechta tomondan ruxsat

Server tez yordamni chaqirishdan oldin bir necha tomonning "ovozini" hisobga oladi:

1. **Sensorlar.** Avtomatik qaror uchun kamida `min_nodes_online` ta plata onlayn bo'lishi kerak (standart 2 ta). Platalar kam bo'lsa, o'lchovga ishonib bo'lmaydi va savol odamga beriladi.
2. **Hayotiy ko'rsatkichlar.** Bitta g'alati o'lchov yetmaydi, kamida 2 tasi kerak (`min_abnormal`).
3. **Odamlar.** Normal holatda nechta "Ha" kerakligi `approvals_required` bilan belgilanadi. Masalan, `2` bo'lsa, siz va onangiz ikkalangiz rozilik berishingiz kerak. Bitta "Kerak emas" javobi holatni yopadi.

Kim qanday javob bergani vaqt chizig'ida yoziladi, masalan `15:30:53 Akosh: chaqirilsin`. Ilovadagi ism sozlamalardagi "Ismingiz" maydonidan olinadi.

Telegram'da buyruqlarni faqat `telegram.chat_ids` dagi odamlar bera oladi. Ro'yxat bo'sh bo'lsa, botga obuna bo'lgan har kim bera oladi.

## 4. Tez yordam qanday chaqiriladi

Tez yordam chaqirish qaroriga kelinganda quyidagilar bo'ladi:

- Telegram'dagi hammaga xabar boradi: `🚑 TEZ YORDAM CHAQIRILDI (103)`, sabab va manzil bilan.
- Telefonda to'liq ekranli bildirishnoma chiqadi, unda "Qo'ng'iroq qilish 103" tugmasi bo'ladi.
- Sozlamalarda **"telefondan o'zi qo'ng'iroq qilsin"** yoqilgan bo'lsa, telefon qulflangan bo'lsa ham ekran yonadi va raqam teriladi.
- `call_webhook` sozlangan bo'lsa, server shu manzilga JSON yuboradi (pastda).

> **Muhim cheklov.** Android oddiy ilovalarga favqulodda raqamlarga (103, 112) o'zi qo'ng'iroq qilishga ruxsat bermaydi. Bunday raqamda telefon terish oynasi 103 yozilgan holda ochiladi va bitta tugmani bosish kerak bo'ladi. Oddiy raqamga, masalan qarindoshning raqamiga, qo'ng'iroq to'liq avtomatik ketadi. Odam aralashuvisiz 103 ga qo'ng'iroq qilish uchun alohida LTE modul kerak, pastdagi "Kelgusi ish" bo'limiga qarang.

### `call_webhook`

Tez yordam chaqirish qarori qabul qilinganda server bu manzilga `POST` so'rov yuboradi:

```json
{"type": "emergency_call", "t": 1760370653.1, "by": "avtomatik", "number": "103",
 "address": "Toshkent, ...", "reason": "yurak urishi anomal (148/daq)", "down_min": 3.5,
 "vitals": "yurak 148/daq, nafas 14/daq"}
```

Shu orqali SMS-shlyuz, SIP-telefoniya yoki LTE modul ulanadi. SIM800L tavsiya etilmaydi: u faqat 2G tarmoqda ishlaydi, 2G esa yopilib bormoqda.

## 5. Qo'shimcha kamera (ixtiyoriy)

Asosiy tizim kamerasiz ishlaydi. Xohlovchilar uchun IP kamera ulash mumkin:

```yaml
camera:
  snapshot_url: http://192.168.1.20/snapshot.jpg   # kameraning JPEG surat manzili
```

- Kamera **doimiy yozib olinmaydi**. Surat faqat yiqilish holatida, qaror bosqichlarida olinadi: savol, sanoq va chaqiruvda bittadan.
- Surat Telegramga yuboriladi va ilovadagi qizil oynada ko'rinadi (`GET /api/escalation/snapshot`). Shunda egasi "Chaqirilsinmi?" degan savolga ko'rib javob bera oladi.
- Ko'p arzon IP kameralar va ESP32-CAM (`/capture`) shunday JPEG manzilni beradi.

Maxfiylik uchun kamerani faqat yotoqxona yoki koridor kabi joylarga qo'yish va hammomga qo'ymaslik tavsiya etiladi.

## 6. 4–6 ta plata

Ko'proq plata qo'yilsa, xonani kesib o'tadigan WiFi yo'llari ko'payadi. Bu ikki foyda beradi:

- yiqilishni ko'rmaydigan "ko'r joylar" kamayadi;
- bitta plataning batareyasi tugasa yoki u o'chib qolsa, aniqlash qolganlari bilan davom etadi. Server endi o'chgan platani kutib turmaydi.

Misol sozlama: [`configs/room_6nodes.yaml`](../configs/room_6nodes.yaml). 5 ta plata bo'lsa, `nodes: [0, 1, 2, 3, 4]` qoldiring va `room.rx` dan `"5"` ni o'chiring: `nodes` dagi raqamlar va `rx` kalitlari platalardagi `CONFIG_WFG_NODE_ID` bilan bir xil bo'lishi kerak. Ishga tushirish: `wfg serve --config configs/room_6nodes.yaml`. Har bir `csi_rx` platasiga o'z `CONFIG_WFG_NODE_ID` (0..5) yoziladi ([hardware.md](hardware.md)).

**Paket tezligi:** ko'p plata bitta TX dan CSI olganda haqiqiy tezlik 100 Hz dan tushib ketishi mumkin. `wfg nodes` har plata tezligini ko'rsatadi. Tezlik 90 Hz dan past bo'lsa, platalarni 50 Hz ga o'tkazing va sozlamada `fs: 50` qo'ying. Aks holda server oynalarni noto'g'ri vaqt bo'yicha yig'adi.

**Halol baho:** simulyatsiyada 6 ta plata joylashuv aniqligini sezilarli oshirmadi ([security_mode.md](security_mode.md#3-harakat-joylashuvi-eksperimental)). Ularning yiqilishni aniqlashga foydasini real platalarda o'lchash kerak; bu diplom uchun yaxshi tajriba (3 plata va 6 plata).

## Sozlamalar

`configs/default.yaml`, `escalation` bo'limi:

| Kalit | Standart | Ma'nosi |
|---|---|---|
| `observe_seconds` | 180 | Yiqilishdan keyin kuzatuv vaqti |
| `heart_low`, `heart_high` | 45, 130 | Normal yurak urishi chegarasi (/daq) |
| `breath_low`, `breath_high` | 8, 30 | Normal nafas chegarasi (/daq) |
| `min_abnormal` | 2 | Qaror uchun kerakli anomal o'lchovlar soni |
| `auto_call` | true | `false`: har doim odamdan so'raladi |
| `cancel_seconds` | 30 | Avtomatik chaqiruvdan oldingi sanoq |
| `approvals_required` | 1 | Normal holatda kerakli "Ha" javoblari |
| `no_answer_seconds` | 600 | Javob bo'lmasa chaqirish (`0` = hech qachon) |
| `min_nodes_online` | 2 | Avtomatik qaror uchun kerakli onlayn platalar |
| `number` | "103" | Tez yordam raqami |
| `address` | "" | Uy manzili, xabarga qo'shiladi |
| `call_webhook` | "" | Chaqiruv uchun tashqi xizmat manzili |

`wfg demo` buyrug'ida kuzatuv 25 soniyaga qisqartiriladi, ilovadagi demo rejimida esa 20 soniyaga. Shunda butun jarayonni bir necha daqiqada ko'rsatish mumkin. Demo rejimidagi yiqilishlar navbat bilan keladi: biri normal yurak urishi bilan (savol), keyingisi anomal yurak urishi bilan (avtomatik sanoq).

## API

| So'rov | Vazifasi |
|---|---|
| `GET /api/escalation` | Joriy holat: `state` (`idle`, `observing`, `asking`, `countdown`, `called`), `timeline`, `answers`, `reason` |
| `POST /api/escalation {"call": true, "who": "Akosh"}` | Javob: `true` bo'lsa chaqirilsin, `false` bo'lsa kerak emas |
| `GET /api/escalation/snapshot` | Oxirgi kamera surati (kamera ulangan bo'lsa) |
| `POST /api/ack` | "Hammasi joyida": ochiq holatni yopadi |
| Telegram `/call`, `/cancel` va xabar ostidagi tugmalar | Xuddi shu javoblar |

Hodisalar (`/api/events`): `ask_owner`, `emergency`, `emergency_call`, `emergency_cancelled`, `resolved`.

## Kelgusi ish (diplom uchun g'oyalar)

- **LTE modul (SIM7600 yoki A7670E):** ESP32 ga ulanadi va `call_webhook` dan buyruq olib, 103 ga yoki qarindoshga o'zi qo'ng'iroq qiladi hamda SMS yuboradi. Bu tizimni telefonga va internetga bog'liq bo'lmagan qiladi.
- Yurak urishi o'lchovini pulsoksimetr bilan solishtirib, `heart_low` va `heart_high` chegaralarini real ma'lumot bo'yicha tanlash.
- Kuzatuv vaqtini (3 daqiqa) odamning yoshi va kasalliklariga qarab sozlash.

Kod: [`wfg/inference/escalation.py`](../wfg/inference/escalation.py). Testlar: [`tests/test_escalation.py`](../tests/test_escalation.py).
