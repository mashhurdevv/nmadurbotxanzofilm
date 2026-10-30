# buttons.py
# Botning barcha reply va inline klaviaturalari shu yerda
#
# Ranglar Telegram Bot API'ning tugma "style" xususiyati orqali beriladi:
#   "success" - yashil, "danger" - qizil, "primary" - ko'k

from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
)
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

import urllib.parse

GREEN = "success"
RED = "danger"
BLUE = "primary"


# ---------------------------------------------------------------------- #
#                        OBUNA TEKSHIRISH QISMI                          #
# ---------------------------------------------------------------------- #
def subscription_keyboard(channels: list) -> InlineKeyboardMarkup:
    """
    channels: [(id, name, username, channel_id, invite_link, is_zayavka), ...]
    Barcha obuna (kanal) tugmalari qizil (oldida ➕), "Tekshirish" - yashil.
    """
    builder = InlineKeyboardBuilder()
    for ch in channels:
        _id, name, username, channel_id, invite_link, is_zayavka = ch
        link = invite_link or (f"https://t.me/{username.lstrip('@')}" if username else None)
        if not link:
            continue
        builder.row(InlineKeyboardButton(text=f"➕ {name}", url=link, style=RED))
    builder.row(InlineKeyboardButton(text="✅ Tekshirish", callback_data="check_sub", style=GREEN))
    return builder.as_markup()


# ---------------------------------------------------------------------- #
#                             PREMIUM SOTIB OLISH                        #
# ---------------------------------------------------------------------- #
def premium_offer_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="💎 PREMIUM OLISH", callback_data="premium_buy", style=GREEN))
    return builder.as_markup()


def premium_payment_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="⬅️ ORQAGA QAYTISH", callback_data="premium_back", style=RED))
    return builder.as_markup()


# ---------------------------------------------------------------------- #
#                       FOYDALANUVCHI ASOSIY MENYUSI                     #
# ---------------------------------------------------------------------- #
def user_main_menu() -> ReplyKeyboardMarkup:
    """Barcha tugmalar qizil. 1-qator uzun, 2-qatorda ikkita, 3-qator uzun."""
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text="🔍 Kino qidirish", style=RED))
    builder.row(
        KeyboardButton(text="🎲 Random kino", style=RED),
        KeyboardButton(text="⏳ Premium muddati", style=RED),
    )
    builder.row(KeyboardButton(text="🆕 Bugungi kinolar", style=RED))
    return builder.as_markup(resize_keyboard=True)


def remove_keyboard():
    return ReplyKeyboardRemove()


# ---------------------------------------------------------------------- #
#                              ADMIN MENYUSI                              #
# ---------------------------------------------------------------------- #
def admin_main_menu() -> ReplyKeyboardMarkup:
    """Admin paneldagi barcha reply tugmalar qizil."""
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text="📢 Reklama yuborish", style=RED),
        KeyboardButton(text="📊 Statistika", style=RED),
    )
    builder.row(
        KeyboardButton(text="➕ Obuna qo'shish", style=RED),
        KeyboardButton(text="🧾 Chek tekshirish", style=RED),
    )
    builder.row(
        KeyboardButton(text="💵 Qo'lda to'lov", style=RED),
        KeyboardButton(text="🎬 Kino qo'shish", style=RED),
    )
    builder.row(
        KeyboardButton(text="📺 Serial / Anime", style=RED),
        KeyboardButton(text="📌 Kanalga joylash", style=RED),
    )
    builder.row(KeyboardButton(text="⚙️ Premium boshqaruvi", style=RED))
    return builder.as_markup(resize_keyboard=True)


def admin_cancel_keyboard() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text="❌ Bekor qilish", style=RED))
    return builder.as_markup(resize_keyboard=True)


# ---------------------------------------------------------------------- #
#                      ADMIN -> OBUNA KANAL BOSHQARUVI                   #
# ---------------------------------------------------------------------- #
def admin_channel_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="➕ Obuna kanal qo'shish", callback_data="ch_add", style=GREEN))
    builder.row(InlineKeyboardButton(text="🗑 Obuna kanal o'chirish", callback_data="ch_del", style=RED))
    builder.row(InlineKeyboardButton(text="📋 Mavjud kanallar", callback_data="ch_list", style=BLUE))
    builder.row(InlineKeyboardButton(text="🎯 Zayavka kanal qo'shish", callback_data="zayavka_add", style=GREEN))
    return builder.as_markup()


def admin_channel_delete_list(channels: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for ch in channels:
        channel_db_id, name, is_zayavka = ch[0], ch[1], ch[5]
        label = f"🎯 {name} (zayavka)" if is_zayavka else f"🗑 {name}"
        builder.row(InlineKeyboardButton(text=label, callback_data=f"ch_del_select:{channel_db_id}", style=RED))
    builder.row(InlineKeyboardButton(text="⬅️ Asosiy menyuga qaytish", callback_data="admin_back_menu", style=BLUE))
    return builder.as_markup()


def admin_channel_delete_confirm(channel_db_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ O'chirish", callback_data=f"ch_del_confirm:{channel_db_id}", style=GREEN),
        InlineKeyboardButton(text="❌ Bekor qilish", callback_data="ch_del_cancel", style=RED),
    )
    return builder.as_markup()


def admin_back_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="⬅️ Asosiy menyuga qaytish", callback_data="admin_back_menu", style=BLUE))
    return builder.as_markup()


# ---------------------------------------------------------------------- #
#                          ADMIN -> CHEK TEKSHIRISH                       #
# ---------------------------------------------------------------------- #
def check_confirm_keyboard(payment_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"check_approve:{payment_id}", style=GREEN),
        InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"check_reject:{payment_id}", style=RED),
    )
    return builder.as_markup()


# ---------------------------------------------------------------------- #
#                         ADMIN -> QO'LDA TO'LOV                         #
# ---------------------------------------------------------------------- #
def manual_payment_confirm_keyboard(user_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"manual_confirm:{user_id}", style=GREEN),
        InlineKeyboardButton(text="❌ Bekor qilish", callback_data="manual_cancel", style=RED),
    )
    return builder.as_markup()


# ---------------------------------------------------------------------- #
#                       ADMIN -> KINO QO'SHISH                       #
# ---------------------------------------------------------------------- #
def cancel_add_movie_keyboard() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text="❌ Bekor qilish", style=RED))
    return builder.as_markup(resize_keyboard=True)


# ---------------------------------------------------------------------- #
#                        ADMIN -> PREMIUM BOSHQARUVI                      #
# ---------------------------------------------------------------------- #
def premium_control_reply_keyboard() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text="❌ Bekor qilish", style=RED))
    return builder.as_markup(resize_keyboard=True)


def premium_control_inline_keyboard(enabled: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if enabled:
        builder.row(InlineKeyboardButton(text="🔴 O'chirish", callback_data="premium_disable", style=RED))
    else:
        builder.row(InlineKeyboardButton(text="🟢 Yoqish", callback_data="premium_enable", style=GREEN))
    return builder.as_markup()


# ---------------------------------------------------------------------- #
#                  ADMIN -> KANALGA JOYLASH (post tugmasi)                #
# ---------------------------------------------------------------------- #
def post_watch_keyboard(url: str) -> InlineKeyboardMarkup:
    """Kanaldagi postning tagidagi doimiy ko'k 'TOMOSHA QILISH' tugmasi."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="« TOMOSHA QILISH »", url=url, style=BLUE))
    return builder.as_markup()


# ---------------------------------------------------------------------- #
#                 FOYDALANUVCHI -> KINO QIDIRISH / TOP RO'YXATLAR         #
# ---------------------------------------------------------------------- #
def search_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🔥 Top filmlar", callback_data="top:film", style=BLUE))
    builder.row(InlineKeyboardButton(text="📺 Top seriallar", callback_data="top:serial", style=GREEN))
    builder.row(InlineKeyboardButton(text="🧸 Top multfilmlar", callback_data="top:multfilm", style=RED))
    return builder.as_markup()


def top_list_keyboard(items: list, category: str) -> InlineKeyboardMarkup:
    """items: [(movie_id, title), ...] — har bir nom bosiladigan tugma."""
    builder = InlineKeyboardBuilder()
    for movie_id, title in items:
        builder.row(InlineKeyboardButton(text=title, callback_data=f"mv:{movie_id}", style=BLUE))
    builder.row(InlineKeyboardButton(text="🔄 Yangilash", callback_data=f"topr:{category}", style=GREEN))
    return builder.as_markup()


# ---------------------------------------------------------------------- #
#                      KINO OSTIDAGI TUGMALAR (film/multfilm)             #
# ---------------------------------------------------------------------- #
def share_url(deep_link: str, text: str = "🎬 Mana bu kinoni ko'ring!") -> str:
    return "https://t.me/share/url?" + urllib.parse.urlencode({"url": deep_link, "text": text})


def movie_actions_keyboard(more_url: str, deep_link: str) -> InlineKeyboardMarkup:
    """Kino tagida: 'Boshqa filmlar' (kanalga) va katta 'Ulashish' — ikkalasi yashil."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🍿 Boshqa filmlar", url=more_url, style=GREEN))
    builder.row(InlineKeyboardButton(text="↗️ Ulashish", url=share_url(deep_link), style=GREEN))
    return builder.as_markup()


# ---------------------------------------------------------------------- #
#                         SERIAL / ANIME QISMLARI                        #
# ---------------------------------------------------------------------- #
SERIES_PAGE_SIZE = 40   # bir sahifada ko'rsatiladigan qism raqamlari soni
SERIES_ROW_SIZE = 5     # bir qatordagi raqamlar soni


def series_keyboard(movie_id: int, total: int, page: int, deep_link: str) -> InlineKeyboardMarkup:
    """Qizil raqamlar (1 2 3 ...) + pastda uzun ko'k 'Do'stlarga ulashish'."""
    builder = InlineKeyboardBuilder()
    pages = max(1, (total + SERIES_PAGE_SIZE - 1) // SERIES_PAGE_SIZE)
    page = min(max(page, 0), pages - 1)
    start = page * SERIES_PAGE_SIZE + 1
    end = min(total, start + SERIES_PAGE_SIZE - 1)

    buttons = [
        InlineKeyboardButton(text=str(n), callback_data=f"sp:{movie_id}:{n}", style=RED)
        for n in range(start, end + 1)
    ]
    for i in range(0, len(buttons), SERIES_ROW_SIZE):
        builder.row(*buttons[i:i + SERIES_ROW_SIZE])

    if pages > 1:
        nav = []
        if page > 0:
            nav.append(InlineKeyboardButton(
                text="⬅️", callback_data=f"spg:{movie_id}:{page - 1}", style=RED))
        nav.append(InlineKeyboardButton(
            text=f"{page + 1}/{pages}", callback_data="noop", style=RED))
        if page < pages - 1:
            nav.append(InlineKeyboardButton(
                text="➡️", callback_data=f"spg:{movie_id}:{page + 1}", style=RED))
        builder.row(*nav)

    builder.row(InlineKeyboardButton(text="📤 Do'stlarga ulashish", url=share_url(deep_link), style=BLUE))
    return builder.as_markup()


# ---------------------------------------------------------------------- #
#                  ADMIN -> KINO TURI / SERIAL QO'SHISH                  #
# ---------------------------------------------------------------------- #
def movie_category_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🎬 Film", callback_data="mcat:film", style=BLUE),
        InlineKeyboardButton(text="🧸 Multfilm", callback_data="mcat:multfilm", style=BLUE),
    )
    return builder.as_markup()


def serial_done_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="✅ Kino tugadi (saqlash)", callback_data="serial_done", style=BLUE))
    return builder.as_markup()
