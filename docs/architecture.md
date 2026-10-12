# Arxitektura

```
 ESP32-S3 TX (AP, 6-kanal)
     │  ping javoblari, 100 Hz
     ▼
 ESP32-S3 RX ×3  ──UDP 148 bayt──►  CSIHub (wfg/collector/hub.py)
 (firmware/csi_rx)                   │ soatlarni moslash, 4 s oyna
                                     ▼
                         Tozalash va belgilar (wfg/dsp)
                         Hampel → low-pass 35 Hz → nisbiy amplituda → PCA → Doppler
                                     ▼
                         Model (wfg/baseline, wfg/models) → 6 sinf ehtimoli
                                     ▼
                         FallDetector (wfg/inference/events.py)
                         yiqildi ×2 oyna → GUMON → 20 s harakatsiz → XAVF
                                     │                └ yurdi → TURDI (bekor)
                                     ▼
              FastAPI (wfg/server/app.py): REST, WebSocket, SQLite
                     │                         │
              Veb panel (static/index.html)   Telegram bot (notifier.py)
```

## Modullar

| Modul | Vazifa |
|---|---|
| `wfg/csi/packet.py` | Proshivka bilan bir xil UDP paket formati; 64 FFT bin → 52 ma'lumot subcarrier |
| `wfg/csi/simulator.py` | Fizik simulyator: statik ko'p yo'llilik + tanadan qaytgan yo'l + shovqin + int8 kvantlash. Har bir "xona" har xil, shuning uchun xonalar orasidagi farqni (domain shift) modellashtiradi |
| `wfg/collector/` | UDP qabul qilish, platalar soatini moslash, dataset yozish |
| `wfg/dsp/` | Signalni tozalash, belgilar (amplituda, Doppler spektrogrammasi, 22 ta klassik belgi) |
| `wfg/baseline/classic.py` | NumPy logistik regressiya, PyTorch kerak emas, RPi'da tez ishlaydi |
| `wfg/models/nets.py` | CNN-1D, CNN-2D, Transformer |
| `wfg/adapt/losses.py` | MMD, CORAL, sinf bo'yicha MMD, DANN diskriminatori |
| `wfg/train/` | O'qitish, few-shot kalibrlash, KNN-MMD, leave-one-room-out tajribasi, metrikalar |
| `wfg/inference/` | Real vaqt dvigateli, hodisa mantiqi, simulyatsiyada qayta o'ynatish va baholash |
| `wfg/server/` | API, veb panel, SQLite, Telegram |

## Asosiy qarorlar

- **Nisbiy amplituda.** Amplituda xonaning o'rtacha signal darajasiga bo'linadi. Bu kuchli va kuchsiz aloqali xonalarni bir xil masshtabga keltiradi.
- **Faza ishlatilmaydi (hozircha).** ESP32 da har bir paketning fazasi tasodifiy siljiydi (CFO/STO). `sanitize_phase` uni qisman tozalaydi, lekin bitta antennada ishonchli emas. Diplomda bu kelajakdagi ish sifatida qayd etiladi.
- **Ikki bosqichli ogohlantirish.** Bitta "yiqilish" bashorati yetarli emas: avval ketma-ket 2 oyna, keyin 20 soniya harakatsizlik. Odam turib yursa ogohlantirish bekor qilinadi. Bu yolg'on signallarni keskin kamaytiradi.
- **Hisoblash serverda.** ESP32 faqat o'lchaydi. Bu modelni almashtirishni osonlashtiradi. TinyML (modelni ESP32 ichida ishlatish) kelajakdagi ish.
