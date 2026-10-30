# 🎬 Kino Bot — Professional Telegram Bot

Aiogram 3.x + SQLite asosida yozilgan to'liq funksional premium kino bot.

## 📁 Loyiha tuzilishi

```
kino_bot/
├── config.py       # Token, admin ID, karta ma'lumotlari, sozlamalar
├── database.py     # SQLite bilan ishlash (aiosqlite, async)
├── states.py       # FSM holatlari
├── buttons.py      # Barcha reply/inline klaviaturalar
├── main.py         # Botning asosiy mantiqi (barcha handlerlar)
├── requirements.txt
└── README.md
```

## ⚙️ O'rnatish

1. Python 3.10+ o'rnatilgan bo'lishi kerak.

2. Kutubxonalarni o'rnating:
```bash
pip install -r requirements.txt
```

3. `config.py` faylini oching va quyidagilarni to'ldiring:
   - `BOT_TOKEN` — @BotFather'dan olingan token
   - `ADMIN_IDS` — sizning Telegram ID raqamingiz (bir nechta admin bo'lsa vergul bilan ro'yxatga qo'shing)
   - `CARD_NUMBER`, `CARD_HOLDER` — to'lov qabul qilinadigan karta ma'lumotlari
   - `PREMIUM_PRICE`, `PREMIUM_DURATION_DAYS` — narx va muddat (standart: 10 000 so'm / 30 kun). Matnlardagi narx va muddat shu qiymatlardan avtomatik olinadi

4. Botni ishga tushiring:
```bash
python main.py
```

Birinchi ishga tushganda `database.db` fayli avtomatik yaratiladi va barcha jadvallar tuziladi.

## 🧩 Asosiy funksiyalar

### Foydalanuvchi uchun
- Majburiy obuna tekshiruvi (bir nechta kanal qo'llab-quvvatlanadi)
- **Har bir menyu tugmasi bosilganda obuna qayta tekshiriladi** — agar admin yangi majburiy kanal qo'shsa (yoki foydalanuvchi biror kanaldan chiqib ketsa), botdan foydalanayotgan foydalanuvchi uchun ham darhol barcha tugmalar to'xtaydi, reply klaviatura olib tashlanadi va qayta obuna bo'lish so'raladi — shundan keyingina botning boshqa funksiyalari qayta ishlay boshlaydi
- Premium sotib olish (karta orqali to'lov + chek yuborish)
- Admin chekni tasdiqlaydi/bekor qiladi
- Premium olgandan keyin (yoki premium tizimi o'chirilgan bo'lsa, hammaga bepul):
  - 🔍 Kino qidirish (kod bo'yicha)
  - ⏳ Premium muddati (real vaqtda hisoblanadi: kun/soat/daqiqa/soniya)
  - 🎲 Random kino
  - 🆕 Bugungi qo'shilgan kinolar
- Kino yuborilganda caption sifatida **faqat admin "Kino qo'shish" bosqichida yozgan tavsif** ko'rsatiladi — bot hech qanday qo'shimcha "Kod:" yoki shunga o'xshash yozuv qo'shmaydi
- Premium tugaganda avtomatik xabar keladi (fon jarayon har daqiqada tekshiradi)
- Deep-link orqali (`https://t.me/BotUsername?start=7112` yoki `/start 7112`) botga kirsa, o'sha kodli kino avtomatik topib beriladi

### Admin uchun
- Admin `/start` bosganda avtomatik tanib olinadi va admin panel ochiladi
- 📢 Reklama yuborish — istalgan turdagi kontent (matn/rasm/video/stiker) barcha foydalanuvchilarga, shu jumladan botni bloklaganlarga ham urinib ko'riladi, natija (nechta yetdi/yetmadi) ko'rsatiladi
- 📊 Statistika — 30 kunlik davr, har 5 soatda keshdan yangilanadi
- ➕ Obuna qo'shish — kanal qo'shish/o'chirish/ro'yxatini ko'rish (bot kanalda admin ekanligi avtomatik tekshiriladi). Kanal **ochiq (public)** bo'lsa `@username` kiritiladi; **yopiq (private)** bo'lsa username o'rniga `-` yuboriladi va bot o'zi (darhol qo'shiladigan) taklif havolasini yaratadi
- 🎯 Zayavka kanal qo'shish — (➕ Obuna qo'shish bo'limi ichida) **avval nomi**, keyin **havola** (masalan `https://t.me/+AbCdEf123`, Telegram'ning o'zidan nusxalab olinadi), so'ngra **ID** so'raladi. Bu kanal ham majburiy obuna ro'yxatiga qo'shiladi va barcha to'lov cheklari shu kanalga ham yuboriladi. Havola "so'rov orqali qo'shilish" (Request Admin Approval) rejimida bo'lishi tavsiya etiladi — bot bu so'rovlarni **hech qachon o'zi qabul qilmaydi**, faqat "kelgan-kelmaganini" bazaga yozib, tekshirish uchun ishlatadi (pastga qarang)
- 🧾 Chek tekshirish — tasdiqlanmagan barcha to'lov cheklari ro'yxati va tasdiqlash/bekor qilish tugmalari
- 💵 Qo'lda to'lov — ID orqali foydalanuvchiga qo'lda premium berish
- 🎬 Kino qo'shish — kod → tavsif → video, xohlagan payt "❌ Bekor qilish" bilan to'xtatish mumkin
- ⚙️ Premium boshqaruvi — premium tizimini butunlay yoqish/o'chirish. O'chirilsa, barcha foydalanuvchilar faqat kanallarga obuna bo'lib, kinolarni **bepul** tomosha qilaveradi

- 📌 Kanalga joylash — kino kodi → (kod bazada yo'q bo'lsa "bu kino qo'shilmagan" deydi) → qisqacha video yoki rasm → izoh (premium emojilar saqlanadi) → bot postni kanalga avtomatik joylaydi: media + izoh + pastida ko'k «TOMOSHA QILISH» tugmasi. Tugma botga `?start=KOD` havolasi bilan olib keladi: premium bor bo'lsa kino chiqadi, bo'lmasa premium sotib olish taklif qilinadi.
  - Kanal `config.py` dagi `POST_CHANNEL_ID` dan olinadi. Bo'sh bo'lsa, bot birinchi joylashda so'raydi va eslab qoladi. O'zgartirish: `/postkanal -1001234567890` yoki `/postkanal @kanal`
  - Bot o'sha kanalda admin bo'lishi kerak. Izoh 1024 belgigacha. Kod faqat lotin harflari/raqam/`_`/`-` bo'lsa havolada ishlaydi.
  - Telegram kanallarga bot nomidan premium emoji yuborishga ruxsat bermaydi. Shuning uchun izohni video/rasm bilan **bir xabarda (caption)** yuborsangiz, bot xabarni kanalga nusxalaydi (copy_message) va premium emojilar saqlanadi. Izohsiz yuborilsa, izoh alohida so'raladi va premium emojilar oddiy emoji bo'lib qolishi mumkin.


### 🆕 Yangi imkoniyatlar
- **Obuna bosqichi:** barcha kanal tugmalari qizil (oldida ➕), «✅ Tekshirish» yashil.
- **Foydalanuvchi menyusi (hammasi qizil):** 🔍 Kino qidirish (uzun) → 🎲 Random kino + ⏳ Premium muddati → 🆕 Bugungi kinolar (uzun).
- **🔍 Kino qidirish:** kod yozish mumkin yoki 3 ta bo'limdan tanlanadi: 🔥 Top filmlar, 📺 Top seriallar, 🧸 Top multfilmlar. Har bosishda tasodifiy 10 tagacha nom chiqadi (kam bo'lsa — borichasi), nomni bossangiz kino yuboriladi. «🔄 Yangilash» ro'yxatni almashtiradi.
- **⏳ Premium muddati:** ID, ism, status, qolgan kun va tugash sanasi chiqadi.
- **Kino tagidagi tugmalar (film/multfilm):** yashil «🍿 Boshqa filmlar» (`MORE_MOVIES_URL` kanaliga) va katta «↗️ Ulashish» (kino havolasini yuboradi).
- **Admin menyusi:** barcha tugmalar qizil.
- **📺 Serial / Anime (admin):** kod (botda yo'q bo'lishi kerak) → izoh → qismlar ketma-ket (1, 2, 3...) → «✅ Kino tugadi» tugmasi bosilgach saqlanadi. «❌ Bekor qilish» bosilsa, hech narsa saqlanmaydi. Foydalanuvchi kodni kiritsa 1-qism chiqadi, tagida qizil qism raqamlari va ko'k «📤 Do'stlarga ulashish»; raqamni bossa o'sha qism chiqadi, izohida «N-qism» yoziladi. 40 tadan ko'p qism bo'lsa sahifalanadi.
- **🎬 Kino qo'shish:** endi kod dan keyin tur tanlanadi (Film / Multfilm).
- **Eski kinolar turi:** avval qo'shilgan kinolar «film» hisoblanadi. O'zgartirish: `/kategoriya KOD film|multfilm|serial`

### 🎨 Rangli tugmalar
Barcha inline va reply tugmalar Telegram'ning tugma `style` xususiyati bilan rangli (yashil / qizil / ko'k). Buning uchun `aiogram>=3.25` kerak va foydalanuvchining Telegram ilovasi yangi bo'lishi kerak (eski ilovalarda tugmalar oddiy rangda ko'rinadi).

### Deep-link orqali to'g'ridan-to'g'ri kino ochish
Foydalanuvchi `https://t.me/BotUsername?start=7112` havolasi orqali (yoki `/start 7112` orqali) botga kirsa:
- Agar obuna/premium shartlari bajarilgan bo'lsa — kod darhol qidiriladi va topilgan kino yuboriladi
- Agar hali obuna bo'lmagan yoki premium sotib olinmagan bo'lsa — kod eslab qolinadi va shartlar bajarilgach (chek tasdiqlangach yoki admin qo'lda premium bergach) avtomatik yuboriladi
- Bunday kod topilmasa, foydalanuvchiga "topilmadi" degan xabar chiqadi

### 🔒 Join Request tizimi (bot HECH QACHON approve qilmaydi)
Bot `chat_join_request` eventini kuzatib turadi, lekin uni **hech qachon o'zi qabul qilmaydi**. Ishlash tartibi:

1. Foydalanuvchi kanalga (majburiy obuna yoki zayavka) Join Request yuboradi
2. Bot buni ushlab, faqat **bazaga yozib qo'yadi** (`join_requests` jadvali: `user_id`, `channel_id`, `requested_at`) — `approve_chat_join_request()` umuman chaqirilmaydi
3. Foydalanuvchi kanalning o'zida hamon **"pending" (kutilmoqda)** holatida qoladi — na bot, na admin uni qo'lda qabul qilmaydi
4. Foydalanuvchi botda "✅ Tekshirish" tugmasini bosganda, bot avval haqiqiy a'zolikni (`get_chat_member`) tekshiradi; agar hali a'zo bo'lmasa, bazadan o'sha kanalga so'rov yuborganini tekshiradi
5. Agar so'rov bazada topilsa — "✅ Kanalga qo'shilish so'rovingiz qabul qilindi. Endi davom etishingiz mumkin." deb, majburiy obuna tekshiruvidan **o'tkazadi** (foydalanuvchi hali kanalga real a'zo bo'lmasa ham)
6. Agar so'rov bazada topilmasa — "❌ Avval kanalga Join Request yuboring." deb ko'rsatadi

**Ishlashi uchun shartlar:**
- Bot o'sha kanalda **admin** bo'lishi kerak (kanal qo'shilganda buni bot avtomatik tekshiradi)
- Kanal bazada ro'yxatdan o'tgan bo'lishi kerak (admin panel orqali qo'shilgan) — ro'yxatda bo'lmagan begona kanallarning so'rovlariga bot tegmaydi

## 🗄 Ma'lumotlar bazasi (SQLite)

- `users` — foydalanuvchilar, premium holati, faollik, pending kod (deep-link)
- `channels` — majburiy obuna kanallari (oddiy va zayavka kanallar bir xil jadvalda, `is_zayavka` ustuni orqali ajratiladi)
- `movies` — kinolar (kod, tavsif, video file_id, tur: film/serial/multfilm)
- `movie_parts` — serial/anime qismlari (movie_id, part_no, file_id)
- `payments` — to'lov cheklari (pending/approved/rejected)
- `premium_history` — barcha berilgan premiumlar tarixi (statistikada foyda hisoblanadi)
- `settings` — statistika keshi, davr sozlamalari, premium yoqiq/o'chiq holati
- `join_requests` — kanallarga yuborilgan Join Request'lar (`user_id`, `channel_id`, `requested_at`) — obuna tekshiruvi uchun "dalil" sifatida ishlatiladi, bot bularni hech qachon avtomatik qabul (approve) qilmaydi

## 📝 Eslatmalar

- Kod `aiosqlite` orqali to'liq **asinxron** yozilgan — bloklanish yo'q.
- Statistika davri 30 kunda avtomatik 0 dan qayta boshlanadi.
- "Qo'lda to'lov" orqali berilgan premiumlar statistikadagi **foyda**ga qo'shilmaydi (chunki haqiqiy to'lov bo'lmagan), lekin foydalanuvchilar sonini hisoblashda hisobga olinadi.
- Ichki fayl/jadval nomlari (`kino_bot`, `movies` jadvali va h.k.) o'zgartirilmadi — bular faqat kod ichida ishlatiladi.
