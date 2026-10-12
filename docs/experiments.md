# Tajribalar: diplomning ilmiy qismi

## Tadqiqot savoli

> Arzon ESP32-S3 platalarida o'qitilgan yiqilishni aniqlash modeli **hech qachon ko'rmagan xonada** qanchalik yaxshi ishlaydi, va bir necha kalibrlash klipi bu farqni qanchalik yopadi?

Ochiq maqolalarda ESP32 bilan "yangi odam" sinovi bor (WiFall, arXiv:2412.04783), lekin "yangi xona" sinovi yo'q. Bu ishning yangiligi shu.

## Sinov sxemasi

`wfg experiment` quyidagilarni avtomatik bajaradi:

1. **Bir xonada (yuqori chegara):** har bir xonaning o'zida 70% o'qitish, 30% sinov.
2. **Yangi xona (leave-one-room-out):** bitta xona sinov uchun chetga olinadi, model qolgan xonalarda o'qitiladi.
   - `k = 0`: kalibrlashsiz.
   - `k = 1, 5`: yangi xonadan har bir sinf uchun k ta belgilangan klip (foydalanuvchi o'rnatish paytida 2–3 daqiqada yozadi).
3. Har bir sozlama 3 xil `seed` bilan takrorlanadi, natija o'rtacha ± standart og'ish.

## Usullar

| Nom | Turi | Tavsif |
|---|---|---|
| `classic` | Asos | 22 ta qo'lda tuzilgan belgi + logistik regressiya (NumPy) |
| `classic+restd` | Kalibrlashsiz moslashish | Belgilarni yangi xonaning o'z statistikasi bilan standartlash |
| `cnn1d`, `transformer`, `cnn2d` | Chuqur o'rganish | Amplituda (1D) yoki Doppler spektrogrammasi (2D) ustida |
| `+mmd`, `+coral` | Kalibrlashsiz moslashish | Manba va yangi xona belgilarining taqsimotini yaqinlashtirish |
| `+dann` | Kalibrlashsiz moslashish | Gradient reversal bilan xonani ajrata olmaydigan belgilar o'rganish |
| `+ft` | Few-shot | k ta klip bilan qayta o'qitish (manba ma'lumoti bilan aralashtirib) |
| `+knnmmd` | Few-shot | KNN orqali yangi xona kliplariga yorliq qo'yib, sinflar bo'yicha MMD (WiFall maqolasi g'oyasi asosida qayta yozilgan) |

## Ishga tushirish

```bash
pip install -e ".[dev,ml]"

# real dataset
wfg experiment --data data/raw \
  --methods classic classic+restd cnn1d cnn1d+mmd cnn1d+dann cnn1d+ft cnn1d+knnmmd transformer transformer+dann \
  --shots 0 1 5 --seeds 0 1 2 --out results/real

# yangi odamga moslashish (WiFall bilan solishtirish uchun)
wfg experiment --data data/raw --domain subject --methods classic cnn1d cnn1d+knnmmd --shots 0 1 --out results/subject
```

GPU bo'lmasa Google Colab'da ishga tushiring: `!pip install -e .[ml]` va `--device cuda`.

Natija: `results/.../results.md` (diplomga tayyor jadval) va `results.json` (barcha raqamlar, chalkashlik matritsalari).

## Real vaqtdagi baholash

Klip darajasidagi aniqlik real hayotni to'liq ko'rsatmaydi. `wfg stream-eval` uzluksiz ssenariylarni (yurish, o'tirish, yiqilish, ...) real vaqt dvigateli orqali o'tkazadi va hisoblaydi:

- **recall**: haqiqiy yiqilishlarning necha foizi 6 soniya ichida aniqlandi,
- **mean_delay_s**: o'rtacha kechikish,
- **false_alarms_per_hour**: soatiga yolg'on "yiqilish gumoni" soni.

Hozircha bu simulyatorda ishlaydi. Real uzluksiz yozuvlar uchun ham xuddi shu `score_events` funksiyasidan foydalaning.

## Simulyatsiya natijalari (namuna)

`results/simulated/` papkasida simulyatsiya qilingan 5 xonadagi natija bor. Bu **real natija emas**, faqat butun zanjir ishlashini va "yangi xonada aniqlik tushadi" degan hodisani ko'rsatadi. Diplomga faqat real datasetdagi raqamlarni yozing.
