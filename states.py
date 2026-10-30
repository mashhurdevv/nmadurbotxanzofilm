# states.py
# Barcha FSM (Finite State Machine) holatlari shu yerda

from aiogram.fsm.state import State, StatesGroup


class UserStates(StatesGroup):
    waiting_movie_code = State()          # kino qidirish uchun kod kutilmoqda
    waiting_payment_check = State()       # to'lov cheki (rasm) kutilmoqda


class AdminChannelStates(StatesGroup):
    waiting_channel_name = State()
    waiting_channel_username = State()
    waiting_channel_id = State()
    waiting_zayavka_name = State()
    waiting_zayavka_link = State()
    waiting_zayavka_channel_id = State()


class AdminMovieStates(StatesGroup):
    waiting_code = State()
    waiting_category = State()
    waiting_description = State()
    waiting_video = State()


class AdminBroadcastStates(StatesGroup):
    waiting_content = State()


class AdminManualPaymentStates(StatesGroup):
    waiting_user_id = State()


class AdminPostStates(StatesGroup):
    waiting_code = State()       # kanalga joylanadigan kino kodi
    waiting_media = State()      # qisqacha video yoki rasm
    waiting_caption = State()    # izoh (premium emojilar bilan)
    waiting_channel = State()    # joylanadigan kanal (birinchi marta)


class AdminSerialStates(StatesGroup):
    waiting_code = State()
    waiting_description = State()
    waiting_videos = State()     # qismlar ketma-ket yuboriladi, "Tugadi" tugmasi bosilguncha
