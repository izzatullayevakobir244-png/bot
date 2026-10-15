# 🎧 MyMusic Telegram Bot

Zamonaviy, tezkor va to'liq funksional Telegram musiqa boti. Aiogram 3 va Python 3.10+ yordamida yaratilgan.

---

## 🚀 Asosiy imkoniyatlar

1. **Musiqa qidirish va yuklab olish:**
   - Qo'shiq nomi yoki ijrochi nomi bo'yicha tezkor qidiruv (YouTube / Music).
   - Sahifalash (Pagination) — 1 sahifada 5 tadan qulay natijalar va tugmalar.
   - Yuqori sifatli MP3 fayl (192 kbps) sifatida yuklab olish.
   - Avtomatik ID3 teglar va muqova (Cover art) o'rnatish.

2. **Kesh tizimi (Instant Cache):**
   - Bir marta yuklangan har qanday qo'shiq SQLite ma'lumotlar bazasida `file_id` bilan saqlanadi.
   - Boshqa foydalanuvchi xuddi shu qo'shiqni so'raganda qayta yuklab o'tirmasdan, **1 soniyada** yuboriladi.

3. **🎤 Ovozli qidiruv (Voice & Video Note Search):**
   - Ovozli xabar (voice) yoki yumaloq video (video note) yuborilganda nutqni taniy oladi (Uzbek, Rus, Ingliz tillarida).
   - Aniqlangan matn orqali avtomatik qidiruv amalga oshiriladi.

4. **📜 Qo'shiq matnlari (Lyrics):**
   - Har bir yuklangan tarona tagida «📜 Matni» tugmasi mavjud bo'lib, LRCLIB orqali qo'shiq matnini chiqarib beradi.

5. **❤️ Sevimlilar (Favorites):**
   - Foydalanuvchilar yoqtirgan qo'shiqlarini o'z shaxsiy ro'yxatiga saqlashi va istalgan vaqt bir tugma bilan tinglashi mumkin.

6. **🔝 Top va Xit Musiqalar (Charts):**
   - O'zbek xitlari, Rus xitlari, Jahon xitlari, Yangi premyeralar, TikTok trendlar bo'yicha toifalar.

7. **⚡️ Inline rejim (Inline Search):**
   - Har qanday guruh yoki shaxsiy chatda `@bot_username qo'shiq_nomi` yozib musiqalarni qidirish va ulashish.

8. **👑 Boshqaruv paneli (Admin Panel):**
   - 📊 Bot statistikasi (foydalanuvchilar soni, qidiruvlar, yuklashlar, kesh hajmi).
   - 📢 Barcha foydalanuvchilarga xabar tarqatish (Broadcast).
   - ➕/➖ Majburiy homiy kanallarni sozlash (Foydalanuvchi obuna bo'lmaguncha botdan foydalana olmaydi).

9. **🌐 Ko'p tilli interfeys:**
   - O'zbekcha, Ruscha va Inglizcha to'liq qo'llab-quvvatlanadi.

---

## 🛠 O'rnatish va Ishga tushirish

### 1. Kerakli kutubxonalarni o'rnatish:
```bash
pip install -r requirements.txt
```

### 2. Sozlamalarni kiritish (.env):
Loyiha papkasida `.env` faylini yarating (yoki `.env.example` dan nusxa oling) va quyidagi ma'lumotlarni to'ldiring:
```env
BOT_TOKEN=1234567890:AAH...sizning_bot_tokeningiz
ADMINS=sizning_telegram_id
BOT_NAME=MyMusic Bot
BOT_USERNAME=MyMusic_bot
```

> **Eslatma:** O'z Telegram ID ingizni bilish uchun Telegramda [@userinfobot](https://t.me/userinfobot) ga `/start` yuborishingiz mumkin.

### 3. Botni ishga tushirish:
```bash
python main.py
```

---

## 📁 Loyiha tuzilishi

```text
├── config.py                  # Bot sozlamalari va muhit o'zgaruvchilari
├── database.py                # SQLite (aiosqlite) ma'lumotlar bazasi
├── main.py                    # Botni ishga tushiruvchi asosiy fayl
├── requirements.txt           # Kerakli Python kutubxonalari
├── .env.example               # Namuna sozlama fayli
├── downloads/                 # Vaqtinchalik audio yuklashlar papkasi
├── handlers/
│   ├── admin.py               # Admin paneli va kanallar boshqaruvi
│   ├── audio.py               # Ovozli xabar va audio fayllarni qabul qilish
│   ├── charts.py              # Xit va top taronalar
│   ├── favorites.py           # Sevimli musiqalar bo'limi
│   ├── inline.py              # Inline qidiruv tizimi
│   └── user.py                # Foydalanuvchi buyruqlari va qidiruv
├── keyboards/
│   ├── inline.py              # Inline tugmalar (tugmalar, pagination, va h.k.)
│   └── reply.py               # Asosiy menyu tugmalari
├── middlewares/
│   └── subscription_middleware.py # Majburiy kanal a'zoligi tekshiruvi
└── services/
    ├── charts_service.py      # Top chartlar xizmati
    ├── lyrics_service.py      # Qo'shiq matnlarini olish (LRCLIB)
    ├── music_service.py       # Musiqa qidirish va MP3 yuklab olish (yt-dlp)
    └── voice_service.py       # Ovozli xabarni tanish (SpeechRecognition)
```
