# Dataset yozish protokoli

Maqsad: kamida **3 ta har xil xonada**, **5–10 ko'ngilli** bilan, har bir harakatdan har bir odamdan 10 tadan klip. Bu "yangi xonaga moslashish" tajribasi uchun yetarli hajm.

## Xonalar

Xonalarni bir-biridan iloji boricha farqli tanlang va har birini yozib qo'ying:

| Kod | Misol | Nimani yozish kerak |
|---|---|---|
| `xona1_gisht` | Uydagi yotoqxona, g'isht devor | o'lchami (m), devor materiali, mebel, deraza |
| `xona2_beton` | Yotoqxona yoki kvartira, beton devor | |
| `xona3_katta` | Auditoriya yoki zal | |
| `xona4_nlos` (ixtiyoriy) | TX va RX orasida devor yoki shkaf | to'g'ridan-to'g'ri ko'rinish yo'q |

## Harakatlar (sinflar)

| Belgi | Ta'rif | Davomiyligi |
|---|---|---|
| `empty` | Xonada hech kim yo'q | 5 s |
| `still` | Odam tik turibdi yoki o'tirib qimirlamayapti | 5 s |
| `walk` | Odatdagi yurish | 5 s |
| `sit` | Tik turgan holatdan stulga o'tirish | 5 s |
| `lie` | Karavot yoki matrasga sekin yotish | 6 s |
| `fall` | Matrasga yiqilish: oldinga, yonga, orqaga, tizzadan (har safar boshqacha) | 5 s |

Har bir klipda harakat signaldan keyin 1 soniya ichida boshlanishi kerak.

## Yozish

```bash
wfg nodes                         # avval uchala plata ~100 Hz ekanini tekshiring
wfg record --room xona1_gisht --subject s01 --protocol configs/protocol.yaml --notes "4x3.5 m, g'isht, RX0 shkaf ustida"
```

Dastur har bir takrordan oldin ko'rsatma beradi, 3-2-1 sanaydi, signal beradi va 5 soniya yozadi. Natija: `data/raw/<xona>/<odam>/<harakat>_NN.npz`.

Bir kishi bir xonada taxminan 45 daqiqa vaqt sarflaydi (60 klip).

## Xavfsizlik va axloq

- Yiqilishlar faqat **matras ustiga**, sekin va nazorat ostida bajariladi. Keksa odamlar yiqilish yozuvida qatnashmaydi. Bu sohadagi barcha ishlar shunday qiladi va diplomda buni cheklov sifatida yozing.
- Har bir ko'ngillidan yozma rozilik oling (namunasi: ism, sana, "tajribada ixtiyoriy ishtirok etaman, istalgan vaqtda to'xtatishim mumkin").
- Datasetda ism saqlanmaydi, faqat `s01`, `s02` kodlari. Kim qaysi kod ekanini alohida qog'ozda saqlang.
- Bo'yi, vazni va yoshini (ixtiyoriy) yozib qo'ying, bu diplomdagi "ishtirokchilar" jadvali uchun kerak.

## Sifat nazorati

Har bir sessiyadan keyin:

```bash
wfg experiment --data data/raw --methods classic --shots 0 --out results/check
```

Bitta xonaning o'zida aniqlik 80% dan past bo'lsa, platalar joylashuvini tekshiring (odam TX va RX orasida harakat qilyaptimi?).
