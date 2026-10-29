# O'rnatish yo'riqnomasi: qurilmalardan ishlaydigan tizimgacha

Bu hujjat tizimni noldan, haqiqiy ESP32-S3 platalari bilan ishga tushirish tartibini ketma-ket beradi. Har bir bosqich oxirida **"Tekshiruv"** bor: u o'tmaguncha keyingi bosqichga o'tmang.

> **Avval bilib qo'ying.** Proshivka va Android ilova hozircha faqat CI'da yig'ilgan, haqiqiy platada va telefonda hali sinalmagan. Birinchi ishga tushirishda kichik muammolar chiqishi tabiiy. Har bir bosqichdagi tekshiruv ularni erta topish uchun. `results/simulated/` dagi raqamlar simulyator natijasi, real aniqlik 9-bosqichdan keyin ma'lum bo'ladi.

## Umumiy ko'rinish

```
                    Uy routeri (internet)
                     │ Ethernet          │ Wi-Fi
                     ▼                   ▼
  ┌──────────────────────────┐      Telefon (FallGuard ilova)
  │ Server: Raspberry Pi 5   │
  │ yoki noutbuk             │◄── Wi-Fi "WFG-NET" ──┐
  │ wfg serve --source udp   │   (192.168.4.200)    │
  └──────────────────────────┘                      │
                                     ESP32-S3 TX (access point, 192.168.4.1)
                                          │ 100 Hz ping
                              ┌───────────┼───────────┐
                            RX0          RX1         RX2   ── CSI, UDP 5500 → server
```

Server ikki tarmoqqa bir vaqtda ulanadi: Wi-Fi orqali platalar tarmog'i `WFG-NET` ga (CSI olish uchun), Ethernet orqali uy routeriga (internet, Telegram va telefon uchun). `WFG-NET` da internet yo'q, shuning uchun ikkinchi ulanish shart.

| Bosqich | Nima qilinadi | Taxminiy vaqt |
|---|---|---|
| 1 | Qismlarni sotib olish | 2–4 hafta (yetkazib berish) |
| 2 | Kompyuterni tayyorlash (ESP-IDF, Python) | 1–2 soat |
| 3 | TX platani proshivka qilish | 15 daqiqa |
| 4 | RX platalarni proshivka qilish | 30 daqiqa |
| 5 | Serverni tayyorlash va tarmoq | 1 soat |
| 6 | Platalarni xonaga joylashtirish | 30 daqiqa |
| 7 | Signal kelayotganini tekshirish | 15 daqiqa |
| 8 | Xona o'lchamlari va sozlamalar | 30 daqiqa |
| 9 | Dataset yozish va modelni o'qitish | 1–2 kun |
| 10 | Telegram bot | 15 daqiqa |
| 11 | Android ilova | 15 daqiqa |
| 12 | Doimiy ishlash (avtomatik ishga tushish) | 30 daqiqa |
| 13 | To'liq sinov | 1 soat |

---

## 1. Qismlarni sotib olish

Minimal to'plam (1 xona, 3 ta qabul qiluvchi):

| Qism | Soni | Taxminiy narx |
|---|---|---|
| ESP32-S3-DevKitC-1U (N8R8 yoki N16R8) | 4 (1 TX + 3 RX) | ~$10 dona |
| 2.4 GHz IPEX antenna, 3 dBi | 4 | ~$2 dona |
| USB-C kabel (ma'lumot uzatadigan, faqat zaryad emas) | 4 | ~$2 dona |
| 5V / 1A USB adapter | 4 | ~$2 dona |
| Kichik shtativ yoki taglik (platani ~1 m balandlikda ushlash uchun) | 4 | ~$7 dona |
| Sport matrasi (yiqilishlarni xavfsiz yozish uchun) | 1 | ~$30 |
| Raspberry Pi 5 (4 GB) + quvvat bloki + 32 GB microSD (ixtiyoriy, noutbuk ham bo'ladi) | 1 | ~$90 |

Jami: Raspberry Pi'siz taxminan $85, bilan taxminan $175–290. Batafsil ro'yxat va variantlar: [hardware.md](hardware.md).

Maslahatlar:

- **"1U"** varianti tashqi antenna uchun ulagichga ega va signal barqarorroq. Oddiy "1" variant ham ishlaydi.
- Bitta ortiqcha plata oling (5 ta). Proshivka paytida bittasi buzilsa, ish to'xtab qolmaydi.
- Noutbuk server bo'lsa, unga **Ethernet porti** yoki ikkinchi USB Wi-Fi adapter kerak (pastda 5-bosqich).

**Tekshiruv:** har bir platani kompyuterga ulang. Platada LED yonadi, kompyuter yangi port ko'radi (Windows'da "Qurilmalar dispetcheri" → "Porty (COM)", Linux'da `ls /dev/ttyACM* /dev/ttyUSB*`). Port ko'rinmasa, kabelni almashtiring: ko'p kabellar faqat zaryad uchun.

## 2. Kompyuterni tayyorlash

Proshivka qilish uchun kompyuter (Windows, Linux yoki macOS) kerak. Bu server bilan bir xil kompyuter bo'lishi shart emas.

1. **ESP-IDF v5.3** ni o'rnating:
   - Windows: [ESP-IDF Tools Installer](https://dl.espressif.com/dl/esp-idf/) dan v5.3.x ni yuklab oling va o'rnating. O'rnatilgach "ESP-IDF 5.3 CMD" yorlig'i paydo bo'ladi, hamma `idf.py` buyruqlarini o'sha oynada yozing.
   - Linux / macOS: [rasmiy yo'riqnoma](https://docs.espressif.com/projects/esp-idf/en/v5.3/esp32s3/get-started/linux-macos-setup.html) bo'yicha, keyin har yangi terminalda `. ~/esp/esp-idf/export.sh`.
2. **Git** va **Python 3.10+** o'rnating.
3. Repozitoriyni yuklab oling:
   ```bash
   git clone https://github.com/Akosh36/wifi-fall-guard
   cd wifi-fall-guard
   ```

**Tekshiruv:** `idf.py --version` buyrug'i `ESP-IDF v5.3...` ni ko'rsatadi.

## 3. TX (uzatuvchi) platani proshivka qilish

TX plata `WFG-NET` nomli Wi-Fi tarmog'ini ochadi (parol `wfg12345`, 6-kanal). Faqat bitta TX kerak.

1. Platani USB orqali ulang. Platada ikkita USB-C bo'lsa, **"UART"** yozilganiga ulang.
2. Portni bilib oling (masalan Windows'da `COM5`, Linux'da `/dev/ttyACM0`).
3. Proshivka qiling:
   ```bash
   cd firmware/csi_tx
   idf.py set-target esp32s3
   idf.py -p COM5 build flash monitor
   ```
   Proshivka boshlanmasa: platadagi **BOOT** tugmasini bosib turing, **RST** ni bir marta bosing, BOOT ni qo'yib yuboring va buyruqni qayta yozing.
4. Monitordan `Ctrl+]` bilan chiqing.
5. Platani qog'ozga **"TX"** deb belgilab qo'ying.

Tarmoq nomi yoki parolini o'zgartirmoqchi bo'lsangiz, `idf.py menuconfig` → "WiFi Fall Guard transmitter". Unda RX platalarda ham xuddi shu nom va parolni yozing.

**Tekshiruv:** monitorda `access point "WFG-NET" on channel 6 is up` yozuvi chiqadi. Telefonning Wi-Fi ro'yxatida `WFG-NET` ko'rinadi.

## 4. RX (qabul qiluvchi) platalarni proshivka qilish

Har bir RX platani **alohida** proshivka qiling, faqat `Node id` har birida boshqacha bo'ladi: 0, 1, 2.

1. Birinchi RX platani ulang va sozlamalarni oching:
   ```bash
   cd firmware/csi_rx
   idf.py set-target esp32s3
   idf.py menuconfig
   ```
2. "WiFi Fall Guard receiver" bo'limida:
   - **WiFi SSID**: `WFG-NET` (o'zgartirmang)
   - **WiFi password**: `wfg12345`
   - **Server IP**: `192.168.4.200` (5-bosqichda serverga shu manzil qo'yiladi)
   - **Server UDP port**: `5500`
   - **Node id**: `0` (keyingi platalarda 1, 2)
   - **CSI sampling rate**: `100`

   `S` bilan saqlang, `Q` bilan chiqing.
3. Proshivka qiling va monitorni ko'ring:
   ```bash
   idf.py -p COM6 build flash monitor
   ```
4. Platani **"RX0"** deb belgilang.
5. Keyingi platani ulang, `menuconfig` da faqat **Node id** ni `1` ga o'zgartiring, yana `build flash`, belgilang **"RX1"**. Keyin `2` va **"RX2"**.

Nega `192.168.4.200`: TX plata ulangan qurilmalarga avtomatik ravishda `192.168.4.2` dan boshlab manzil beradi. Platalar serverdan oldin yoqilsa, `.2` manzil platalardan biriga tushib qolishi mumkin. `.200` bu ro'yxatdan tashqarida, shuning uchun server har doim shu manzilda bo'ladi.

**Tekshiruv** (TX plata yoqilgan holda): RX monitorida ketma-ket chiqadi:
```
connected to WFG-NET, BSSID ..., channel 6
pinging gateway 192.168.4.1 at 100 Hz
node 0 sending CSI to 192.168.4.200:5500
```
Agar `disconnected, reconnecting` takrorlansa, SSID/parol noto'g'ri yoki TX o'chiq.

## 5. Serverni tayyorlash va tarmoq

Server Raspberry Pi 5 (tavsiya, kecha-kunduz ishlaydi) yoki noutbuk bo'lishi mumkin.

### 5.1. Dasturni o'rnatish

Raspberry Pi'ga **Raspberry Pi OS (64-bit)** yozing ([Raspberry Pi Imager](https://www.raspberrypi.com/software/)), keyin:

```bash
sudo apt update && sudo apt install -y git python3-venv
git clone https://github.com/Akosh36/wifi-fall-guard
cd wifi-fall-guard
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

Ishlashini simulyator bilan tekshiring: `wfg demo`, brauzerda `http://localhost:8000`. Ko'rib bo'lgach `Ctrl+C`.

### 5.2. Ikki tarmoqqa ulash

1. **Ethernet** kabel bilan serverni uy routeriga ulang. Bu internet va telefon uchun.
2. **Wi-Fi** orqali serverni `WFG-NET` ga ulang va unga **qo'lda (statik) manzil** bering:
   - IP: `192.168.4.200`
   - Maska: `255.255.255.0`
   - Shlyuz (gateway): **bo'sh qoldiring** (aks holda internet `WFG-NET` orqali qidiriladi va Telegram ishlamaydi)

   Raspberry Pi / Linux (NetworkManager):
   ```bash
   sudo nmcli dev wifi connect WFG-NET password wfg12345 name wfg
   sudo nmcli con mod wfg ipv4.method manual ipv4.addresses 192.168.4.200/24 ipv4.gateway "" ipv4.never-default yes
   sudo nmcli con up wfg
   ```
   Windows: "Tarmoq va Internet" → `WFG-NET` → "Xususiyatlar" → "IP tayinlash" → "Qo'lda" → IPv4: IP `192.168.4.200`, maska `255.255.255.0`, shlyuz bo'sh.
3. Noutbukda Ethernet bo'lmasa: ikkinchi USB Wi-Fi adapter oling (biri `WFG-NET` ga, ikkinchisi uy Wi-Fi'siga). Yoki [hardware.md](hardware.md) dagi "uy routeri rejimi"ni ishlating: TX'siz, RX platalarni to'g'ridan-to'g'ri uy routeriga ulab (`menuconfig` da routerning SSID va paroli, Server IP = serverning uy tarmog'idagi manzili).
4. **Windows firewall**: birinchi `wfg` ishga tushganda "Ruxsat berish" oynasi chiqadi, "Xususiy tarmoqlar"ga ruxsat bering. Chiqmasa, UDP 5500 va TCP 8000 portlarini qo'lda oching.
5. Uy routeri 2.4 GHz da **6-kanalda** ishlasa, routerni 1- yoki 11-kanalga o'tkazing: TX bilan bir kanal CSI ni shovqinli qiladi.

**Tekshiruv:**
- `ping 8.8.8.8` ishlaydi (internet bor);
- `ping 192.168.4.1` ishlaydi (TX ko'rinadi);
- serverning uy tarmog'idagi manzilini yozib oling (`ip a` yoki `ipconfig`, masalan `192.168.1.50`). U 11-bosqichda telefon uchun kerak. Routerda bu manzilni "DHCP reservation" bilan serverga bog'lab qo'ying, shunda u o'zgarmaydi.

## 6. Platalarni xonaga joylashtirish

```
   +-----------------------------------------+
   |  RX0 (burchakda, 1 m)        RX1        |
   |                                         |
   |              [ yurish va                |
   |                yiqilish zonasi ]        |
   |                                         |
   |  TX (qarama-qarshi devor, 1.2 m)   RX2  |
   +-----------------------------------------+
```

1. TX ni bir devor yoniga, RX larni **turli burchaklarga** qo'ying. Odam yuradigan va yiqilishi mumkin bo'lgan joy TX va RX lar orasida bo'lsin.
2. Hamma platalar taxminan **1 m** balandlikda (TX 1–1.2 m), shtativ yoki javon ustida. Polga qo'ymang.
3. Platalar orasidagi masofa **2–5 m**. Bir-biriga 0.5 m dan yaqin bo'lmasin.
4. Antennani tik qo'ying, metall buyum (muzlatgich, temir shkaf) orqasiga yashirmang.
5. Har bir platani doimiy 5V adapterga ulang. Powerbank bir necha soatdan keyin o'chib qoladi.
6. Joylashuvni **rasmga oling** va har bir plataning xona burchagidan masofasini metrda o'lchab yozing (8-bosqichda kerak).

## 7. Signal kelayotganini tekshirish

Hamma platalar yoqilgan, server `WFG-NET` ga ulangan holda:

```bash
source .venv/bin/activate
wfg nodes
```

Kutiladigan natija:
```
#0: ON  99.8 Hz loss 0.2% rssi -41   #1: ON 100.1 Hz loss 0.1% rssi -45   #2: ON 99.6 Hz loss 0.4% rssi -50
```

**Tekshiruv:** har bir plata **ON**, taxminan **100 Hz**, `loss` 5% dan kam, `rssi` −30 dan −70 gacha. Xonada qo'l silkitsangiz, raqamlar o'zgarmaydi, bu normal: bu buyruq faqat paket oqimini tekshiradi.

| Muammo | Yechim |
|---|---|
| Hech qaysi plata ko'rinmaydi | Serverning `WFG-NET` dagi IP'si `192.168.4.200` ekanini tekshiring; firewall UDP 5500 ni yopmaganini tekshiring |
| Bitta plata yo'q | Shu platani kompyuterga ulab `idf.py -p COMx monitor` bilan qarang. Node id takrorlanmaganini tekshiring |
| Rate 100 Hz dan ancha past | Plata TX dan uzoq yoki orasida qalin devor. Yaqinroq qo'ying |
| `loss` 5% dan yuqori | Antenna ulanganini tekshiring, uy routerini boshqa kanalga o'tkazing |

## 8. Xona o'lchamlari va sozlamalar

`configs/default.yaml` ni nusxalang va o'z xonangizga moslang:

```bash
cp configs/default.yaml configs/uy.yaml
```

`configs/uy.yaml` da:

```yaml
source: udp
nodes: [0, 1, 2]              # RX platalarning Node id lari

room:
  name: Yotoqxona
  size: [4.0, 3.5, 2.7]       # eni, bo'yi, balandligi (m)
  tx: [0.3, 0.3, 1.2]         # TX ning joyi: burchakdan x, y va balandlik
  rx:
    "0": [3.7, 0.4, 1.0]      # 6-bosqichda o'lchangan joylar
    "1": [3.7, 3.1, 1.0]
    "2": [0.3, 3.1, 1.0]
  furniture:
    - {kind: bed, pos: [3.0, 2.4], size: [1.0, 2.0], rot: 0}

escalation:
  address: "Toshkent sh., ... ko'chasi, 12-uy"   # tez yordam xabariga qo'shiladi
  number: "+998901234567"     # SINOV PAYTIDA o'z yoki yaqiningiz raqami! 103 emas
police:
  number: "+998901234567"     # sinov paytida 102 emas
```

> **Muhim:** sinovlar tugaguncha `escalation.number` va `police.number` ga **haqiqiy 103 / 102 ni yozmang**. Matrasga yiqilish sinovlarida tizim chaqiruv qarorini chiqaradi. Tizim ishonchli ekaniga ishonch hosil qilgandan keyingina 103 va 102 ni qaytaring.

4–6 ta plata uchun namuna: `configs/room_6nodes.yaml`. Qolgan sozlamalar (yiqilish chegarasi, kuzatuv vaqti, qo'riqlash) fayl ichida izohlangan, batafsil: [escalation.md](escalation.md), [security_mode.md](security_mode.md).

## 9. Dataset yozish va modelni o'qitish

Birinchi ishga tushishda server o'zi yaratadigan model (`models/classic_sim.npz`) faqat **simulyatsiya** ma'lumotida o'qitilgan. Haqiqiy xonada u yaxshi ishlamaydi, shuning uchun o'z xonangizda ma'lumot yozib, modelni qayta o'qitish kerak.

1. Matrasni yiqilish zonasiga qo'ying. Xonada faqat sinov qatnashchisi bo'lsin, ventilyator va konditsioner o'chiq.
2. Yozing (har bir harakatdan 10 takror, taxminan 45 daqiqa):
   ```bash
   wfg record --room xona1 --subject s01 --protocol configs/protocol.yaml \
              --notes "4x3.5 m, g'isht devor, RX0 shkaf ustida"
   ```
   Dastur har takrordan oldin nima qilishni aytadi, 3-2-1 sanaydi va 5 soniya yozadi. Klip natijasi: `data/raw/xona1/s01/...`.
3. Kamida 2–3 kishi bilan takrorlang (`--subject s02`, `s03`). Diplom tajribasi uchun 3 xona kerak: [dataset_protocol.md](dataset_protocol.md).
4. Modelni o'qiting:
   ```bash
   wfg train --data data/raw --arch classic --out models/uy
   ```
   Natija: `models/uy.npz`. Kuchliroq model (CNN) uchun `pip install -e ".[ml]"` va `--arch cnn1d` (fayl `models/uy.pt` bo'ladi). Raspberry Pi'da CNN sekin o'qitiladi, uni noutbukda o'qitib, faylni Pi'ga ko'chiring.

**Tekshiruv:** serverni yangi model bilan ishga tushiring:
```bash
wfg serve --config configs/uy.yaml --source udp --model models/uy.npz
```
Brauzerda `http://localhost:8000` ni oching. Xonada yuring, o'tiring, yoting: ko'rsatilgan holat sizning harakatingizga mos kelishi kerak. Mos kelmasa, ko'proq klip yozing.

## 10. Telegram bot

1. Telegramda **@BotFather** ga yozing: `/newbot`, botga nom bering. U token beradi, masalan `123456:ABC-DEF...`.
2. O'z chat ID'ingizni biling: **@userinfobot** ga `/start` yozing, u `Id: 987654321` ni ko'rsatadi. Buyruqlarni (`/arm`, `/call` va h.k.) faqat shu ID egalari bera oladi.
3. Serverni token bilan ishga tushiring:
   ```bash
   export WFG_TELEGRAM_TOKEN=123456:ABC-DEF...
   export WFG_TELEGRAM_CHAT_IDS=987654321          # bir nechta bo'lsa vergul bilan
   wfg serve --config configs/uy.yaml --source udp --model models/uy.npz
   ```
   Windows'da `export` o'rniga `set`.
4. Botingizni toping va `/start` yozing. Yaqinlaringiz ham botga `/start` yozadi.

**Tekshiruv:** bot "Siz ogohlantirishlarga obuna bo'ldingiz" deb javob beradi, `/status` buyrug'i xona holatini qaytaradi.

## 11. Android ilova

1. Telefonda oching: https://github.com/Akosh36/wifi-fall-guard/releases/tag/android-latest va `FallGuard.apk` ni yuklab oling.
2. Faylni oching. "Noma'lum manbadan o'rnatish"ga ruxsat bering.
3. Ilovani oching va **bildirishnomalarga ruxsat bering**. Ruxsatsiz fon alerti ishlamaydi.
4. Telefon **uy Wi-Fi'siga** ulangan bo'lsin (`WFG-NET` ga emas).
5. ⚙ tugmasi → "Server manzili": `http://192.168.1.50:8000` (5-bosqichda yozib olingan manzil) → "Saqlash". Serverga token qo'ygan bo'lsangiz (`WFG_TOKEN`), uni "Token" maydoniga yozing. "Ismingiz" ga ismingizni yozing.
6. Telefon sozlamalarida FallGuard uchun **batareya tejashni o'chiring** ("Cheklanmagan" / "Optimallashtirmaslik"). Aks holda telefon ilovani fonda to'xtatib qo'yishi mumkin.

**Tekshiruv:** yuqori qator yashil, 3D xonada sizning xonangiz va platalar ko'rinadi. Platalar soni pastki qatorda to'g'ri ko'rsatiladi. Uydan tashqarida ham ishlashi kerak bo'lsa: [security_mode.md](security_mode.md#uydan-tashqaridan-ulanish) (Tailscale).

## 12. Doimiy ishlash

Server kompyuter qayta yoqilganda o'zi ishga tushishi uchun Raspberry Pi'da systemd xizmati yarating:

```bash
sudo tee /etc/systemd/system/wfg.service >/dev/null <<EOF
[Unit]
Description=WiFi Fall Guard
After=network-online.target
Wants=network-online.target

[Service]
User=$USER
WorkingDirectory=$HOME/wifi-fall-guard
Environment=WFG_TELEGRAM_TOKEN=123456:ABC-DEF...
Environment=WFG_TELEGRAM_CHAT_IDS=987654321
Environment=WFG_TOKEN=uzun-maxfiy-soz
ExecStart=$HOME/wifi-fall-guard/.venv/bin/wfg serve --config configs/uy.yaml --source udp --model models/uy.npz
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl daemon-reload
sudo systemctl enable --now wfg
```

Holatni ko'rish: `systemctl status wfg`, jurnal: `journalctl -u wfg -f`.

Tavsiyalar:

- Server, TX va RX platalarni **UPS** yoki uzilmaydigan rozetkaga ulang. Svet o'chsa tizim ishlamaydi.
- Platalar svet qaytgach o'zi `WFG-NET` ga qayta ulanadi, buning uchun hech narsa qilish kerak emas.

**Tekshiruv:** `sudo reboot` qiling. 2 daqiqadan keyin telefondagi ilova yana yashil bo'ladi va `/status` javob beradi.

## 13. To'liq sinov

Har bir sinovni bajaring va natijani yozib boring (diplomdagi "Sinovlar" bo'limi uchun):

| # | Sinov | Kutiladigan natija |
|---|---|---|
| 1 | Xonadan chiqing | Holat "Xona bo'sh" |
| 2 | Kiring, yuring, stulga o'tiring, karavotga yoting | Har bir harakat to'g'ri ko'rsatiladi, alert yo'q |
| 3 | Matrasga yiqiling va turing | "Yiqilish" signali, turib yurgach bekor qilinadi |
| 4 | Matrasga yiqiling va 20 s qimirlamang | Telefonda to'liq ekranli **XAVF** alarmi, Telegramga xabar, 3 daqiqalik kuzatuv boshlanadi |
| 5 | 4-sinovdan keyin 3 daqiqa kuting | "Tez yordam chaqirilsinmi?" savoli ilovada va Telegramda |
| 6 | Savolga "Kerak emas" deb javob bering | Episod yopiladi, qo'ng'iroq yo'q |
| 7 | Savolga "Ha" deb javob bering | Telefonda 8-bosqichdagi **sinov raqami** bilan terish oynasi ochiladi |
| 8 | Ilovada 🛡 ni bosing (qo'riqlash), 30 s ichida xonadan chiqing, keyin qayting | "XAVF: uyda harakat" va "Politsiya chaqirilsinmi?" savoli |
| 9 | Bitta RX ni o'chiring | Ilovada platalar soni kamayadi; 2 tadan kam bo'lsa tizim o'zi chaqiruv qarorini chiqarmaydi |
| 10 | Serverni o'chiring | Ilova kulrang bo'ladi, qayta yoqilgach tarix to'ldiriladi |
| 11 | Ilovani yopib, telefonni qulflab 4-sinovni takrorlang | Qulflangan ekranda alarm chiqadi |

Hammasi o'tgach va bir necha kun yolg'on signalsiz ishlagach, `escalation.number` ni `103`, `police.number` ni `102` ga qaytaring va xizmatni qayta ishga tushiring: `sudo systemctl restart wfg`.

## Qo'shimcha (ixtiyoriy)

- **GSM orqali avtomatik qo'ng'iroq va SMS** (SIM800L / A7670 moduli) va **yiqilishda surat oladigan kamera**: bu qismlar alohida tayyorlanmoqda va hali asosiy tarmoqqa qo'shilmagan (PR #1). Ularsiz telefon faqat raqamni terilgan holda ochadi, qo'ng'iroqni odam bosadi.
- Qo'shimcha xona yoki 4–6 plata: [hardware.md](hardware.md), `configs/room_6nodes.yaml`.
