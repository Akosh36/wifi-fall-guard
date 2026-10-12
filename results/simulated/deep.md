# Chuqur modellar: simulyatsiya natijalari

> **Diqqat:** bu natijalar **simulyatsiya** qilingan ma'lumotlarda olingan, real o'lchov emas.
> Ular faqat kod zanjiri ishlashini va "yangi xonada aniqlik tushadi, moslashtirish uni qaytaradi" degan hodisani ko'rsatadi. Diplomga faqat real datasetdagi raqamlarni yozing.

Manba: GitHub Actions "Simulated experiment" workflow, run 38315840448 (2026-10-12).

Buyruqlar:

```
wfg simulate --rooms sim_a sim_b sim_c sim_d --clips 20 --out data/sim
wfg experiment --data data/sim --methods classic classic+restd cnn1d cnn1d+mmd cnn1d+dann cnn1d+ft cnn1d+knnmmd --shots 0 1 5 --seeds 0 --epochs 25 --out results/ci
```

480 klip, 4 xona, leave-one-room-out, bitta seed.

| Sharoit | Usul | k (kalibrlash) | Aniqlik | Macro-F1 | Yiqilish recall | Yiqilish precision | Yolg'on signal |
|---|---|---|---|---|---|---|---|
| Yangi xona | classic | 0 | 85.8% ± 3.8% | 0.855 | 85.0% | 92.2% | 1.8% |
| Yangi xona | classic | 1 | 87.1% ± 4.9% | 0.867 | 86.8% | 91.8% | 1.8% |
| Yangi xona | classic | 5 | 87.8% ± 4.5% | 0.875 | 96.7% | 91.2% | 2.0% |
| Yangi xona | classic+restd | 0 | 89.6% ± 3.0% | 0.894 | 96.2% | 96.7% | 0.8% |
| Yangi xona | classic+restd | 1 | 89.0% ± 3.4% | 0.889 | 96.1% | 96.6% | 0.8% |
| Yangi xona | classic+restd | 5 | 88.6% ± 2.0% | 0.885 | 96.7% | 97.1% | 0.7% |
| Yangi xona | cnn1d | 0 | 48.3% ± 10.2% | 0.405 | 31.2% | 31.3% | 16.5% |
| Yangi xona | cnn1d | 1 | 64.3% ± 5.8% | 0.635 | 47.4% | 73.9% | 3.7% |
| Yangi xona | cnn1d | 5 | 88.1% ± 3.6% | 0.877 | 76.7% | 91.6% | 1.7% |
| Yangi xona | cnn1d+dann | 0 | 69.2% ± 4.9% | 0.676 | 51.2% | 68.3% | 4.8% |
| Yangi xona | cnn1d+dann | 1 | 78.5% ± 2.9% | 0.780 | 55.3% | 69.5% | 5.0% |
| Yangi xona | cnn1d+dann | 5 | 88.3% ± 2.9% | 0.883 | 81.7% | 94.5% | 1.0% |
| Yangi xona | cnn1d+ft | 1 | 71.7% ± 5.2% | 0.704 | 44.7% | 77.1% | 2.4% |
| Yangi xona | cnn1d+ft | 5 | 88.6% ± 4.7% | 0.878 | 81.7% | 83.2% | 3.3% |
| Yangi xona | cnn1d+knnmmd | 1 | 70.2% ± 5.8% | 0.699 | 56.6% | 71.5% | 10.0% |
| Yangi xona | cnn1d+knnmmd | 5 | 85.3% ± 3.6% | 0.847 | 76.7% | 86.9% | 2.3% |
| Yangi xona | cnn1d+mmd | 0 | 78.1% ± 5.7% | 0.776 | 60.0% | 66.2% | 6.2% |
| Yangi xona | cnn1d+mmd | 1 | 85.5% ± 2.4% | 0.852 | 76.3% | 76.1% | 4.7% |
| Yangi xona | cnn1d+mmd | 5 | 90.8% ± 2.9% | 0.907 | 86.7% | 89.6% | 2.0% |
| Bir xonada | classic | 0 | 88.9% ± 5.9% | 0.889 | 91.7% | 96.4% | 0.8% |
| Bir xonada | cnn1d | 0 | 95.1% ± 2.3% | 0.952 | 100.0% | 93.8% | 1.7% |

## Nimani ko'rsatadi

- CNN bir xonada eng yaxshi (95.1%), lekin yangi xonaga o'tganda 48.3% gacha tushadi. Bu diplomning asosiy muammosi: domen siljishi.
- Moslashtirish farqni qisqartiradi: k=0 da MMD 48% → 78%, DANN 48% → 69%. 5 ta kalibrlash klipi bilan CNN+MMD 90.8% ga chiqadi.
- Klassik belgilar (xona bo'yicha standartlash bilan, `classic+restd`) simulyatsiyada juda barqaror. Real ma'lumotda bu tartib o'zgarishi mumkin; aynan shu savolni real dataset hal qiladi.
- KNN-MMD bu yerda oddiy MMD dan past. Sabab ehtimol kichik dataset va bitta seed; real ma'lumotda qayta sinash kerak.
- Faqat bitta seed ishlatilgan, shuning uchun ± qiymatlari xonalar orasidagi farqni ko'rsatadi, seedlar orasidagini emas.
