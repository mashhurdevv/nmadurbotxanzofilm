# main.py
# Kino bot - asosiy fayl. Barcha handlerlar shu yerda ro'yxatdan o'tkaziladi.

import asyncio
import html
import logging
import datetime
import re

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode, ChatMemberStatus
from aiogram.filters import CommandStart, CommandObject, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, CallbackQuery, ReplyKeyboardRemove, ChatJoinRequest, MessageEntity
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

import config as _cfg
from config import (
    BOT_TOKEN, ADMIN_IDS, CARD_NUMBER, CARD_HOLDER,
    PREMIUM_PRICE, PREMIUM_DURATION_HOURS
)

# Yangi sozlamalar eski config.py da bo'lmasa ham bot ishlayveradi
PREMIUM_DURATION_DAYS = getattr(_cfg, "PREMIUM_DURATION_DAYS", max(1, PREMIUM_DURATION_HOURS // 24))
POST_CHANNEL_ID = getattr(_cfg, "POST_CHANNEL_ID", None)
MORE_MOVIES_URL = getattr(_cfg, "MORE_MOVIES_URL", "https://t.me/xanzotv")
from database import Database
from states import (
    UserStates, AdminChannelStates, AdminMovieStates,
    AdminBroadcastStates, AdminManualPaymentStates, AdminPostStates, AdminSerialStates
)
import buttons as kb

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())
router = Router()
dp.include_router(router)

db = Database()

# Muvaqqat holatda kino qo'shish ma'lumotlarini saqlash uchun FSM data ishlatiladi
# Kanal qo'shish jarayonida ham xuddi shunday


# ------------------------------------------------------------------------- #
#                               YORDAMCHI FUNKSIYALAR                       #
# ------------------------------------------------------------------------- #
def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


async def check_subscription_detailed(user_id: int) -> tuple[bool, bool]:
    """
    Foydalanuvchi barcha majburiy kanallarga obuna bo'lganini tekshiradi.

    Har bir kanal uchun avval haqiqiy a'zolik (get_chat_member) tekshiriladi.
    A'zo bo'lmasa — bu "pending" (hali tasdiqlanmagan Join Request) holati bo'lishi mumkin,
    shu sababli get_chat_member natijasiga suyanmasdan, bazadagi join_requests jadvalidan
    o'sha foydalanuvchi shu kanalga so'rov yuborganini tekshiramiz. Bot hech qachon
    so'rovni o'zi qabul qilmaydi (approve_chat_join_request ISHLATILMAYDI).

    Qaytaradi: (barcha_shartlar_bajarildimi, hech_bo'lmasa_bitta_kanal_join_request_orqali_o'tdimi)
    """
    channels = await db.get_channels()
    if not channels:
        return True, False

    any_via_request = False

    for ch in channels:
        _id, name, username, channel_id, invite_link, is_zayavka = ch
        # channel_id bazada matn (str) sifatida saqlanadi, lekin Telegram API
        # butun sonli ID larni raqam (int) shaklida kutadi — shu sababli o'giramiz.
        try:
            chat_id_value = int(channel_id)
        except (TypeError, ValueError):
            chat_id_value = channel_id

        is_member = False
        try:
            member = await bot.get_chat_member(chat_id=chat_id_value, user_id=user_id)
            if member.status in (
                ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR
            ):
                is_member = True
        except Exception as e:
            # Bu yerga tushish odatiy holat: foydalanuvchi hali a'zo emas yoki
            # so'rovi hali "pending" holatida — shuning uchun xatoni faqat log qilamiz,
            # pastda join_requests jadvalidan tekshiramiz.
            logger.info(f"get_chat_member natija bermadi (ehtimol pending): user={user_id}, kanal={name}: {e}")

        if is_member:
            continue

        # Haqiqiy a'zo emas — bazada shu kanalga Join Request yuborganini tekshiramiz
        has_request = await db.has_join_request(user_id, channel_id)
        if has_request:
            any_via_request = True
            continue

        logger.info(f"Obuna emas: user={user_id}, kanal={name} ({channel_id})")
        return False, any_via_request

    return True, any_via_request


async def check_subscription(user_id: int) -> bool:
    """check_subscription_detailed ning oddiy (faqat bool qaytaradigan) qisqartmasi."""
    subscribed, _ = await check_subscription_detailed(user_id)
    return subscribed


@router.chat_join_request()
async def handle_chat_join_request(update: ChatJoinRequest):
    """
    Bot admin bo'lgan va bazada ro'yxatdan o'tgan (majburiy obuna yoki zayavka) kanallarga
    kelgan Join Request'larni FAQAT bazaga (join_requests jadvaliga) yozib qo'yadi.

    MUHIM: bot bu so'rovni HECH QACHON avtomatik qabul qilmaydi —
    approve_chat_join_request() BU YERDA UMUMAN ISHLATILMAYDI.
    Foydalanuvchi kanalning o'zida "pending" (kutilayotgan so'rov) holatida qolaveradi,
    admin ham qo'lda tasdiqlamaydi. Faqat botning ichki "obuna tekshiruvi" uchun
    bu so'rov "dalil" sifatida bazada saqlanadi.
    """
    channels = await db.get_channels()
    registered_ids = {str(ch[3]) for ch in channels}

    if str(update.chat.id) not in registered_ids:
        # Bu kanal bizning bazamizda ro'yxatdan o'tmagan — tegmaymiz
        return

    await db.save_join_request(update.from_user.id, str(update.chat.id))
    logger.info(f"Join so'rov bazaga saqlandi (approve qilinmadi): user={update.from_user.id}, chat={update.chat.id}")


async def send_subscription_request(chat_id: int):
    channels = await db.get_channels()
    text = (
        "👋 <b>Assalomu alaykum, hurmatli obunachi!</b>\n\n"
        "🚫 <b>Botdan to'liq foydalanish uchun quyidagi kanallarga obuna bo'ling!</b>"
    )
    await bot.send_message(chat_id, text, reply_markup=kb.subscription_keyboard(channels))


PRICE_TEXT = f"{PREMIUM_PRICE:,}".replace(",", " ")  # 10 000
DURATION_TEXT = f"{PREMIUM_DURATION_DAYS} kun"


async def send_premium_offer(chat_id: int):
    text = (
        f"💎 <b>ATIGA {PRICE_TEXT} SO'M</b>\n\n"
        "Hurmatli obunachi, kinolarni ko'rish uchun oldin premium sotib olishingiz kerak. "
        "Premium sotib olsangiz, xohlagancha kino ko'rish imkoniga ega bo'lasiz — barchasi 4K formatda! 🎬\n\n"
        f"⏳ Premium muddati: <b>{DURATION_TEXT}</b>\n"
        f"💰 Premium narxi: <b>{PRICE_TEXT} so'm</b>\n\n"
        "To'lov qilish uchun quyidagi tugmani bosing 👇🏻"
    )
    await bot.send_message(chat_id, text, reply_markup=kb.premium_offer_keyboard())


async def send_payment_details(chat_id: int):
    text = (
        "💳 <b>PREMIUM SOTIB OLISH</b>\n\n"
        f"💳 Karta raqam: <code>{CARD_NUMBER}</code>\n"
        f"👤 Karta egasi: <b>{CARD_HOLDER}</b>\n"
        f"💰 To'lov summasi: <b>{PRICE_TEXT} so'm</b>\n\n"
        "⚠️ To'lov qilgach, chek rasmini botga yuboring!"
    )
    await bot.send_message(chat_id, text, reply_markup=kb.premium_payment_keyboard())


async def send_main_menu(chat_id: int, extra_text: str = ""):
    text = extra_text or "✅ Xush kelibsiz! Quyidagi menyudan foydalanishingiz mumkin."
    await bot.send_message(chat_id, text, reply_markup=kb.user_main_menu())


async def user_has_access(user_id: int) -> bool:
    """Premium tizimi o'chirilgan bo'lsa (ochiq/tekin holat) yoki foydalanuvchida faol premium bo'lsa True."""
    if not await db.get_premium_enabled():
        return True
    return await db.is_premium(user_id)


async def try_send_pending_code(chat_id: int, user_id: int):
    """Deep-link orqali kelgan (yoki premium/tolov kutilayotgan) kino kodini yuboradi, mavjud bo'lsa."""
    code = await db.get_pending_code(user_id)
    if not code:
        return
    await db.clear_pending_code(user_id)
    movie = await db.get_movie_by_code(code)
    if movie:
        await send_movie_to_user(chat_id, movie)
    else:
        await bot.send_message(chat_id, f"❌ <b>{code}</b> kodli kino topilmadi.")


def format_remaining(until_dt: datetime.datetime) -> str:
    delta = until_dt - datetime.datetime.now()
    if delta.total_seconds() <= 0:
        return "Premium muddati tugagan"
    total_seconds = int(delta.total_seconds())
    days = total_seconds // 86400
    hours = (total_seconds % 86400) // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    return f"{days} kun {hours} soat {minutes} daqiqa {seconds} soniya"


# ------------------------------------------------------------------------- #
#                                    /start                                 #
# ------------------------------------------------------------------------- #
@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, command: CommandObject):
    await state.clear()
    user = message.from_user
    deep_link_code = command.args.strip() if command.args else None

    if is_admin(user.id):
        await db.add_user(user.id, user.username or "", user.full_name)
        await message.answer(
            f"👑 Xush kelibsiz, Admin <b>{user.full_name}</b>!\n\nAdmin panelga xush kelibsiz.",
            reply_markup=kb.admin_main_menu()
        )
        return

    await db.add_user(user.id, user.username or "", user.full_name)

    # Deep-link orqali (masalan https://t.me/BotUsername?start=7112) kod bilan kirilgan bo'lsa saqlab qo'yamiz
    if deep_link_code:
        await db.set_pending_code(user.id, deep_link_code)

    subscribed = await check_subscription(user.id)
    if not subscribed:
        await send_subscription_request(message.chat.id)
        return

    if await user_has_access(user.id):
        await send_main_menu(message.chat.id, "✅ Sizda faol premium mavjud. Kino ko'rishdan bahramand bo'ling!")
        await try_send_pending_code(message.chat.id, user.id)
    else:
        await send_premium_offer(message.chat.id)


# ------------------------------------------------------------------------- #
#                         OBUNA TEKSHIRISH (CALLBACK)                       #
# ------------------------------------------------------------------------- #
@router.callback_query(F.data == "check_sub")
async def cb_check_sub(call: CallbackQuery):
    subscribed, via_request = await check_subscription_detailed(call.from_user.id)
    if not subscribed:
        await call.answer("❌ Avval kanalga Join Request yuboring.", show_alert=True)
        return

    await call.message.delete()

    if via_request:
        await bot.send_message(
            call.message.chat.id,
            "✅ Kanalga qo'shilish so'rovingiz qabul qilindi. Endi davom etishingiz mumkin."
        )

    if await user_has_access(call.from_user.id):
        await send_main_menu(call.message.chat.id, "✅ Sizda faol premium mavjud. Kino ko'rishdan bahramand bo'ling!")
        await try_send_pending_code(call.message.chat.id, call.from_user.id)
    else:
        await send_premium_offer(call.message.chat.id)
    await call.answer()


# ------------------------------------------------------------------------- #
#                            PREMIUM SOTIB OLISH OQIMI                      #
# ------------------------------------------------------------------------- #
@router.callback_query(F.data == "premium_buy")
async def cb_premium_buy(call: CallbackQuery, state: FSMContext):
    await call.message.delete()
    await send_payment_details(call.message.chat.id)
    await state.set_state(UserStates.waiting_payment_check)
    await call.answer()


@router.callback_query(F.data == "premium_back")
async def cb_premium_back(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.delete()
    await send_premium_offer(call.message.chat.id)
    await call.answer()


@router.message(UserStates.waiting_payment_check, F.photo)
async def process_payment_check(message: Message, state: FSMContext):
    photo_id = message.photo[-1].file_id
    payment_id = await db.create_payment(message.from_user.id, photo_id)
    await state.clear()

    await message.answer(
        "✅ Chekingiz qabul qilindi va admin tekshiruviga yuborildi. "
        "Tasdiqlangach sizga xabar beramiz."
    )

    caption = (
        "🧾 <b>Yangi to'lov cheki</b>\n\n"
        f"👤 Foydalanuvchi: {message.from_user.full_name}\n"
        f"🆔 ID: <code>{message.from_user.id}</code>\n"
        f"👤 Username: @{message.from_user.username or '—'}\n"
        f"🕐 Vaqt: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_photo(
                admin_id, photo_id, caption=caption,
                reply_markup=kb.check_confirm_keyboard(payment_id)
            )
        except Exception as e:
            logger.warning(f"Adminga chek yuborishda xato: {e}")

    zayavka_channels = await db.get_zayavka_channels()
    for zayavka_channel in zayavka_channels:
        try:
            await bot.send_photo(
                zayavka_channel, photo_id, caption=caption,
                reply_markup=kb.check_confirm_keyboard(payment_id)
            )
        except Exception as e:
            logger.warning(f"Zayavka kanaliga chek yuborishda xato: {e}")


@router.message(UserStates.waiting_payment_check)
async def process_payment_check_invalid(message: Message):
    await message.answer("⚠️ Iltimos, to'lov chekining <b>rasmini</b> yuboring.")


# ------------------------------------------------------------------------- #
#                    ADMIN: CHEKNI TASDIQLASH / BEKOR QILISH                #
# ------------------------------------------------------------------------- #
@router.callback_query(F.data.startswith("check_approve:"))
async def cb_check_approve(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return await call.answer("Ruxsat yo'q", show_alert=True)

    payment_id = int(call.data.split(":")[1])
    payment = await db.get_payment(payment_id)
    if not payment or payment[3] != "pending":
        await call.answer("Bu chek allaqachon ko'rib chiqilgan.", show_alert=True)
        return

    user_id = payment[1]
    until_str = await db.grant_premium(user_id, source="check", amount=PREMIUM_PRICE)
    await db.resolve_payment(payment_id, "approved")

    await call.message.edit_caption(
        caption=call.message.caption + "\n\n✅ <b>TASDIQLANDI</b>",
        reply_markup=None
    )
    await call.answer("Premium berildi ✅")

    try:
        await bot.send_message(
            user_id,
            f"🎉 To'lovingiz tasdiqlandi! Sizga <b>{DURATION_TEXT}lik</b> premium berildi.\n"
            f"⏳ Premium tugash vaqti: <b>{until_str}</b>\n\n"
            "Endi barcha kinolardan bemalol foydalanishingiz mumkin!",
            reply_markup=kb.user_main_menu()
        )
        await try_send_pending_code(user_id, user_id)
    except Exception as e:
        logger.warning(f"Foydalanuvchiga xabar yuborishda xato: {e}")


@router.callback_query(F.data.startswith("check_reject:"))
async def cb_check_reject(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return await call.answer("Ruxsat yo'q", show_alert=True)

    payment_id = int(call.data.split(":")[1])
    payment = await db.get_payment(payment_id)
    if not payment or payment[3] != "pending":
        await call.answer("Bu chek allaqachon ko'rib chiqilgan.", show_alert=True)
        return

    user_id = payment[1]
    await db.resolve_payment(payment_id, "rejected")

    await call.message.edit_caption(
        caption=call.message.caption + "\n\n❌ <b>BEKOR QILINDI</b>",
        reply_markup=None
    )
    await call.answer("Chek bekor qilindi")

    try:
        await bot.send_message(
            user_id,
            "❌ To'lovingiz bekor qilindi. Iltimos, qayta to'lov qiling.",
            reply_markup=kb.premium_offer_keyboard()
        )
    except Exception as e:
        logger.warning(f"Foydalanuvchiga xabar yuborishda xato: {e}")


# ------------------------------------------------------------------------- #
#                     FOYDALANUVCHI ASOSIY MENYU HANDLERLARI                #
# ------------------------------------------------------------------------- #
async def require_access(message: Message) -> bool:
    """
    Har bir foydalanuvchi menyu tugmasidan foydalanishdan oldin ikkalasini ham tekshiradi:
    1) Majburiy kanal(lar)ga obuna bo'lganmi (yangi qo'shilgan kanal bo'lsa ham shu yerda tutiladi)
    2) Premium (yoki premium tizimi o'chirilgan bo'lsa — ochiq/tekin holat)

    Shartlardan biri bajarilmasa, reply klaviatura ("tugmalar") olib tashlanadi va
    foydalanuvchi qayta tegishli bosqichdan (obuna yoki premium) o'tishi so'raladi.
    """
    if not await check_subscription(message.from_user.id):
        await message.answer(
            "🔒 Yangi majburiy obuna kanali qo'shildi (yoki hali barcha kanallarga obuna emassiz). "
            "Davom etish uchun avval quyidagi kanal(lar)ga obuna bo'ling.",
            reply_markup=ReplyKeyboardRemove()
        )
        await send_subscription_request(message.chat.id)
        return False

    if not await user_has_access(message.from_user.id):
        await message.answer(
            "🔒 Bu bo'limdan foydalanish uchun avval premium sotib oling.",
            reply_markup=ReplyKeyboardRemove()
        )
        await send_premium_offer(message.chat.id)
        return False

    return True


MENU_TEXTS = {"🔍 Kino qidirish", "🎲 Random kino", "⏳ Premium muddati", "🆕 Bugungi kinolar"}

CATEGORY_NAMES = {
    "film": ("🔥", "filmlar"),
    "serial": ("📺", "seriallar"),
    "multfilm": ("🧸", "multfilmlar"),
}

_bot_username = None


async def get_bot_username() -> str:
    global _bot_username
    if not _bot_username:
        _bot_username = (await bot.get_me()).username
    return _bot_username


async def movie_deep_link(code: str) -> str:
    username = await get_bot_username()
    if re.fullmatch(r"[A-Za-z0-9_-]{1,64}", code or ""):
        return f"https://t.me/{username}?start={code}"
    return f"https://t.me/{username}"


def clean_title(description: str, code: str) -> str:
    """Tavsifning birinchi qatorini (HTML teglarsiz) tugma nomi sifatida oladi."""
    text = html.unescape(re.sub(r"<[^>]+>", "", description or ""))
    for line in text.splitlines():
        line = line.strip()
        if line:
            return line if len(line) <= 40 else line[:39] + "…"
    return f"Kino {code}"


async def callback_access(call: CallbackQuery) -> bool:
    """Inline tugmalar uchun: obuna va premium shartlarini tekshiradi."""
    uid = call.from_user.id
    if is_admin(uid):
        return True
    if not await check_subscription(uid):
        await call.answer("🔒 Avval kanallarga obuna bo'ling. /start bosing.", show_alert=True)
        return False
    if not await user_has_access(uid):
        await call.answer("🔒 Avval premium sotib oling. /start bosing.", show_alert=True)
        return False
    return True


@router.message(F.text == "🔍 Kino qidirish")
async def user_search_movie(message: Message, state: FSMContext):
    if is_admin(message.from_user.id):
        return
    if not await require_access(message):
        return
    await message.answer(
        "🔍 <b>Kino qidirish</b>\n\n"
        "🔢 Kino kodini yuboring yoki quyidagi bo'limlardan birini tanlang 👇",
        reply_markup=kb.search_menu_keyboard()
    )
    await state.set_state(UserStates.waiting_movie_code)


@router.message(UserStates.waiting_movie_code, F.text, ~F.text.in_(MENU_TEXTS))
async def process_movie_code(message: Message, state: FSMContext):
    if not await require_access(message):
        await state.clear()
        return

    code = message.text.strip()
    movie = await db.get_movie_by_code(code)
    await state.clear()

    if not movie:
        await message.answer("❌ Bunday kodli kino topilmadi.")
        return

    await send_movie_to_user(message.chat.id, movie)


async def build_top_items(category: str) -> list:
    rows = await db.get_top_movies(category, 10)
    return [(r[0], f"{i}. {clean_title(r[2], r[1])}") for i, r in enumerate(rows, start=1)]


def top_list_text(category: str, count: int) -> str:
    icon, name = CATEGORY_NAMES[category]
    return f"{icon} <b>Top {count} ta {name}</b>\n\n👇 Ko'rmoqchi bo'lganingizni tanlang:"


@router.callback_query(F.data.startswith("top:"))
async def cb_top_list(call: CallbackQuery):
    category = call.data.split(":", 1)[1]
    if category not in CATEGORY_NAMES:
        return await call.answer()
    if not await callback_access(call):
        return
    items = await build_top_items(category)
    if not items:
        await call.answer("😔 Hozircha bu bo'limda hech narsa yo'q.", show_alert=True)
        return
    await call.message.answer(
        top_list_text(category, len(items)),
        reply_markup=kb.top_list_keyboard(items, category)
    )
    await call.answer()


@router.callback_query(F.data.startswith("topr:"))
async def cb_top_refresh(call: CallbackQuery):
    category = call.data.split(":", 1)[1]
    if category not in CATEGORY_NAMES:
        return await call.answer()
    if not await callback_access(call):
        return
    items = await build_top_items(category)
    if not items:
        await call.answer("😔 Hozircha bu bo'limda hech narsa yo'q.", show_alert=True)
        return
    try:
        await call.message.edit_text(
            top_list_text(category, len(items)),
            reply_markup=kb.top_list_keyboard(items, category)
        )
        await call.answer("🔄 Yangilandi")
    except TelegramBadRequest:
        await call.answer("Boshqa variant yo'q, ro'yxat o'zgarmadi.")


@router.callback_query(F.data.startswith("mv:"))
async def cb_open_movie(call: CallbackQuery):
    if not await callback_access(call):
        return
    try:
        movie_id = int(call.data.split(":")[1])
    except ValueError:
        return await call.answer()
    movie = await db.get_movie_by_id(movie_id)
    if not movie:
        await call.answer("❌ Bu kino topilmadi.", show_alert=True)
        return
    await send_movie_to_user(call.message.chat.id, movie)
    await call.answer()


@router.callback_query(F.data.startswith("sp:"))
async def cb_series_part(call: CallbackQuery):
    if not await callback_access(call):
        return
    try:
        _, movie_id, part_no = call.data.split(":")
        movie_id, part_no = int(movie_id), int(part_no)
    except ValueError:
        return await call.answer()
    movie = await db.get_movie_by_id(movie_id)
    if not movie:
        await call.answer("❌ Bu serial topilmadi.", show_alert=True)
        return
    await send_movie_to_user(call.message.chat.id, movie, part_no=part_no)
    await call.answer()


@router.callback_query(F.data.startswith("spg:"))
async def cb_series_page(call: CallbackQuery):
    if not await callback_access(call):
        return
    try:
        _, movie_id, page = call.data.split(":")
        movie_id, page = int(movie_id), int(page)
    except ValueError:
        return await call.answer()
    movie = await db.get_movie_by_id(movie_id)
    if not movie:
        return await call.answer()
    total = await db.count_parts(movie_id)
    deep_link = await movie_deep_link(movie[1])
    try:
        await call.message.edit_reply_markup(
            reply_markup=kb.series_keyboard(movie_id, total, page, deep_link)
        )
    except TelegramBadRequest:
        pass
    await call.answer()


@router.callback_query(F.data == "noop")
async def cb_noop(call: CallbackQuery):
    await call.answer()


async def send_media_message(chat_id: int, file_id: str, content_type: str, caption: str, markup):
    sender = bot.send_document if content_type == "document" else bot.send_video
    try:
        await sender(chat_id, file_id, caption=caption, reply_markup=markup)
    except TelegramBadRequest as e:
        # Izoh juda uzun bo'lsa va hokazo: media alohida, izoh alohida yuboriladi
        logger.warning(f"Media izoh bilan yuborilmadi, ajratib yuborilmoqda: {e}")
        await sender(chat_id, file_id)
        await bot.send_message(chat_id, caption or "🎬", reply_markup=markup)


async def send_movie_to_user(chat_id: int, movie, part_no: int = 1):
    """
    Kinoni foydalanuvchiga yuboradi.
    - Film / multfilm: tagida yashil "Boshqa filmlar" va "Ulashish" tugmalari.
    - Serial / anime: tagida qizil qism raqamlari va ko'k "Do'stlarga ulashish".
    """
    movie_id, code, description, file_id, content_type, added_at, category = movie
    caption = description or ""
    try:
        deep_link = await movie_deep_link(code)

        if category == "serial":
            total = await db.count_parts(movie_id)
            if total > 0:
                part_no = min(max(part_no, 1), total)
                file_id, content_type = await db.get_part(movie_id, part_no)
                caption = f"{caption}\n\n📺 <b>{part_no}-qism</b>"
                page = (part_no - 1) // kb.SERIES_PAGE_SIZE
                markup = kb.series_keyboard(movie_id, total, page, deep_link)
                await send_media_message(chat_id, file_id, content_type, caption, markup)
                return

        markup = kb.movie_actions_keyboard(MORE_MOVIES_URL, deep_link)
        await send_media_message(chat_id, file_id, content_type, caption, markup)
    except Exception as e:
        logger.warning(f"Kino yuborishda xato: {e}")
        await bot.send_message(chat_id, "⚠️ Kinoni yuborishda xatolik yuz berdi.")


@router.message(F.text == "⏳ Premium muddati")
async def user_premium_time(message: Message):
    if is_admin(message.from_user.id):
        return
    if not await require_access(message):
        return

    if not await db.get_premium_enabled():
        await message.answer("🟡 Hozir premium tizimi o'chirilgan — barcha kinolar bepul!")
        return

    until_dt = await db.get_premium_until(message.from_user.id)
    if not until_dt:
        await message.answer("🔒 Sizda faol premium mavjud emas.")
        return

    delta = until_dt - datetime.datetime.now()
    total_seconds = max(0, int(delta.total_seconds()))
    days = total_seconds // 86400
    if days >= 1:
        remaining = f"{days} kun"
    else:
        remaining = f"{total_seconds // 3600} soat {(total_seconds % 3600) // 60} daqiqa"

    await message.answer(
        f"🆔 <b>ID:</b> <code>{message.from_user.id}</code>\n"
        f"👤 <b>Ism:</b> {html.escape(message.from_user.full_name)}\n"
        f"💎 <b>Status:</b> Premium Obunachi ✅\n"
        f"⏰ <b>Qolgan muddat:</b> {remaining}\n"
        f"📅 <b>Tugash sanasi:</b> {until_dt.strftime('%Y-%m-%d %H:%M:%S')}"
    )


@router.message(F.text == "🎲 Random kino")
async def user_random_movie(message: Message):
    if is_admin(message.from_user.id):
        return
    if not await require_access(message):
        return
    movie = await db.get_random_movie()
    if not movie:
        await message.answer("😔 Hozircha botda hech qanday kino mavjud emas.")
        return
    await send_movie_to_user(message.chat.id, movie)


@router.message(F.text == "🆕 Bugungi kinolar")
async def user_today_movies(message: Message):
    if is_admin(message.from_user.id):
        return
    if not await require_access(message):
        return
    movies = await db.get_today_movies()
    if not movies:
        await message.answer("📭 Bugun hali yangi kino qo'shilmagan.")
        return
    for movie in movies:
        await send_movie_to_user(message.chat.id, movie)


# ------------------------------------------------------------------------- #
#                             ADMIN: BEKOR QILISH                           #
# ------------------------------------------------------------------------- #
@router.message(F.text == "❌ Bekor qilish")
async def admin_cancel_action(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.clear()
    await message.answer("❌ Amal bekor qilindi.", reply_markup=kb.admin_main_menu())


# ------------------------------------------------------------------------- #
#                          ADMIN: REKLAMA YUBORISH                          #
# ------------------------------------------------------------------------- #
@router.message(F.text == "📢 Reklama yuborish")
async def admin_broadcast_start(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await message.answer(
        "📢 Yubormoqchi bo'lgan reklama xabarini yuboring (matn, rasm, video, sticker va h.k.):",
        reply_markup=kb.admin_cancel_keyboard()
    )
    await state.set_state(AdminBroadcastStates.waiting_content)


@router.message(AdminBroadcastStates.waiting_content)
async def admin_broadcast_process(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.clear()

    user_ids = await db.get_all_user_ids()
    sent, failed = 0, 0

    status_msg = await message.answer("⏳ Xabar yuborilmoqda...")

    for uid in user_ids:
        try:
            await bot.copy_message(chat_id=uid, from_chat_id=message.chat.id, message_id=message.message_id)
            sent += 1
        except TelegramForbiddenError:
            failed += 1
            await db.mark_user_left(uid)
        except Exception as e:
            failed += 1
            logger.warning(f"Reklama yuborishda xato ({uid}): {e}")
        await asyncio.sleep(0.05)  # Telegram limitlariga tushib qolmaslik uchun

    await status_msg.edit_text(
        f"✅ Reklama yuborish yakunlandi!\n\n"
        f"📨 Yuborildi: <b>{sent}</b> ta foydalanuvchiga\n"
        f"🚫 Yuborilmadi: <b>{failed}</b> ta foydalanuvchiga"
    )
    await message.answer("Admin panelga qaytdingiz.", reply_markup=kb.admin_main_menu())


# ------------------------------------------------------------------------- #
#                              ADMIN: STATISTIKA                            #
# ------------------------------------------------------------------------- #
def build_stats_text(stats: dict) -> str:
    return (
        "📊 <b>Statistika</b> (so'nggi 30 kunlik davr)\n\n"
        f"👥 Jami obunachilar: <b>{stats['total_users']}</b>\n"
        f"🟢 Bu davrda qo'shilgan: <b>{stats['new_users']}</b>\n"
        f"🔴 Bu davrda chiqib ketgan: <b>{stats['left_users']}</b>\n"
        f"🎬 Bu davrda qo'shilgan kinolar: <b>{stats['movies_added']}</b>\n"
        f"💎 Bu davrda sotib olingan premiumlar: <b>{stats['premium_bought']}</b>\n"
        f"💰 Bu davr foydasi: <b>{stats['revenue']} so'm</b>\n\n"
        f"🕐 Davr boshlanishi: {stats['period_start']}"
    )


@router.message(F.text == "📊 Statistika")
async def admin_statistics(message: Message):
    if not is_admin(message.from_user.id):
        return
    text = await db.get_cached_stats_text(build_stats_text)
    await message.answer(text)


# ------------------------------------------------------------------------- #
#                       ADMIN: OBUNA KANAL BOSHQARUVI                       #
# ------------------------------------------------------------------------- #
@router.message(F.text == "➕ Obuna qo'shish")
async def admin_channels_menu(message: Message):
    if not is_admin(message.from_user.id):
        return
    await message.answer("📡 Obuna kanallarni boshqarish:", reply_markup=kb.admin_channel_menu())


@router.callback_query(F.data == "admin_back_menu")
async def cb_admin_back_menu(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return await call.answer()
    await state.clear()
    try:
        await call.message.edit_text("📡 Obuna kanallarni boshqarish:", reply_markup=kb.admin_channel_menu())
    except TelegramBadRequest:
        await call.message.answer("📡 Obuna kanallarni boshqarish:", reply_markup=kb.admin_channel_menu())
    await call.answer()


@router.callback_query(F.data == "ch_add")
async def cb_channel_add(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return await call.answer()
    await call.message.answer("📝 Kanal nomini kiriting:", reply_markup=kb.admin_cancel_keyboard())
    await state.set_state(AdminChannelStates.waiting_channel_name)
    await call.answer()


@router.message(AdminChannelStates.waiting_channel_name, F.text)
async def process_channel_name(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.update_data(channel_name=message.text.strip())
    await message.answer(
        "🔗 Kanal usernamesini kiriting (masalan: @mychannel).\n\n"
        "Agar kanal <b>yopiq (private)</b> bo'lsa va username'i bo'lmasa, shunchaki <code>-</code> belgisini yuboring — "
        "bot o'zi taklif havolasini (invite link) yaratadi."
    )
    await state.set_state(AdminChannelStates.waiting_channel_username)


@router.message(AdminChannelStates.waiting_channel_username, F.text)
async def process_channel_username(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    raw = message.text.strip()
    username = None if raw in ("-", "—", "yo'q", "yoq", "yoʻq") else raw
    await state.update_data(channel_username=username)
    await message.answer("🆔 Kanal ID sini kiriting (masalan: -1001234567890):")
    await state.set_state(AdminChannelStates.waiting_channel_id)


@router.message(AdminChannelStates.waiting_channel_id, F.text)
async def process_channel_id(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    channel_id = message.text.strip()
    data = await state.get_data()
    name = data.get("channel_name")
    username = data.get("channel_username")

    try:
        chat_id_value = int(channel_id)
    except ValueError:
        chat_id_value = channel_id

    try:
        bot_member = await bot.get_chat_member(chat_id=chat_id_value, user_id=bot.id)
        if bot_member.status not in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR):
            await message.answer(
                "⚠️ Botni ushbu kanalda <b>admin</b> qiling va qaytadan urinib ko'ring."
            )
            return
    except Exception as e:
        await message.answer(
            f"⚠️ Kanalni tekshirib bo'lmadi. ID to'g'riligini va bot admin ekanini tekshiring.\nXato: {e}"
        )
        return

    if username:
        # Ochiq (public) kanal — username orqali oddiy havola
        invite_link = f"https://t.me/{username.lstrip('@')}"
    else:
        # Yopiq (private) kanal — bot o'zi darhol qo'shiladigan taklif havolasini yaratadi
        try:
            invite = await bot.create_chat_invite_link(chat_id=chat_id_value)
            invite_link = invite.invite_link
        except Exception as e:
            await message.answer(
                "⚠️ Kanal yopiq (private) ko'rinadi, lekin botga taklif havolasi yaratish huquqi yo'q.\n"
                "Botga ushbu kanalda <b>\"Foydalanuvchilarni taklif qilish\" (Invite Users via Link)</b> "
                f"huquqini bering va qaytadan urinib ko'ring.\nXato: {e}"
            )
            return

    await db.add_channel(name, username, channel_id, invite_link=invite_link, is_zayavka=0)
    await state.clear()
    await message.answer(
        f"✅ Kanal muvaffaqiyatli qo'shildi!\n\n📛 Nomi: {name}\n"
        f"🔗 {'Username: ' + username if username else 'Taklif havolasi: ' + invite_link}\n🆔 ID: {channel_id}",
        reply_markup=kb.admin_main_menu()
    )


@router.callback_query(F.data == "zayavka_add")
async def cb_zayavka_add(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return await call.answer()
    await call.message.answer(
        "📝 Zayavka kanal nomini kiriting:",
        reply_markup=kb.admin_cancel_keyboard()
    )
    await state.set_state(AdminChannelStates.waiting_zayavka_name)
    await call.answer()


@router.message(AdminChannelStates.waiting_zayavka_name, F.text)
async def process_zayavka_name(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.update_data(zayavka_name=message.text.strip())
    await message.answer(
        "🔗 Endi zayavka kanal havolasini kiriting (masalan: https://t.me/+AbCdEf123).\n\n"
        "Havolani Telegram'ning o'zidan (kanal → Invite Links) nusxalab oling. Havola \"so'rov orqali "
        "qo'shilish\" (Request Admin Approval) rejimida bo'lsin — bot ushbu so'rovlarni "
        "<b>hech qachon o'zi qabul qilmaydi</b>, faqat obuna tekshiruvi uchun bazaga yozib qo'yadi."
    )
    await state.set_state(AdminChannelStates.waiting_zayavka_link)


@router.message(AdminChannelStates.waiting_zayavka_link, F.text)
async def process_zayavka_link(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    link = message.text.strip()
    if not link.startswith("http"):
        await message.answer("⚠️ Havola https://t.me/... shaklida bo'lishi kerak. Qaytadan kiriting:")
        return
    await state.update_data(zayavka_link=link)
    await message.answer("🆔 Endi zayavka kanal ID sini kiriting (masalan: -1001234567890):")
    await state.set_state(AdminChannelStates.waiting_zayavka_channel_id)


@router.message(AdminChannelStates.waiting_zayavka_channel_id, F.text)
async def process_zayavka_channel_id(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    channel_id = message.text.strip()
    data = await state.get_data()
    invite_link = data.get("zayavka_link")
    name = data.get("zayavka_name") or "Zayavka kanal"

    try:
        chat_id_value = int(channel_id)
    except ValueError:
        chat_id_value = channel_id

    try:
        bot_member = await bot.get_chat_member(chat_id=chat_id_value, user_id=bot.id)
        if bot_member.status not in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR):
            await message.answer(
                "⚠️ Botni ushbu zayavka kanalida <b>admin</b> qiling va qaytadan urinib ko'ring."
            )
            return
    except Exception as e:
        await message.answer(
            f"⚠️ Kanalni tekshirib bo'lmadi. ID to'g'riligini va bot admin ekanini tekshiring.\nXato: {e}"
        )
        return

    await db.add_channel(name, None, channel_id, invite_link=invite_link, is_zayavka=1)
    await state.clear()
    await message.answer(
        f"✅ Zayavka kanal muvaffaqiyatli qo'shildi!\n\n📛 Nomi: {name}\n🔗 Havola: {invite_link}\n🆔 ID: {channel_id}\n\n"
        "Endi bu kanal ham majburiy obuna ro'yxatiga qo'shildi (foydalanuvchi obuna bo'lmasa, "
        "\"obuna bo'ling\" deb so'raladi) va barcha to'lov cheklari ushbu kanalga ham yuboriladi.\n\n"
        "🔒 Foydalanuvchi ushbu havola orqali so'rov yuborsa, bot buni faqat bazaga yozib qo'yadi "
        "(<b>approve qilinmaydi</b>) va \"✅ Tekshirish\" bosilganda dalil sifatida ishlatadi.",
        reply_markup=kb.admin_main_menu()
    )


@router.callback_query(F.data == "ch_del")
async def cb_channel_del(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return await call.answer()
    channels = await db.get_channels()
    if not channels:
        await call.answer("Hozircha hech qanday kanal mavjud emas.", show_alert=True)
        return
    await call.message.edit_text(
        "🗑 O'chirmoqchi bo'lgan kanalni tanlang:",
        reply_markup=kb.admin_channel_delete_list(channels)
    )
    await call.answer()


@router.callback_query(F.data.startswith("ch_del_select:"))
async def cb_channel_del_select(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return await call.answer()
    channel_db_id = int(call.data.split(":")[1])
    channel = await db.get_channel(channel_db_id)
    if not channel:
        await call.answer("Kanal topilmadi.", show_alert=True)
        return
    await call.message.edit_text(
        f"🗑 <b>{channel[1]}</b> kanalini o'chirmoqchimisiz?",
        reply_markup=kb.admin_channel_delete_confirm(channel_db_id)
    )
    await call.answer()


@router.callback_query(F.data.startswith("ch_del_confirm:"))
async def cb_channel_del_confirm(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return await call.answer()
    channel_db_id = int(call.data.split(":")[1])
    await db.remove_channel(channel_db_id)
    await call.message.edit_text("✅ Kanal o'chirildi.", reply_markup=kb.admin_back_menu_keyboard())
    await call.answer()


@router.callback_query(F.data == "ch_del_cancel")
async def cb_channel_del_cancel(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return await call.answer()
    await call.message.edit_text("📡 Obuna kanallarni boshqarish:", reply_markup=kb.admin_channel_menu())
    await call.answer("Bekor qilindi")


@router.callback_query(F.data == "ch_list")
async def cb_channel_list(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return await call.answer()
    channels = await db.get_channels()
    if not channels:
        text = "📭 Hozircha hech qanday kanal qo'shilmagan."
    else:
        lines = []
        for c in channels:
            _id, name, username, channel_id, invite_link, is_zayavka = c
            if is_zayavka:
                lines.append(f"🎯 <b>{name}</b> (zayavka) — ID: <code>{channel_id}</code>")
            else:
                lines.append(f"• {name} — {username} (ID: <code>{channel_id}</code>)")
        text = "📋 <b>Mavjud kanallar:</b>\n\n" + "\n".join(lines)
    await call.message.edit_text(text, reply_markup=kb.admin_back_menu_keyboard())
    await call.answer()


# ------------------------------------------------------------------------- #
#                          ADMIN: CHEK TEKSHIRISH                           #
# ------------------------------------------------------------------------- #
@router.message(F.text == "🧾 Chek tekshirish")
async def admin_check_payments(message: Message):
    if not is_admin(message.from_user.id):
        return
    pending = await db.get_pending_payments()
    if not pending:
        await message.answer("📭 Hozircha tekshirilmagan cheklar yo'q.")
        return

    for payment in pending:
        payment_id, user_id, photo_file_id, status, created_at, resolved_at = payment
        user = await db.get_user(user_id)
        full_name = user[2] if user else "Noma'lum"
        caption = (
            "🧾 <b>Tekshirilmagan to'lov</b>\n\n"
            f"👤 Foydalanuvchi: {full_name}\n"
            f"🆔 ID: <code>{user_id}</code>\n"
            f"🕐 Yuborilgan vaqt: {created_at}"
        )
        await message.answer_photo(
            photo_file_id, caption=caption,
            reply_markup=kb.check_confirm_keyboard(payment_id)
        )


# ------------------------------------------------------------------------- #
#                          ADMIN: QO'LDA TO'LOV                             #
# ------------------------------------------------------------------------- #
@router.message(F.text == "💵 Qo'lda to'lov")
async def admin_manual_payment_start(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await message.answer(
        "🆔 Premium bermoqchi bo'lgan foydalanuvchi ID sini kiriting:",
        reply_markup=kb.admin_cancel_keyboard()
    )
    await state.set_state(AdminManualPaymentStates.waiting_user_id)


@router.message(AdminManualPaymentStates.waiting_user_id, F.text)
async def admin_manual_payment_process(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    try:
        user_id = int(message.text.strip())
    except ValueError:
        await message.answer("⚠️ Iltimos, faqat raqamlardan iborat ID kiriting.")
        return

    user = await db.get_user(user_id)
    await state.clear()

    if not user:
        await message.answer("❌ Bunday ID li foydalanuvchi botda topilmadi.", reply_markup=kb.admin_main_menu())
        return

    await message.answer(
        f"👤 Foydalanuvchi topildi: <b>{user[2]}</b> (@{user[1] or '—'})\n"
        f"🆔 ID: <code>{user_id}</code>\n\n"
        f"Ushbu foydalanuvchiga <b>{DURATION_TEXT}lik</b> premium berilsinmi?",
        reply_markup=kb.manual_payment_confirm_keyboard(user_id)
    )


@router.callback_query(F.data.startswith("manual_confirm:"))
async def cb_manual_confirm(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return await call.answer()
    user_id = int(call.data.split(":")[1])
    until_str = await db.grant_premium(user_id, source="manual", amount=0)

    await call.message.edit_text(
        f"✅ Foydalanuvchiga (<code>{user_id}</code>) premium berildi.\n"
        f"⏳ Tugash vaqti: <b>{until_str}</b>"
    )
    await call.answer()

    try:
        await bot.send_message(
            user_id,
            f"🎉 Sizga admin tomonidan <b>{DURATION_TEXT}lik premium</b> berildi!\n"
            f"⏳ Premium tugash vaqti: <b>{until_str}</b>\n\n"
            "Endi barcha kinolardan bemalol foydalanishingiz mumkin!",
            reply_markup=kb.user_main_menu()
        )
        await try_send_pending_code(user_id, user_id)
    except Exception as e:
        logger.warning(f"Foydalanuvchiga xabar yuborishda xato: {e}")


@router.callback_query(F.data == "manual_cancel")
async def cb_manual_cancel(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return await call.answer()
    await call.message.edit_text("❌ Bekor qilindi.")
    await call.answer()


# ------------------------------------------------------------------------- #
#                          ADMIN: PREMIUM BOSHQARUVI                        #
# ------------------------------------------------------------------------- #
async def send_premium_control_panel(chat_id: int):
    enabled = await db.get_premium_enabled()
    status_text = "🟢 Yoniq" if enabled else "🟡 Ochiq (tekin)"
    text = (
        "⚙️ <b>Premium boshqaruvi</b>\n\n"
        f"Joriy holat: <b>{status_text}</b>\n\n"
        + (
            "Premium hozir <b>yoniq</b> — foydalanuvchilar kino ko'rish uchun premium sotib olishlari kerak."
            if enabled else
            "Premium hozir <b>ochiq</b> — barcha foydalanuvchilar faqat kanallarga obuna bo'lib, "
            "kinolarni bepul tomosha qilishlari mumkin."
        )
    )
    await bot.send_message(chat_id, text, reply_markup=kb.premium_control_inline_keyboard(enabled))


@router.message(F.text == "⚙️ Premium boshqaruvi")
async def admin_premium_control(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.clear()
    await message.answer(
        "⚙️ Premium boshqaruvi bo'limidasiz.",
        reply_markup=kb.premium_control_reply_keyboard()
    )
    await send_premium_control_panel(message.chat.id)


@router.callback_query(F.data == "premium_disable")
async def cb_premium_disable(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return await call.answer()
    await db.set_premium_enabled(False)
    try:
        await call.message.delete()
    except TelegramBadRequest:
        pass
    await send_premium_control_panel(call.message.chat.id)
    await call.answer("Premium o'chirildi — endi hammaga tekin ✅")


@router.callback_query(F.data == "premium_enable")
async def cb_premium_enable(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return await call.answer()
    await db.set_premium_enabled(True)
    try:
        await call.message.delete()
    except TelegramBadRequest:
        pass
    await send_premium_control_panel(call.message.chat.id)
    await call.answer("Premium yoqildi ✅")


# ------------------------------------------------------------------------- #
#                          ADMIN: KINO QO'SHISH                         #
# ------------------------------------------------------------------------- #
@router.message(F.text == "🎬 Kino qo'shish")
async def admin_add_movie_start(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await message.answer(
        "🔢 Kino kodini kiriting:",
        reply_markup=kb.cancel_add_movie_keyboard()
    )
    await state.set_state(AdminMovieStates.waiting_code)


@router.message(AdminMovieStates.waiting_code, F.text)
async def admin_add_movie_code(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    code = message.text.strip()

    if code == "❌ Bekor qilish":
        return  # bu holat yuqoridagi umumiy handler orqali qayta ishlanadi

    if await db.movie_exists(code):
        await message.answer("⚠️ Bu kod band. Boshqa kod kiriting:")
        return

    await state.update_data(movie_code=code)
    await message.answer("🗂 Bu qaysi tur? Tanlang:", reply_markup=kb.movie_category_keyboard())
    await state.set_state(AdminMovieStates.waiting_category)


@router.callback_query(AdminMovieStates.waiting_category, F.data.startswith("mcat:"))
async def cb_movie_category(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return await call.answer()
    category = call.data.split(":", 1)[1]
    if category not in ("film", "multfilm"):
        return await call.answer()
    await state.update_data(movie_category=category)
    try:
        await call.message.edit_reply_markup(reply_markup=None)
    except TelegramBadRequest:
        pass
    label = "🎬 Film" if category == "film" else "🧸 Multfilm"
    await call.message.answer(f"{label} tanlandi.\n\n📝 Endi kino tavsifini (matn) yuboring:")
    await state.set_state(AdminMovieStates.waiting_description)
    await call.answer()


@router.message(AdminMovieStates.waiting_category)
async def admin_add_movie_category_invalid(message: Message):
    if not is_admin(message.from_user.id):
        return
    await message.answer("⚠️ Iltimos, turini yuqoridagi tugmalardan tanlang (🎬 Film yoki 🧸 Multfilm).")


@router.message(AdminMovieStates.waiting_description)
async def admin_add_movie_description(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    description_html = message.html_text or (message.text or message.caption or "")
    await state.update_data(movie_description=description_html)
    await message.answer("🎥 Endi kino videosini yuboring:")
    await state.set_state(AdminMovieStates.waiting_video)


@router.message(AdminMovieStates.waiting_video, F.video)
async def admin_add_movie_video(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    data = await state.get_data()
    code = data.get("movie_code")
    description = data.get("movie_description")
    file_id = message.video.file_id

    if await db.movie_exists(code):
        await message.answer("⚠️ Bu kod band ekan. Kino qo'shish bekor qilindi, qaytadan urinib ko'ring.")
        await state.clear()
        await message.answer("Admin panelga qaytdingiz.", reply_markup=kb.admin_main_menu())
        return

    await db.add_movie(code, description, file_id, content_type="video",
                       category=data.get("movie_category") or "film")
    await state.clear()

    await message.answer(
        f"✅ Kino muvaffaqiyatli qo'shildi!\n\n🔢 Kod: <b>{code}</b>",
        reply_markup=kb.admin_main_menu()
    )


@router.message(AdminMovieStates.waiting_video)
async def admin_add_movie_video_invalid(message: Message):
    if not is_admin(message.from_user.id):
        return
    await message.answer("⚠️ Iltimos, kino <b>videosini</b> yuboring.")


# ------------------------------------------------------------------------- #
#                        ADMIN: SERIAL / ANIME QO'SHISH                     #
# ------------------------------------------------------------------------- #
serial_lock = asyncio.Lock()  # bir vaqtda kelgan videolar tartibi buzilmasligi uchun


@router.message(Command("kategoriya"))
async def admin_set_category(message: Message, command: CommandObject):
    """/kategoriya KOD film|multfilm|serial — mavjud kinoning turini o'zgartirish."""
    if not is_admin(message.from_user.id):
        return
    args = (command.args or "").split()
    valid = ("film", "multfilm", "serial")
    if len(args) != 2 or args[1].lower() not in valid:
        await message.answer(
            "ℹ️ Foydalanish: <code>/kategoriya KOD film</code>\n"
            "Turlar: <code>film</code>, <code>multfilm</code>, <code>serial</code>"
        )
        return
    if await db.set_movie_category(args[0], args[1].lower()):
        await message.answer(f"✅ <b>{args[0]}</b> kodli kino turi <b>{args[1].lower()}</b> qilindi.")
    else:
        await message.answer("❌ Bunday kodli kino topilmadi.")


@router.message(F.text == "📺 Serial / Anime")
async def admin_serial_start(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.clear()
    await message.answer(
        "🔢 Serial yoki anime uchun <b>yangi kod</b> kiriting (botda yo'q kod bo'lishi kerak):",
        reply_markup=kb.admin_cancel_keyboard()
    )
    await state.set_state(AdminSerialStates.waiting_code)


@router.message(AdminSerialStates.waiting_code, F.text)
async def admin_serial_code(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    code = message.text.strip()
    if not code:
        return
    if await db.movie_exists(code):
        await message.answer("⚠️ Bu kod botda allaqachon bor. Boshqa (yangi) kod kiriting:")
        return
    await state.update_data(serial_code=code)
    await message.answer("📝 Endi serial/anime <b>izohini</b> yuboring:")
    await state.set_state(AdminSerialStates.waiting_description)


@router.message(AdminSerialStates.waiting_description, F.text)
async def admin_serial_description(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.update_data(serial_description=message.html_text, serial_parts=[])
    await message.answer(
        "🎥 Endi <b>1-qism</b> videosini yuboring.\n\n"
        "Qismlarni ketma-ket, birin-ketin yuboring — bot ularni 1, 2, 3, 4 deb raqamlab boradi. "
        "Hammasi tugagach, pastda chiqadigan <b>«✅ Kino tugadi»</b> tugmasini bosing."
    )
    await state.set_state(AdminSerialStates.waiting_videos)


@router.message(AdminSerialStates.waiting_videos, F.video | F.document)
async def admin_serial_video(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    if message.video:
        file_id, ctype = message.video.file_id, "video"
    else:
        if not (message.document.mime_type or "").startswith("video/"):
            await message.answer("⚠️ Iltimos, <b>video</b> yuboring.")
            return
        file_id, ctype = message.document.file_id, "document"

    async with serial_lock:
        data = await state.get_data()
        parts = list(data.get("serial_parts") or [])
        parts.append([file_id, ctype])
        await state.update_data(serial_parts=parts)
        number = len(parts)

    await message.answer(
        f"✅ <b>{number}-qism</b> qabul qilindi.\n\n"
        "🎥 Keyingi qismni yuboring yoki hammasi tugagan bo'lsa pastdagi tugmani bosing 👇",
        reply_markup=kb.serial_done_keyboard()
    )


@router.message(AdminSerialStates.waiting_description)
async def admin_serial_description_invalid(message: Message):
    if not is_admin(message.from_user.id):
        return
    await message.answer("⚠️ Iltimos, izohni matn ko'rinishida yuboring.")


@router.message(AdminSerialStates.waiting_videos)
async def admin_serial_video_invalid(message: Message):
    if not is_admin(message.from_user.id):
        return
    await message.answer("⚠️ Iltimos, <b>video</b> yuboring yoki «✅ Kino tugadi» tugmasini bosing.")


@router.callback_query(AdminSerialStates.waiting_videos, F.data == "serial_done")
async def cb_serial_done(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return await call.answer()

    async with serial_lock:
        data = await state.get_data()
        parts = data.get("serial_parts") or []
        code = data.get("serial_code")
        description = data.get("serial_description") or ""

        if not parts:
            await call.answer("Avval kamida bitta video yuboring.", show_alert=True)
            return

        if await db.movie_exists(code):
            await state.clear()
            await call.message.answer(
                "⚠️ Bu kod endi band ekan. Saqlash bekor qilindi, qaytadan urinib ko'ring.",
                reply_markup=kb.admin_main_menu()
            )
            await call.answer()
            return

        await db.add_series(code, description, [(p[0], p[1]) for p in parts])
        await state.clear()

    try:
        await call.message.edit_reply_markup(reply_markup=None)
    except TelegramBadRequest:
        pass
    await call.message.answer(
        f"✅ Serial/anime saqlandi!\n\n🔢 Kod: <b>{code}</b>\n🎞 Qismlar soni: <b>{len(parts)}</b>",
        reply_markup=kb.admin_main_menu()
    )
    await call.answer("Saqlandi ✅")


@router.callback_query(F.data == "serial_done")
async def cb_serial_done_stale(call: CallbackQuery):
    await call.answer("Bu serial allaqachon saqlangan yoki bekor qilingan.", show_alert=True)


# ------------------------------------------------------------------------- #
#                        ADMIN: KANALGA JOYLASH                             #
# ------------------------------------------------------------------------- #
DEEP_LINK_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
CAPTION_LIMIT = 1024  # Telegram: rasm/video izohi uchun maksimal belgilar soni


async def get_post_channel():
    """Joylanadigan kanal: avval config.py, bo'lmasa bazadagi saqlangan qiymat."""
    if POST_CHANNEL_ID:
        return str(POST_CHANNEL_ID)
    return await db.get_setting("post_channel_id") or None


def to_chat_id(value: str):
    try:
        return int(value)
    except (TypeError, ValueError):
        return value


async def verify_post_channel(raw: str):
    """Bot kanalda admin ekanini tekshiradi. (ok, xato_matni) qaytaradi."""
    try:
        member = await bot.get_chat_member(chat_id=to_chat_id(raw), user_id=bot.id)
    except Exception as e:
        return False, f"⚠️ Kanalni tekshirib bo'lmadi. ID/username to'g'riligini va bot admin ekanini tekshiring.\nXato: {e}"
    if member.status not in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR):
        return False, "⚠️ Botni ushbu kanalda <b>admin</b> qiling (xabar yuborish huquqi bilan) va qaytadan urinib ko'ring."
    return True, ""


@router.message(Command("postkanal"))
async def admin_set_post_channel(message: Message, command: CommandObject):
    """/postkanal -1001234567890  yoki  /postkanal @kanal  — post kanalini o'zgartirish."""
    if not is_admin(message.from_user.id):
        return
    raw = (command.args or "").strip()
    if not raw:
        current = await get_post_channel()
        await message.answer(
            f"📌 Joriy post kanali: <code>{current or 'belgilanmagan'}</code>\n\n"
            "O'zgartirish: <code>/postkanal -1001234567890</code> yoki <code>/postkanal @kanal</code>"
        )
        return
    ok, err = await verify_post_channel(raw)
    if not ok:
        await message.answer(err)
        return
    await db.set_setting("post_channel_id", raw)
    await message.answer(f"✅ Post kanali saqlandi: <code>{raw}</code>")


@router.message(F.text == "📌 Kanalga joylash")
async def admin_post_start(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.clear()
    await message.answer(
        "🔢 Kanalga joylamoqchi bo'lgan <b>kino kodini</b> kiriting:",
        reply_markup=kb.admin_cancel_keyboard()
    )
    await state.set_state(AdminPostStates.waiting_code)


@router.message(AdminPostStates.waiting_code, F.text)
async def admin_post_code(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    code = message.text.strip()

    if not await db.movie_exists(code):
        await message.answer(
            "❌ Bu kodli kino qo'shilmagan.\n"
            "Avval «🎬 Kino qo'shish» orqali kinoni qo'shing yoki boshqa kod kiriting:"
        )
        return

    if not DEEP_LINK_RE.match(code):
        await message.answer(
            "⚠️ Bu kodni havolada ishlatib bo'lmaydi (faqat lotin harflari, raqamlar, <code>_</code> va "
            "<code>-</code> belgilari ruxsat etiladi, 64 tagacha). Boshqa kod kiriting:"
        )
        return

    await state.update_data(post_code=code)
    await message.answer(
        "🖼 Endi kinoning <b>qisqacha videosini yoki rasmini</b> yuboring.\n\n"
        "💡 Premium emojilar kanalda ham premium bo'lib chiqishi uchun <b>izohni shu video/rasmning "
        "tagiga (caption) yozib, bitta xabarda</b> yuboring. Izohsiz yuborsangiz, izohni keyin so'rayman."
    )
    await state.set_state(AdminPostStates.waiting_media)


@router.message(AdminPostStates.waiting_code)
async def admin_post_code_invalid(message: Message):
    if not is_admin(message.from_user.id):
        return
    await message.answer("⚠️ Iltimos, kino kodini matn ko'rinishida yuboring.")


@router.message(AdminPostStates.waiting_media, F.video | F.photo)
async def admin_post_media(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    if message.video:
        media_type, file_id = "video", message.video.file_id
    else:
        media_type, file_id = "photo", message.photo[-1].file_id

    await state.update_data(post_media_type=media_type, post_media_id=file_id)

    # Izoh video/rasm bilan birga kelgan bo'lsa: xabarni kanalga "nusxalaymiz" (copy_message).
    # Telegram kanallarga bot nomidan premium emoji yuborishga ruxsat bermaydi, lekin
    # admin yuborgan xabar nusxalanganda premium emojilar aynan saqlanib qoladi.
    if message.caption:
        entities = [e.model_dump(mode="json", exclude_none=True) for e in (message.caption_entities or [])]
        await state.update_data(
            post_caption_text=message.caption,
            post_caption_entities=entities,
            post_caption_html=message.html_text,
            post_copy_chat_id=message.chat.id,
            post_copy_message_id=message.message_id,
        )
        await proceed_to_publish(message, state)
        return

    await message.answer(
        "📝 Endi post uchun <b>izoh</b> yuboring (qalin/kursiv va havolalar saqlanadi).\n"
        f"Maksimal uzunlik: {CAPTION_LIMIT} belgi.\n\n"
        "⚠️ Premium emojilar to'liq saqlanishi uchun izohni alohida emas, <b>video/rasm bilan bir xabarda</b> "
        "(caption sifatida) yuborgan ma'qul."
    )
    await state.set_state(AdminPostStates.waiting_caption)


@router.message(AdminPostStates.waiting_media)
async def admin_post_media_invalid(message: Message):
    if not is_admin(message.from_user.id):
        return
    await message.answer("⚠️ Iltimos, <b>video</b> yoki <b>rasm</b> yuboring.")


@router.message(AdminPostStates.waiting_caption, F.text)
async def admin_post_caption(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    if len(message.text) > CAPTION_LIMIT:
        await message.answer(
            f"⚠️ Izoh juda uzun ({len(message.text)} belgi). {CAPTION_LIMIT} belgidan oshmasligi kerak. "
            "Qisqaroq izoh yuboring:"
        )
        return

    entities = [e.model_dump(mode="json", exclude_none=True) for e in (message.entities or [])]
    await state.update_data(
        post_caption_text=message.text,
        post_caption_entities=entities,
        post_caption_html=message.html_text,
    )

    await proceed_to_publish(message, state)


async def proceed_to_publish(message: Message, state: FSMContext):
    channel = await get_post_channel()
    if not channel:
        await message.answer(
            "📡 Post yuboriladigan <b>kanal ID</b> yoki <b>@username</b> ini kiriting "
            "(bot o'sha kanalda admin bo'lishi kerak). Bir marta kiritasiz, keyin eslab qolinadi:"
        )
        await state.set_state(AdminPostStates.waiting_channel)
        return
    await publish_post(message, state, channel)


@router.message(AdminPostStates.waiting_caption)
async def admin_post_caption_invalid(message: Message):
    if not is_admin(message.from_user.id):
        return
    await message.answer("⚠️ Iltimos, izohni matn ko'rinishida yuboring.")


@router.message(AdminPostStates.waiting_channel, F.text)
async def admin_post_channel_input(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    raw = message.text.strip()
    ok, err = await verify_post_channel(raw)
    if not ok:
        await message.answer(err)
        return
    await db.set_setting("post_channel_id", raw)
    await publish_post(message, state, raw)


async def publish_post(message: Message, state: FSMContext, channel: str):
    data = await state.get_data()
    code = data.get("post_code")
    media_type = data.get("post_media_type")
    media_id = data.get("post_media_id")
    caption_text = data.get("post_caption_text") or ""
    caption_html = data.get("post_caption_html") or ""
    entities = [MessageEntity(**e) for e in (data.get("post_caption_entities") or [])]

    me = await bot.get_me()
    url = f"https://t.me/{me.username}?start={code}"
    markup = kb.post_watch_keyboard(url)
    chat_id = to_chat_id(channel)

    send = bot.send_video if media_type == "video" else bot.send_photo

    copy_chat_id = data.get("post_copy_chat_id")
    copy_message_id = data.get("post_copy_message_id")
    if copy_chat_id and copy_message_id:
        try:
            await bot.copy_message(
                chat_id=chat_id, from_chat_id=copy_chat_id,
                message_id=copy_message_id, reply_markup=markup
            )
            await state.clear()
            await message.answer(
                f"✅ Post kanalga joylandi!\n\n🔢 Kino kodi: <b>{code}</b>\n🔗 Tugma havolasi: <code>{url}</code>",
                reply_markup=kb.admin_main_menu()
            )
            return
        except Exception as e:
            logger.warning(f"copy_message ishlamadi, oddiy yuborishga o'tilmoqda: {e}")

    # 1-urinish: izoh entity'lari bilan (premium emojilar aynan shu usulda saqlanadi)
    # 2-urinish: HTML bilan, 3-urinish: oddiy matn
    attempts = [
        ("entities", dict(caption=caption_text, caption_entities=entities, parse_mode=None)),
        ("html", dict(caption=caption_html, parse_mode=ParseMode.HTML)),
        ("plain", dict(caption=caption_text, parse_mode=None)),
    ]
    used = None
    errors = []
    last_exc = None
    for name, kwargs in attempts:
        try:
            await send(chat_id, media_id, reply_markup=markup, **kwargs)
            used = name
            break
        except TelegramBadRequest as e:
            logger.warning(f"Post '{name}' usulida yuborilmadi: {e}")
            errors.append(f"{name}: {e}")
            last_exc = e
        except Exception as e:
            last_exc = e
            break

    if used is None:
        await state.clear()
        await message.answer(
            f"❌ Postni kanalga yuborib bo'lmadi.\nXato: {last_exc}",
            reply_markup=kb.admin_main_menu()
        )
        return

    has_custom = any(e.type == "custom_emoji" for e in entities)
    warn = ""
    if has_custom and used != "entities":
        warn = (
            "\n\n⚠️ Premium emojilar Telegram tomonidan qabul qilinmadi, post oddiy emoji bilan joylandi.\n"
            f"Sabab: <code>{errors[0] if errors else '—'}</code>"
        )

    await state.clear()
    await message.answer(
        f"✅ Post kanalga joylandi!\n\n🔢 Kino kodi: <b>{code}</b>\n🔗 Tugma havolasi: <code>{url}</code>{warn}",
        reply_markup=kb.admin_main_menu()
    )


# ------------------------------------------------------------------------- #
#                        FOYDALANUVCHI CHIQIB KETSA (BLOK)                  #
# ------------------------------------------------------------------------- #
@router.message()
async def fallback_handler(message: Message):
    """Boshqa hech qaysi handlerga tushmagan xabarlar uchun."""
    if is_admin(message.from_user.id):
        await message.answer("Admin panelidan foydalaning 👇", reply_markup=kb.admin_main_menu())
        return

    if not await check_subscription(message.from_user.id):
        await message.answer(
            "🔒 Davom etish uchun avval quyidagi kanal(lar)ga obuna bo'ling.",
            reply_markup=ReplyKeyboardRemove()
        )
        await send_subscription_request(message.chat.id)
        return

    if await user_has_access(message.from_user.id):
        await message.answer("Menyudan birini tanlang 👇", reply_markup=kb.user_main_menu())
    else:
        await send_premium_offer(message.chat.id)


# ------------------------------------------------------------------------- #
#                    PREMIUM MUDDATI TUGAGANINI KUZATISH (FON JARAYON)      #
# ------------------------------------------------------------------------- #
async def premium_expiry_watcher():
    while True:
        try:
            expired_users = await db.get_expired_unnotified_users()
            for user_id in expired_users:
                await db.mark_expired_and_notified(user_id)
                try:
                    await bot.send_message(
                        user_id,
                        "⌛️ Premium muddatingiz tugadi.\n\n"
                        "Kinolarni davom ettirib ko'rish uchun qaytadan premium sotib oling 👇",
                        reply_markup=ReplyKeyboardRemove()
                    )
                    await send_premium_offer(user_id)
                except Exception as e:
                    logger.warning(f"Premium tugashi haqida xabar yuborilmadi ({user_id}): {e}")
        except Exception as e:
            logger.error(f"premium_expiry_watcher xatosi: {e}")
        await asyncio.sleep(60)  # har daqiqada tekshiradi


# ------------------------------------------------------------------------- #
#                                    ISHGA TUSHIRISH                        #
# ------------------------------------------------------------------------- #
async def main():
    await db.connect()
    asyncio.create_task(premium_expiry_watcher())
    logger.info("Bot ishga tushdi...")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot to'xtatildi.")
