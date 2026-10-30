# config.py
# Botning asosiy sozlamalari shu yerda saqlanadi

BOT_TOKEN = ""  # <-- @BotFather dan olingan tokenni shu yerga qo'ying

# Admin(lar) ID raqami(lari). Bir nechta admin bo'lishi mumkin, ro'yxatga qo'shib ketavering.
ADMIN_IDS = [8550069571]  # <-- o'zingizning Telegram ID raqamingizni yozing

# To'lov qabul qilinadigan karta ma'lumotlari
CARD_NUMBER = "3443"
CARD_HOLDER = " Qizlarxon"

# Premium narxi va muddati
PREMIUM_PRICE = 10000           # so'mda
PREMIUM_DURATION_DAYS = 30      # kun
PREMIUM_DURATION_HOURS = PREMIUM_DURATION_DAYS * 24  # soatga o'girilgan (avtomatik)

# Statistika har necha kunda 0 dan qayta boshlanadi
STATS_RESET_DAYS = 30

# Statistika keshi necha soatda yangilanadi (soat)
STATS_REFRESH_HOURS = 5

# Premium muddati foydalanuvchiga necha daqiqada bir yangilanib turishi kerakligi haqida eslatma
# (foydalanuvchi tugma bosganda har doim ANIQ vaqt hisoblanadi, bu son faqat izoh uchun)
PREMIUM_TIMER_REFRESH_MINUTES = 10

DB_NAME = "database.db"

# "📌 Kanalga joylash" postlari yuboriladigan kanal.
# ID (masalan -1001234567890) yoki @username yozing. Bo'sh qoldirsangiz (None),
# bot birinchi joylashda adminning o'zidan so'raydi va eslab qoladi
# (keyin /postkanal <ID yoki @username> buyrug'i bilan o'zgartirish mumkin).
POST_CHANNEL_ID = None

# Kino ostidagi "Boshqa filmlar" tugmasi olib boradigan kanal
MORE_MOVIES_URL = "https://t.me/Xanzofilm"
