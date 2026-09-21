"""
Telegram Bot for "Dr. Shoxruz XDENT Dental Clinic" (Tashkent).
Built with aiogram 3.x.

Automates patient intake (Full Name, Birth Year, District/Address, Phone)
and dispatches structured leads to clinic administrators in real time.
"""

from __future__ import annotations

import asyncio
import html
import logging
import os
import sys
from datetime import datetime, timezone, timedelta
from typing import Optional, Union

from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, F, types
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)

# Optional import for compatibility across aiogram 3.x minor versions
try:
    from aiogram.client.default import DefaultBotProperties
    HAS_DEFAULT_PROPERTIES = True
except ImportError:
    HAS_DEFAULT_PROPERTIES = False

# ---------------------------------------------------------------------------
# Configuration & Constants
# ---------------------------------------------------------------------------
load_dotenv()

# Placeholders or environment variables
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID", "").strip()

# Administrator / Manager IDs (Hardcoded fallback + environment variable)
ADMIN_IDS: set[int] = {5831301324}
if ADMIN_CHAT_ID:
    try:
        ADMIN_IDS.add(int(ADMIN_CHAT_ID))
    except ValueError:
        pass


def is_manager(user_id: int) -> bool:
    """Check if the Telegram user ID belongs to a clinic manager/admin."""
    return user_id in ADMIN_IDS


# In-memory store of recent leads for manager inspection
RECENT_LEADS: list[dict] = []
MAX_RECENT_LEADS = 30

CLINIC_NAME = "Dr. Shoxruz XDENT Dental Clinic"
CLINIC_ADDRESS = "г. Ташкент, пр-т Мирзо Улугбека"
CLINIC_PHONE = "+998 95 111 11 61"
CLINIC_SCHEDULE = "24/7 (Круглосуточно, без выходных)"
CLINIC_LATITUDE = 41.3275
CLINIC_LONGITUDE = 69.3297

# Tashkent Timezone (UTC+5)
TASHKENT_TZ = timezone(timedelta(hours=5))

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Catalog Data: Services & Doctors
# ---------------------------------------------------------------------------
SERVICES_DATA = {
    "consultation": {
        "title": "Первичная консультация и диагностика",
        "description": (
            "🔍 <b>Первичная консультация и диагностика</b>\n\n"
            "Комплексный осмотр ведущим специалистом с применением "
            "дентального микроскопа и фотопротокола.\n\n"
            "💳 <b>Стоимость:</b>\n"
            "• Консультация + цифровой снимок: <b>150 000 сум</b>\n"
            "<i>(При продолжении лечения в клинике — БЕСПЛАТНО)</i>\n\n"
            "Включает составление персонального плана лечения и сметы."
        ),
    },
    "therapy": {
        "title": "Терапия и чистка",
        "description": (
            "✨ <b>Терапия и профессиональная гигиена</b>\n\n"
            "Лечение зубов с сохранением максимального объема здоровых тканей:\n\n"
            "💳 <b>Стоимость:</b>\n"
            "• Ультразвуковая чистка + AirFlow: <b>от 450 000 сум</b>\n"
            "• Лечение кариеса (эстетическая реставрация): <b>от 350 000 сум</b>\n"
            "• Лечение каналов под микроскопом: <b>от 600 000 сум</b>"
        ),
    },
    "orthodontics": {
        "title": "Ортодонтия (Брекеты / Элайнеры)",
        "description": (
            "🦷 <b>Ортодонтия и исправление прикуса</b>\n\n"
            "Современные методы коррекции прикуса для детей и взрослых:\n\n"
            "💳 <b>Стоимость:</b>\n"
            "• Первичный ортодонтический осмотр и слепки: <b>от 200 000 сум</b>\n"
            "• Металлические брекет-системы: <b>от 4 500 000 сум</b> (на одну челюсть)\n"
            "• Керамические / сапфировые брекеты: <b>от 7 000 000 сум</b>\n"
            "• Прозрачные элайнеры: <b>индивидуальный расчет</b>"
        ),
    },
    "surgery": {
        "title": "Хирургия и имплантация",
        "description": (
            "⚙️ <b>Хирургия и имплантация зубов</b>\n\n"
            "Безболезненные хирургические манипуляции и импланты премиум-класса:\n\n"
            "💳 <b>Стоимость:</b>\n"
            "• Простое / сложное удаление зуба: <b>от 250 000 сум</b>\n"
            "• Удаление зуба мудрости: <b>от 500 000 сум</b>\n"
            "• Установка дентального импланта под ключ (Osstem, Dentium, Straumann): <b>от 3 500 000 сум</b>"
        ),
    },
    "pediatric": {
        "title": "Детская стоматология",
        "description": (
            "🧸 <b>Детская стоматология без страха и слез</b>\n\n"
            "Адаптационный прием, бережное отношение и лечение в игровой форме:\n\n"
            "💳 <b>Стоимость:</b>\n"
            "• Адаптационный осмотр и фторирование: <b>от 150 000 сум</b>\n"
            "• Лечение молочного зуба: <b>от 250 000 сум</b>\n"
            "• Герметизация фиссур: <b>от 180 000 сум</b>"
        ),
    },
}

DOCTORS_TEXT = (
    "👨‍⚕️ <b>Наши врачи и направления — Dr. Shoxruz XDENT</b>\n\n"
    "👑 <b>Главный врач: Др. Шохруз</b>\n"
    "• <i>Ведущий хирург-имплантолог, опыт более 12 лет</i>\n"
    "• Специализация: сложная тотальная имплантация, костная пластика, синус-лифтинг.\n\n"
    "💎 <b>Врач-терапевт: Др. Нигора</b>\n"
    "• <i>Эстетическая стоматология и эндодонтия</i>\n"
    "• Специализация: художественная реставрация зубов, лечение каналов под микроскопом.\n\n"
    "📐 <b>Врач-ортодонт: Др. Сардор</b>\n"
    "• <i>Эксперт по коррекции прикуса</i>\n"
    "• Специализация: самолигирующие брекет-системы, невидимые элайнеры.\n\n"
    "🧸 <b>Детский врач-стоматолог: Др. Мадина</b>\n"
    "• <i>Детский стоматолог-психолог</i>\n"
    "• Специализация: лечение кариеса без бормашины (Icon), адаптация деток."
)

ABOUT_CLINIC_TEXT = (
    f"💎 <b>О стоматологической клинике {CLINIC_NAME}</b>\n\n"
    "<b>Dr. Shoxruz XDENT</b> — флагманский центр эстетической, ортодонтической "
    "и хирургической стоматологии в Ташкенте.\n\n"
    "✨ <b>Наши стандарты качества:</b>\n"
    "• <b>Европейское оборудование:</b> дентальные микроскопы Carl Zeiss, 3D-томографы, немецкие установки KaVo.\n"
    "• <b>Абсолютная стерильность:</b> 5-ступенчатая стерилизация инструментов (автоклавы B-класса Euronda, Италия).\n"
    "• <b>Лечение без боли:</b> ультратонкие японские иглы и премиальные анестетики последнего поколения.\n"
    "• <b>24/7 Скорая помощь:</b> круглосуточный прием пациентов с острой зубной болью и травмами.\n"
    "• <b>Официальная гарантия:</b> гарантийные сертификаты на все виды имплантов и коронок.\n\n"
    f"📍 <b>Адрес:</b> {CLINIC_ADDRESS}\n"
    f"🕒 <b>Режим работы:</b> {CLINIC_SCHEDULE}\n"
    f"📞 <b>Единый колл-центр:</b> <code>{CLINIC_PHONE}</code>"
)

# ---------------------------------------------------------------------------
# FSM States
# ---------------------------------------------------------------------------
class BookingState(StatesGroup):
    service = State()     # Selected or typed service/problem
    full_name = State()   # Patient's Full Name (ФИО)
    birth_year = State()  # Year of birth (Год рождения)
    address = State()     # District or home address
    phone = State()       # Phone number (contact or text)


# ---------------------------------------------------------------------------
# Keyboards Builder
# ---------------------------------------------------------------------------
def get_main_menu_keyboard(is_admin_user: bool = False) -> InlineKeyboardMarkup:
    """Main menu inline keyboard."""
    buttons = []
    if is_admin_user:
        buttons.append(
            [
                InlineKeyboardButton(
                    text="👨‍💼 Панель администратора", callback_data="admin_panel"
                )
            ]
        )
    buttons.extend([
        [
            InlineKeyboardButton(
                text="🦷 Услуги и цены", callback_data="menu_services"
            )
        ],
        [
            InlineKeyboardButton(
                text="👨‍⚕️ Наши врачи и направления", callback_data="menu_doctors"
            )
        ],
        [
            InlineKeyboardButton(
                text="📝 Записаться на прием", callback_data="book_start"
            )
        ],
        [
            InlineKeyboardButton(
                text="📍 Локация и контакты", callback_data="menu_location"
            )
        ],
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_admin_panel_keyboard() -> InlineKeyboardMarkup:
    """Manager/Admin panel keyboard."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📋 Последние заявки", callback_data="admin_recent_leads"
                ),
                InlineKeyboardButton(
                    text="📊 Статистика", callback_data="admin_stats"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🧪 Отправить тестовую заявку", callback_data="admin_test_lead"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🦷 Открыть меню пациента (тест)", callback_data="admin_as_client"
                ),
            ],
        ]
    )


def get_lead_actions_keyboard(lead_id: int, current_status: str = "new") -> InlineKeyboardMarkup:
    """Action buttons attached to lead notifications sent to managers."""
    buttons = []
    if current_status == "new":
        buttons.append([
            InlineKeyboardButton(text="✅ В работу", callback_data=f"lead_take_{lead_id}"),
            InlineKeyboardButton(text="📞 Подтверждено", callback_data=f"lead_confirm_{lead_id}"),
        ])
        buttons.append([
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"lead_reject_{lead_id}"),
        ])
    elif current_status == "in_progress":
        buttons.append([
            InlineKeyboardButton(text="📞 Подтверждено", callback_data=f"lead_confirm_{lead_id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"lead_reject_{lead_id}"),
        ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_services_keyboard() -> InlineKeyboardMarkup:
    """Services list keyboard."""
    buttons = []
    for key, data in SERVICES_DATA.items():
        buttons.append(
            [InlineKeyboardButton(text=f"• {data['title']}", callback_data=f"svc_{key}")]
        )
    buttons.append(
        [InlineKeyboardButton(text="📝 Записаться на прием", callback_data="book_start")]
    )
    buttons.append(
        [InlineKeyboardButton(text="◀️ В главное меню", callback_data="menu_main")]
    )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_service_detail_keyboard(service_key: str) -> InlineKeyboardMarkup:
    """Service detail screen keyboard."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📝 Записаться на эту услугу",
                    callback_data=f"book_with_svc_{service_key}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="◀️ Назад к услугам", callback_data="menu_services"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🏠 В главное меню", callback_data="menu_main"
                )
            ],
        ]
    )


def get_doctors_keyboard() -> InlineKeyboardMarkup:
    """Doctors screen keyboard."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📝 Записаться к врачу", callback_data="book_start"
                )
            ],
            [
                InlineKeyboardButton(
                    text="◀️ В главное меню", callback_data="menu_main"
                )
            ],
        ]
    )


def get_location_keyboard() -> InlineKeyboardMarkup:
    """Location screen keyboard."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📝 Записаться на прием", callback_data="book_start"
                )
            ],
            [
                InlineKeyboardButton(
                    text="◀️ В главное меню", callback_data="menu_main"
                )
            ],
        ]
    )


def get_cancel_inline_keyboard() -> InlineKeyboardMarkup:
    """Inline button to cancel FSM process."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отменить запись", callback_data="booking_cancel")]
        ]
    )


def get_bottom_reply_keyboard(is_admin_user: bool = False) -> ReplyKeyboardMarkup:
    """Persistent bottom keyboard docked below the text input."""
    kb = [
        [
            KeyboardButton(text="🦷 Услуги и цены"),
            KeyboardButton(text="👨‍⚕️ Наши врачи"),
        ],
        [
            KeyboardButton(text="📝 Записаться на прием"),
        ],
        [
            KeyboardButton(text="📍 Локация и контакты"),
            KeyboardButton(text="ℹ️ О клинике"),
        ],
    ]
    if is_admin_user:
        kb.append([KeyboardButton(text="👨‍💼 Панель администратора")])
    return ReplyKeyboardMarkup(
        keyboard=kb,
        resize_keyboard=True,
        is_persistent=True,
    )


def get_services_choice_keyboard() -> InlineKeyboardMarkup:
    """Inline buttons to quickly choose a service on Step 1."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔍 Консультация + снимок (150 тыс)",
                    callback_data="pick_svc_consultation",
                )
            ],
            [
                InlineKeyboardButton(
                    text="✨ Проф. чистка / AirFlow",
                    callback_data="pick_svc_therapy",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🦷 Острая боль / Лечение кариеса",
                    callback_data="pick_svc_pain",
                )
            ],
            [
                InlineKeyboardButton(
                    text="⚙️ Имплантация зубов под ключ",
                    callback_data="pick_svc_surgery",
                )
            ],
            [
                InlineKeyboardButton(
                    text="📐 Исправление прикуса (Брекеты / Элайнеры)",
                    callback_data="pick_svc_orthodontics",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🧸 Детская стоматология",
                    callback_data="pick_svc_pediatric",
                )
            ],
            [
                InlineKeyboardButton(
                    text="✍️ Другая проблема (ввести текстом)",
                    callback_data="pick_svc_custom",
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ Отменить запись", callback_data="booking_cancel"
                )
            ],
        ]
    )


def get_name_choice_keyboard(first_name: Optional[str] = None) -> InlineKeyboardMarkup:
    """Inline buttons for name step."""
    buttons = []
    if first_name and first_name != "Гость":
        buttons.append([
            InlineKeyboardButton(
                text=f"👤 Использовать: {first_name}",
                callback_data=f"pick_name_{first_name[:30]}",
            )
        ])
    buttons.append([
        InlineKeyboardButton(text="❌ Отменить запись", callback_data="booking_cancel")
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_year_choice_keyboard() -> InlineKeyboardMarkup:
    """Inline buttons for quick birth year selection on Step 3."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="1985", callback_data="pick_year_1985"),
                InlineKeyboardButton(text="1990", callback_data="pick_year_1990"),
                InlineKeyboardButton(text="1995", callback_data="pick_year_1995"),
            ],
            [
                InlineKeyboardButton(text="1998", callback_data="pick_year_1998"),
                InlineKeyboardButton(text="2000", callback_data="pick_year_2000"),
                InlineKeyboardButton(text="2002", callback_data="pick_year_2002"),
            ],
            [
                InlineKeyboardButton(text="2005", callback_data="pick_year_2005"),
                InlineKeyboardButton(text="👶 Ребенок (до 14 лет)", callback_data="pick_year_2015"),
            ],
            [
                InlineKeyboardButton(text="✍️ Ввести свой год", callback_data="pick_year_custom"),
            ],
            [
                InlineKeyboardButton(text="❌ Отменить запись", callback_data="booking_cancel"),
            ],
        ]
    )


def get_districts_keyboard() -> InlineKeyboardMarkup:
    """Inline buttons for Tashkent districts on Step 4."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Мирзо-Улугбекский", callback_data="pick_dist_Мирзо-Улугбекский"),
                InlineKeyboardButton(text="Юнусабадский", callback_data="pick_dist_Юнусабадский"),
            ],
            [
                InlineKeyboardButton(text="Чиланзарский", callback_data="pick_dist_Чиланзарский"),
                InlineKeyboardButton(text="Яшнабадский", callback_data="pick_dist_Яшнабадский"),
            ],
            [
                InlineKeyboardButton(text="Мирабадский", callback_data="pick_dist_Мирабадский"),
                InlineKeyboardButton(text="Яккасарайский", callback_data="pick_dist_Яккасарайский"),
            ],
            [
                InlineKeyboardButton(text="Шайхантахурский", callback_data="pick_dist_Шайхантахурский"),
                InlineKeyboardButton(text="Алмазарский", callback_data="pick_dist_Алмазарский"),
            ],
            [
                InlineKeyboardButton(text="Сергелийский", callback_data="pick_dist_Сергелийский"),
                InlineKeyboardButton(text="Учтепинский", callback_data="pick_dist_Учтепинский"),
            ],
            [
                InlineKeyboardButton(text="Янгихаётский", callback_data="pick_dist_Янгихаётский"),
                InlineKeyboardButton(text="Другой регион / область", callback_data="pick_dist_Другой регион"),
            ],
            [
                InlineKeyboardButton(text="❌ Отменить запись", callback_data="booking_cancel"),
            ],
        ]
    )


def get_contact_reply_keyboard() -> ReplyKeyboardMarkup:
    """Reply keyboard requesting user contact with one-tap button."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📱 Поделиться контактом", request_contact=True)],
            [KeyboardButton(text="❌ Отменить запись")],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


# ---------------------------------------------------------------------------
# Bot & Dispatcher Setup
# ---------------------------------------------------------------------------
bot: Optional[Bot] = None
if BOT_TOKEN and ":" in BOT_TOKEN and not BOT_TOKEN.startswith("YOUR_"):
    if HAS_DEFAULT_PROPERTIES:
        bot = Bot(
            token=BOT_TOKEN,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )
    else:
        bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
else:
    logger.warning("BOT_TOKEN is not set or invalid! Please configure BOT_TOKEN.")

dp = Dispatcher(storage=MemoryStorage())


# ---------------------------------------------------------------------------
# General Handlers & Navigation
# ---------------------------------------------------------------------------
@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    """Handler for /start command."""
    await state.clear()
    user_id = message.from_user.id

    # If the user is an authorized manager
    if is_manager(user_id):
        admin_name = html.escape(message.from_user.first_name or "Менеджер")
        greeting = (
            f"👨‍💼 <b>Кабинет администратора — {CLINIC_NAME}</b>\n\n"
            f"Здравствуйте, <b>{admin_name}</b>!\n"
            f"Вы авторизованы как <b>Управляющий / Администратор</b> (ID: <code>{user_id}</code>).\n\n"
            f"✅ Уведомления о новых пациентах: <b>АКТИВНЫ</b>\n"
            f"Все новые записи пациентов автоматически поступают в этот чат с деталями, контактами и адресом.\n\n"
            f"Для управления заявками и разделами клиники используйте меню внизу экрана 👇"
        )
        await message.answer(
            greeting,
            reply_markup=get_bottom_reply_keyboard(is_admin_user=True),
        )
        return

    # Normal patient / client flow
    first_name = html.escape(message.from_user.first_name or "Гость")
    greeting = (
        f"Здравствуйте, <b>{first_name}</b>!\n\n"
        f"Добро пожаловать в цифровую приемную клиники <b>{CLINIC_NAME}</b> 🦷\n\n"
        f"Мы предоставляем полный спектр премиальной стоматологической помощи "
        f"в Ташкенте с использованием передового европейского оборудования.\n\n"
        f"Воспользуйтесь кнопками меню прямо под клавиатурой 👇"
    )
    await message.answer(
        greeting,
        reply_markup=get_bottom_reply_keyboard(is_admin_user=False),
    )


# ---------------------------------------------------------------------------
# Bottom Reply Keyboard Handlers
# ---------------------------------------------------------------------------
@dp.message(F.text == "🦷 Услуги и цены")
async def msg_services(message: Message, state: FSMContext) -> None:
    """Handle bottom keyboard 'Услуги и цены'."""
    await state.clear()
    text = (
        "🦷 <b>Услуги и цены клиники Dr. Shoxruz XDENT</b>\n\n"
        "Мы придерживаемся политики открытых и честных цен без скрытых доплат. "
        "Выберите направление стоматологии для получения подробной информации:"
    )
    await message.answer(text, reply_markup=get_services_keyboard())


@dp.message(F.text.in_({"👨‍⚕️ Наши врачи", "👨‍⚕️ Врачи"}))
async def msg_doctors(message: Message, state: FSMContext) -> None:
    """Handle bottom keyboard 'Наши врачи'."""
    await state.clear()
    await message.answer(DOCTORS_TEXT, reply_markup=get_doctors_keyboard())


@dp.message(F.text == "📝 Записаться на прием")
async def msg_book(message: Message, state: FSMContext) -> None:
    """Handle bottom keyboard 'Записаться на прием'."""
    await state.set_state(BookingState.service)
    text = (
        "📝 <b>Запись на прием в Dr. Shoxruz XDENT</b>\n\n"
        "<b>Шаг 1 из 5:</b> Выберите услугу или проблему из списка ниже "
        "или опишите вашу ситуацию своими словами:"
    )
    await message.answer(text, reply_markup=get_services_choice_keyboard())


@dp.message(F.text == "📍 Локация и контакты")
async def msg_location(message: Message, state: FSMContext) -> None:
    """Handle bottom keyboard 'Локация и контакты'."""
    await state.clear()
    location_text = (
        f"📍 <b>Локация и контакты — {CLINIC_NAME}</b>\n\n"
        f"🏢 <b>Адрес:</b> {CLINIC_ADDRESS}\n"
        f"🕒 <b>Режим работы:</b> {CLINIC_SCHEDULE}\n"
        f"📞 <b>Единый телефон:</b> <code>{CLINIC_PHONE}</code>\n\n"
        f"<i>Ниже мы отправили геолокацию на карте, чтобы вам было удобно построить маршрут.</i>"
    )
    await message.answer(location_text, reply_markup=get_location_keyboard())
    try:
        await message.answer_location(
            latitude=CLINIC_LATITUDE,
            longitude=CLINIC_LONGITUDE,
        )
    except Exception as exc:
        logger.warning("Could not send location coordinates: %s", exc)


@dp.message(F.text == "ℹ️ О клинике")
async def msg_about(message: Message, state: FSMContext) -> None:
    """Handle bottom keyboard 'О клинике'."""
    await state.clear()
    await message.answer(ABOUT_CLINIC_TEXT)


@dp.message(F.text == "👨‍💼 Панель администратора")
async def msg_admin_panel(message: Message, state: FSMContext) -> None:
    """Handle bottom keyboard 'Панель администратора'."""
    await cmd_admin(message, state)


@dp.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext) -> None:
    """Direct command to open the Manager Panel."""
    await state.clear()
    user_id = message.from_user.id
    if not is_manager(user_id):
        await message.answer(
            "⛔ <i>Доступ ограничен. Данный раздел доступен только администраторам клиники Dr. Shoxruz XDENT.</i>"
        )
        return

    admin_name = html.escape(message.from_user.first_name or "Менеджер")
    text = (
        f"👨‍💼 <b>Панель администратора — {CLINIC_NAME}</b>\n\n"
        f"Администратор: <b>{admin_name}</b> (ID: <code>{user_id}</code>)\n"
        f"Управление записями и мониторинг:"
    )
    await message.answer(text, reply_markup=get_admin_panel_keyboard())


@dp.callback_query(F.data == "admin_panel")
async def cb_admin_panel(callback: CallbackQuery, state: FSMContext) -> None:
    """Callback to return to the Manager Panel."""
    await state.clear()
    user_id = callback.from_user.id
    if not is_manager(user_id):
        await callback.answer("⛔ Доступ ограничен", show_alert=True)
        return

    admin_name = html.escape(callback.from_user.first_name or "Менеджер")
    text = (
        f"👨‍💼 <b>Панель администратора — {CLINIC_NAME}</b>\n\n"
        f"Администратор: <b>{admin_name}</b> (ID: <code>{user_id}</code>)\n"
        f"Управление записями и мониторинг:"
    )
    await callback.message.edit_text(text, reply_markup=get_admin_panel_keyboard())
    await callback.answer()


@dp.callback_query(F.data == "admin_as_client")
async def cb_admin_as_client(callback: CallbackQuery, state: FSMContext) -> None:
    """Allow manager to preview/test the client menu."""
    await state.clear()
    user_id = callback.from_user.id
    text = (
        f"🦷 <b>Режим предпросмотра пациента — {CLINIC_NAME}</b>\n\n"
        f"Вы перешли в интерфейс пациента. Здесь можно протестировать меню и оформление заявки.\n\n"
        f"<i>(Для возврата в панель управления нажмите верхнюю кнопку или введите /admin)</i>"
    )
    await callback.message.edit_text(
        text,
        reply_markup=get_main_menu_keyboard(is_admin_user=True),
    )
    await callback.answer()


@dp.callback_query(F.data == "admin_recent_leads")
async def cb_admin_recent_leads(callback: CallbackQuery) -> None:
    """Display recent patient leads."""
    if not is_manager(callback.from_user.id):
        await callback.answer("⛔ Доступ ограничен", show_alert=True)
        return

    if not RECENT_LEADS:
        text = (
            "📋 <b>Последние заявки пациентов</b>\n\n"
            "<i>Заявок в текущей сессии пока нет.</i>\n\n"
            "Вы можете нажать кнопку «🧪 Отправить тестовую заявку», чтобы проверить формат оповещений."
        )
    else:
        text = f"📋 <b>Последние заявки пациентов (всего: {len(RECENT_LEADS)})</b>:\n\n"
        for lead in reversed(RECENT_LEADS[-10:]):
            text += (
                f"#{lead['id']} • <b>{html.escape(lead['full_name'])}</b> ({lead['status']})\n"
                f"   🛠 {html.escape(lead['service'])}\n"
                f"   📞 {html.escape(lead['phone'])} | 📅 {lead['birth_year']} г.р.\n"
                f"   ⏱ {lead['timestamp']}\n\n"
            )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Обновить", callback_data="admin_recent_leads")],
            [InlineKeyboardButton(text="◀️ В панель администратора", callback_data="admin_panel")],
        ]
    )
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@dp.callback_query(F.data == "admin_stats")
async def cb_admin_stats(callback: CallbackQuery) -> None:
    """Display lead statistics."""
    if not is_manager(callback.from_user.id):
        await callback.answer("⛔ Доступ ограничен", show_alert=True)
        return

    total = len(RECENT_LEADS)
    new_count = sum(1 for l in RECENT_LEADS if l.get("status_key") == "new")
    in_progress = sum(1 for l in RECENT_LEADS if l.get("status_key") == "in_progress")
    confirmed = sum(1 for l in RECENT_LEADS if l.get("status_key") == "confirmed")
    rejected = sum(1 for l in RECENT_LEADS if l.get("status_key") == "rejected")

    text = (
        f"📊 <b>Статистика цифровой приемной — {CLINIC_NAME}</b>\n\n"
        f"• Всего поступило заявок: <b>{total}</b>\n"
        f"• Новые заявки: <b>{new_count}</b> 🟡\n"
        f"• В обработке: <b>{in_progress}</b> 🔵\n"
        f"• Подтвержденных: <b>{confirmed}</b> 🟢\n"
        f"• Отклоненных: <b>{rejected}</b> 🔴\n\n"
        f"🕒 Время сервера: {datetime.now(TASHKENT_TZ).strftime('%d.%m.%Y %H:%M:%S')} (Ташкент)"
    )
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Обновить", callback_data="admin_stats")],
            [InlineKeyboardButton(text="◀️ В панель администратора", callback_data="admin_panel")],
        ]
    )
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@dp.callback_query(F.data == "admin_test_lead")
async def cb_admin_test_lead(callback: CallbackQuery) -> None:
    """Send a test patient lead card to verify notification formatting."""
    if not is_manager(callback.from_user.id):
        await callback.answer("⛔ Доступ ограничен", show_alert=True)
        return

    lead_id = len(RECENT_LEADS) + 1
    timestamp = datetime.now(TASHKENT_TZ).strftime("%d.%m.%Y %H:%M:%S")
    test_lead = {
        "id": lead_id,
        "full_name": "Каримов Тимур (Тестовый пациент)",
        "birth_year": "1994",
        "address": "Мирзо-Улугбекский р-н, ул. БИЙ",
        "service": "Первичная консультация и диагностика",
        "phone": "+998901234567",
        "timestamp": timestamp,
        "username": "test_patient",
        "status": "🟡 Новая",
        "status_key": "new",
    }
    RECENT_LEADS.append(test_lead)

    test_lead_text = (
        "🦷 <b>НОВАЯ ЗАПИСЬ НА ПРИЕМ (XDENT) — ТЕСТ</b>\n\n"
        f"👤 <b>Пациент:</b> Каримов Тимур (Тестовый пациент) (@test_patient)\n"
        f"📅 <b>Год рождения:</b> 1994\n"
        f"📍 <b>Адрес:</b> Мирзо-Улугбекский р-н, ул. БИЙ\n"
        f"🛠 <b>Услуга:</b> Первичная консультация и диагностика\n"
        f"📞 <b>Телефон:</b> <code>+998901234567</code>\n"
        f"⏱ <b>Время заявки:</b> {timestamp} (Ташкент)\n"
        f"📌 <b>Статус:</b> 🟡 Новая"
    )

    await callback.message.answer(
        test_lead_text,
        reply_markup=get_lead_actions_keyboard(lead_id, current_status="new"),
    )
    await callback.answer("✅ Тестовая заявка отправлена!")


@dp.callback_query(F.data.startswith("lead_take_"))
async def cb_lead_take(callback: CallbackQuery) -> None:
    """Manager takes lead into processing."""
    if not is_manager(callback.from_user.id):
        await callback.answer("⛔ Доступ ограничен", show_alert=True)
        return

    lead_id = int(callback.data.replace("lead_take_", ""))
    manager_name = html.escape(callback.from_user.first_name or "Менеджер")

    for l in RECENT_LEADS:
        if l["id"] == lead_id:
            l["status"] = f"🔵 В работе ({manager_name})"
            l["status_key"] = "in_progress"
            break

    current_text = callback.message.html_text or callback.message.text
    if "📌 <b>Статус:</b>" in current_text:
        new_text = current_text.split("📌 <b>Статус:</b>")[0] + f"📌 <b>Статус:</b> 🔵 В работе ({manager_name})"
    else:
        new_text = current_text + f"\n\n📌 <b>Статус:</b> 🔵 В работе ({manager_name})"

    await callback.message.edit_text(
        new_text,
        reply_markup=get_lead_actions_keyboard(lead_id, current_status="in_progress"),
    )
    await callback.answer("✅ Заявка принята в работу")


@dp.callback_query(F.data.startswith("lead_confirm_"))
async def cb_lead_confirm(callback: CallbackQuery) -> None:
    """Manager confirms appointment with patient."""
    if not is_manager(callback.from_user.id):
        await callback.answer("⛔ Доступ ограничен", show_alert=True)
        return

    lead_id = int(callback.data.replace("lead_confirm_", ""))
    manager_name = html.escape(callback.from_user.first_name or "Менеджер")

    for l in RECENT_LEADS:
        if l["id"] == lead_id:
            l["status"] = f"🟢 Подтверждено ({manager_name})"
            l["status_key"] = "confirmed"
            break

    current_text = callback.message.html_text or callback.message.text
    if "📌 <b>Статус:</b>" in current_text:
        new_text = current_text.split("📌 <b>Статус:</b>")[0] + f"📌 <b>Статус:</b> 🟢 Подтверждено ({manager_name})"
    else:
        new_text = current_text + f"\n\n📌 <b>Статус:</b> 🟢 Подтверждено ({manager_name})"

    await callback.message.edit_text(new_text, reply_markup=None)
    await callback.answer("🎉 Запись подтверждена!")


@dp.callback_query(F.data.startswith("lead_reject_"))
async def cb_lead_reject(callback: CallbackQuery) -> None:
    """Manager rejects / cancels lead."""
    if not is_manager(callback.from_user.id):
        await callback.answer("⛔ Доступ ограничен", show_alert=True)
        return

    lead_id = int(callback.data.replace("lead_reject_", ""))
    manager_name = html.escape(callback.from_user.first_name or "Менеджер")

    for l in RECENT_LEADS:
        if l["id"] == lead_id:
            l["status"] = f"🔴 Отклонено ({manager_name})"
            l["status_key"] = "rejected"
            break

    current_text = callback.message.html_text or callback.message.text
    if "📌 <b>Статус:</b>" in current_text:
        new_text = current_text.split("📌 <b>Статус:</b>")[0] + f"📌 <b>Статус:</b> 🔴 Отклонено ({manager_name})"
    else:
        new_text = current_text + f"\n\n📌 <b>Статус:</b> 🔴 Отклонено ({manager_name})"

    await callback.message.edit_text(new_text, reply_markup=None)
    await callback.answer("❌ Заявка отклонена")


@dp.callback_query(F.data == "menu_main")
async def cb_main_menu(callback: CallbackQuery, state: FSMContext) -> None:
    """Return to main menu."""
    await state.clear()
    user_id = callback.from_user.id
    text = (
        f"Главное меню цифровой приемной <b>{CLINIC_NAME}</b> 🦷\n\n"
        f"Чем мы можем вам помочь?"
    )
    await callback.message.edit_text(
        text,
        reply_markup=get_main_menu_keyboard(is_admin_user=is_manager(user_id)),
    )
    await callback.answer()


@dp.callback_query(F.data == "menu_services")
async def cb_services_menu(callback: CallbackQuery) -> None:
    """Show services categories."""
    text = (
        "🦷 <b>Услуги и цены клиники Dr. Shoxruz XDENT</b>\n\n"
        "Мы придерживаемся политики открытых и честных цен без скрытых доплат. "
        "Выберите направление стоматологии для получения подробной информации:"
    )
    await callback.message.edit_text(text, reply_markup=get_services_keyboard())
    await callback.answer()


@dp.callback_query(F.data.startswith("svc_"))
async def cb_service_detail(callback: CallbackQuery) -> None:
    """Show single service description and price."""
    svc_key = callback.data.replace("svc_", "")
    service = SERVICES_DATA.get(svc_key)

    if not service:
        await callback.answer("Услуга не найдена", show_alert=True)
        return

    await callback.message.edit_text(
        service["description"],
        reply_markup=get_service_detail_keyboard(svc_key),
    )
    await callback.answer()


@dp.callback_query(F.data == "menu_doctors")
async def cb_doctors_menu(callback: CallbackQuery) -> None:
    """Show clinic doctors and specializations."""
    await callback.message.edit_text(
        DOCTORS_TEXT,
        reply_markup=get_doctors_keyboard(),
    )
    await callback.answer()


@dp.callback_query(F.data == "menu_location")
async def cb_location_menu(callback: CallbackQuery) -> None:
    """Send location details and native Telegram map pin."""
    location_text = (
        f"📍 <b>Локация и контакты — {CLINIC_NAME}</b>\n\n"
        f"🏢 <b>Адрес:</b> {CLINIC_ADDRESS}\n"
        f"🕒 <b>Режим работы:</b> {CLINIC_SCHEDULE}\n"
        f"📞 <b>Единый телефон:</b> <code>{CLINIC_PHONE}</code>\n\n"
        f"<i>Ниже мы отправили геолокацию на карте, чтобы вам было удобно построить маршрут.</i>"
    )
    await callback.message.edit_text(location_text, reply_markup=get_location_keyboard())

    # Send native location coordinates
    try:
        await callback.message.answer_location(
            latitude=CLINIC_LATITUDE,
            longitude=CLINIC_LONGITUDE,
        )
    except Exception as exc:
        logger.warning("Could not send location coordinates: %s", exc)

    await callback.answer()


# ---------------------------------------------------------------------------
# FSM Lead Intake Flow (Booking)
# ---------------------------------------------------------------------------
SERVICE_PICK_MAP = {
    "consultation": "Первичная консультация и диагностика",
    "therapy": "Терапия и чистка (Проф. гигиена)",
    "pain": "Острая зубная боль / Лечение кариеса",
    "surgery": "Хирургия и имплантация зубов",
    "orthodontics": "Ортодонтия (Брекеты / Элайнеры)",
    "pediatric": "Детская стоматология",
}


@dp.callback_query(F.data == "booking_cancel")
@dp.message(Command("cancel"))
@dp.message(F.text.casefold() == "отмена")
@dp.message(F.text.casefold() == "❌ отменить запись")
async def cancel_booking(event: Union[Message, CallbackQuery], state: FSMContext) -> None:
    """Cancel booking flow at any step."""
    await state.clear()
    user_id = event.from_user.id

    cancel_msg = (
        "❌ <b>Запись на прием отменена.</b>\n\n"
        "Вы всегда можете вернуться к записи или выбрать интересующий раздел "
        "в меню внизу экрана 👇"
    )

    reply_kb = get_bottom_reply_keyboard(is_admin_user=is_manager(user_id))
    if isinstance(event, CallbackQuery):
        await event.message.answer(cancel_msg, reply_markup=reply_kb)
        await event.answer()
    else:
        await event.answer(cancel_msg, reply_markup=reply_kb)


@dp.callback_query(F.data == "book_start")
async def start_booking_generic(callback: CallbackQuery, state: FSMContext) -> None:
    """Initiate booking without preselected service (Step 1)."""
    await state.set_state(BookingState.service)
    text = (
        "📝 <b>Запись на прием в Dr. Shoxruz XDENT</b>\n\n"
        "<b>Шаг 1 из 5:</b> Выберите услугу или проблему из списка ниже "
        "(или опишите вашу ситуацию своими словами):"
    )
    await callback.message.answer(text, reply_markup=get_services_choice_keyboard())
    await callback.answer()


@dp.callback_query(BookingState.service, F.data.startswith("pick_svc_"))
async def cb_pick_service(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle 1-tap service selection on Step 1."""
    svc_key = callback.data.replace("pick_svc_", "")
    if svc_key == "custom":
        await callback.message.answer(
            "Пожалуйста, напишите кратко текстом вашу проблему или желаемую услугу:",
            reply_markup=get_cancel_inline_keyboard(),
        )
        await callback.answer()
        return

    svc_title = SERVICE_PICK_MAP.get(svc_key, svc_key)
    await state.update_data(service=svc_title)
    await state.set_state(BookingState.full_name)

    first_name = callback.from_user.first_name
    text = (
        f"📝 <b>Выбрано:</b> <i>{html.escape(svc_title)}</i>\n\n"
        "<b>Шаг 2 из 5:</b> Укажите ваше <b>ФИО</b> (например: <i>Каримов Тимур</i>).\n\n"
        "Вы можете нажать кнопку ниже, чтобы использовать имя вашего профиля, "
        "или ввести ФИО вручную:"
    )
    await callback.message.answer(text, reply_markup=get_name_choice_keyboard(first_name))
    await callback.answer()


@dp.callback_query(F.data.startswith("book_with_svc_"))
async def start_booking_with_service(callback: CallbackQuery, state: FSMContext) -> None:
    """Initiate booking with pre-selected service (Skips to Step 2)."""
    svc_key = callback.data.replace("book_with_svc_", "")
    svc_title = SERVICES_DATA.get(svc_key, {}).get("title", "Стоматологическая услуга")

    await state.update_data(service=svc_title)
    await state.set_state(BookingState.full_name)

    first_name = callback.from_user.first_name
    text = (
        f"📝 <b>Запись на прием:</b> <i>{html.escape(svc_title)}</i>\n\n"
        "<b>Шаг 2 из 5:</b> Укажите ваше <b>ФИО</b> (например: <i>Каримов Тимур</i>).\n\n"
        "Вы можете нажать кнопку ниже, чтобы использовать имя вашего профиля, "
        "или ввести ФИО вручную:"
    )
    await callback.message.answer(text, reply_markup=get_name_choice_keyboard(first_name))
    await callback.answer()


@dp.message(BookingState.service)
async def process_service(message: Message, state: FSMContext) -> None:
    """Process custom service/problem text (Step 1 -> Step 2)."""
    service_text = message.text.strip() if message.text else ""
    if len(service_text) < 2:
        await message.answer(
            "Пожалуйста, выберите услугу кнопкой или опишите проблему текстом:",
            reply_markup=get_services_choice_keyboard(),
        )
        return

    await state.update_data(service=service_text)
    await state.set_state(BookingState.full_name)

    first_name = message.from_user.first_name
    text = (
        f"📝 <b>Выбрано:</b> <i>{html.escape(service_text)}</i>\n\n"
        "<b>Шаг 2 из 5:</b> Укажите ваше <b>ФИО</b> (например: <i>Каримов Тимур</i>).\n\n"
        "Вы можете нажать кнопку ниже, чтобы использовать имя вашего профиля, "
        "или ввести ФИО вручную:"
    )
    await message.answer(text, reply_markup=get_name_choice_keyboard(first_name))


@dp.callback_query(BookingState.full_name, F.data.startswith("pick_name_"))
async def cb_pick_name(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle 1-tap name selection on Step 2."""
    name_val = callback.data.replace("pick_name_", "")
    await state.update_data(full_name=name_val)
    await state.set_state(BookingState.birth_year)

    text = (
        f"Принято, <b>{html.escape(name_val)}</b>!\n\n"
        "<b>Шаг 3 из 5:</b> Укажите ваш <b>год рождения</b> (необходимо для амбулаторной карты).\n\n"
        "Выберите год на кнопках ниже или введите вручную (например: <code>1995</code>):"
    )
    await callback.message.answer(text, reply_markup=get_year_choice_keyboard())
    await callback.answer()


@dp.message(BookingState.full_name)
async def process_full_name(message: Message, state: FSMContext) -> None:
    """Process patient full name (Step 2 -> Step 3)."""
    name_text = message.text.strip() if message.text else ""
    if len(name_text) < 3 or any(char.isdigit() for char in name_text):
        await message.answer(
            "⚠️ Пожалуйста, введите корректные имя и фамилию (без цифр, например: <i>Каримов Тимур</i>) "
            "или нажмите кнопку с вашим именем ниже:",
            reply_markup=get_name_choice_keyboard(message.from_user.first_name),
        )
        return

    await state.update_data(full_name=name_text)
    await state.set_state(BookingState.birth_year)

    text = (
        f"Принято, <b>{html.escape(name_text)}</b>!\n\n"
        "<b>Шаг 3 из 5:</b> Укажите ваш <b>год рождения</b> (необходимо для амбулаторной карты).\n\n"
        "Выберите год на кнопках ниже или введите вручную (например: <code>1995</code>):"
    )
    await message.answer(text, reply_markup=get_year_choice_keyboard())


@dp.callback_query(BookingState.birth_year, F.data.startswith("pick_year_"))
async def cb_pick_year(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle 1-tap birth year selection on Step 3."""
    year_val = callback.data.replace("pick_year_", "")
    if year_val == "custom":
        await callback.message.answer(
            "Введите ваш 4-значный год рождения (например: <code>1992</code>):",
            reply_markup=get_cancel_inline_keyboard(),
        )
        await callback.answer()
        return

    await state.update_data(birth_year=year_val)
    await state.set_state(BookingState.address)

    text = (
        "<b>Шаг 4 из 5:</b> Выберите ваш <b>район проживания в Ташкенте</b>:\n\n"
        "<i>(Или введите точный адрес/ориентир текстом)</i>"
    )
    await callback.message.answer(text, reply_markup=get_districts_keyboard())
    await callback.answer()


@dp.message(BookingState.birth_year)
async def process_birth_year(message: Message, state: FSMContext) -> None:
    """Process patient birth year with validation (Step 3 -> Step 4)."""
    year_text = message.text.strip() if message.text else ""
    current_year = datetime.now(TASHKENT_TZ).year

    if not year_text.isdigit() or not (1920 <= int(year_text) <= current_year):
        await message.answer(
            f"⚠️ Пожалуйста, выберите год на кнопках или введите от 1920 до {current_year}:",
            reply_markup=get_year_choice_keyboard(),
        )
        return

    await state.update_data(birth_year=year_text)
    await state.set_state(BookingState.address)

    text = (
        "<b>Шаг 4 из 5:</b> Выберите ваш <b>район проживания в Ташкенте</b>:\n\n"
        "<i>(Или введите точный адрес/ориентир текстом)</i>"
    )
    await message.answer(text, reply_markup=get_districts_keyboard())


@dp.callback_query(BookingState.address, F.data.startswith("pick_dist_"))
async def cb_pick_district(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle 1-tap district selection on Step 4."""
    dist_val = callback.data.replace("pick_dist_", "")
    await state.update_data(address=dist_val)
    await state.set_state(BookingState.phone)

    text = (
        f"📍 <b>Район:</b> {html.escape(dist_val)}\n\n"
        "<b>Шаг 5 из 5:</b> Отправьте ваш <b>контактный номер телефона</b>.\n\n"
        "Нажмите кнопку <b>«📱 Поделиться контактом»</b> внизу экрана "
        "или введите номер вручную (например: <code>+998901234567</code>):"
    )
    await callback.message.answer(text, reply_markup=get_contact_reply_keyboard())
    await callback.answer()


@dp.message(BookingState.address)
async def process_address(message: Message, state: FSMContext) -> None:
    """Process patient address/district (Step 4 -> Step 5)."""
    address_text = message.text.strip() if message.text else ""
    if len(address_text) < 3:
        await message.answer(
            "⚠️ Пожалуйста, выберите район кнопкой или укажите ориентир (не менее 3 символов):",
            reply_markup=get_districts_keyboard(),
        )
        return

    await state.update_data(address=address_text)
    await state.set_state(BookingState.phone)

    text = (
        "<b>Шаг 5 из 5:</b> Отправьте ваш <b>контактный номер телефона</b>.\n\n"
        "Нажмите кнопку <b>«📱 Поделиться контактом»</b> внизу экрана "
        "или введите номер вручную (например: <code>+998901234567</code>):"
    )
    await message.answer(text, reply_markup=get_contact_reply_keyboard())


@dp.message(BookingState.phone, F.contact)
@dp.message(BookingState.phone, F.text)
async def process_phone_and_finalize(message: Message, state: FSMContext, bot: Bot) -> None:
    """Process phone number, finalize lead, and alert clinic admins."""
    # Extract phone from contact or typed text
    if message.contact:
        phone_number = message.contact.phone_number
        if not phone_number.startswith("+"):
            phone_number = f"+{phone_number}"
    else:
        phone_raw = message.text.strip()
        # Basic validation: must contain at least 7 digits
        digits_only = "".join(filter(str.isdigit, phone_raw))
        if len(digits_only) < 7:
            await message.answer(
                "⚠️ Пожалуйста, введите корректный номер телефона (например: <code>+998901234567</code>) "
                "или нажмите кнопку «📱 Поделиться контактом» внизу:",
                reply_markup=get_contact_reply_keyboard(),
            )
            return
        phone_number = phone_raw

    # Collect all lead data
    data = await state.get_data()
    await state.clear()

    full_name = data.get("full_name", "Не указано")
    birth_year = data.get("birth_year", "Не указано")
    address = data.get("address", "Не указано")
    service = data.get("service", "Не указано")
    timestamp = datetime.now(TASHKENT_TZ).strftime("%d.%m.%Y %H:%M:%S")

    # Record lead in memory store
    lead_id = len(RECENT_LEADS) + 1
    lead_record = {
        "id": lead_id,
        "full_name": full_name,
        "birth_year": birth_year,
        "address": address,
        "service": service,
        "phone": phone_number,
        "timestamp": timestamp,
        "username": message.from_user.username,
        "status": "🟡 Новая",
        "status_key": "new",
    }
    RECENT_LEADS.append(lead_record)

    # Format user reference
    user_id = message.from_user.id
    if message.from_user.username:
        user_display = f"@{message.from_user.username}"
    else:
        user_display = f'<a href="tg://user?id={user_id}">{html.escape(full_name)}</a>'

    # Admin lead notification
    admin_lead_text = (
        "🦷 <b>НОВАЯ ЗАПИСЬ НА ПРИЕМ (XDENT)</b>\n\n"
        f"👤 <b>Пациент:</b> {html.escape(full_name)} ({user_display})\n"
        f"📅 <b>Год рождения:</b> {html.escape(birth_year)}\n"
        f"📍 <b>Адрес:</b> {html.escape(address)}\n"
        f"🛠 <b>Услуга:</b> {html.escape(service)}\n"
        f"📞 <b>Телефон:</b> <code>{html.escape(phone_number)}</code>\n"
        f"⏱ <b>Время заявки:</b> {timestamp} (Ташкент)\n"
        f"📌 <b>Статус:</b> 🟡 Новая"
    )

    # Dispatch to all authorized manager chats
    for target_chat_id in ADMIN_IDS:
        try:
            await bot.send_message(
                chat_id=target_chat_id,
                text=admin_lead_text,
                reply_markup=get_lead_actions_keyboard(lead_id, current_status="new"),
            )
            logger.info("Successfully dispatched lead #%d to manager chat: %s", lead_id, target_chat_id)
        except Exception as exc:
            logger.error("Failed to send lead to manager chat %s: %s", target_chat_id, exc)

    # User confirmation message
    user_confirm_text = (
        f"✅ <b>Спасибо, {html.escape(full_name)}! Ваша запись принята.</b>\n\n"
        f"📋 <b>Детали вашей заявки:</b>\n"
        f"• <b>Услуга:</b> {html.escape(service)}\n"
        f"• <b>Год рождения:</b> {html.escape(birth_year)}\n"
        f"• <b>Район:</b> {html.escape(address)}\n"
        f"• <b>Контактный телефон:</b> {html.escape(phone_number)}\n\n"
        f"📞 Координатор клиники <b>{CLINIC_NAME}</b> свяжется с вами "
        f"в ближайшее время для подтверждения и подбора удобного времени визита.\n\n"
        f"<i>При возникновении срочных вопросов звоните нам 24/7:</i> <code>{CLINIC_PHONE}</code>"
    )

    # Restore the persistent bottom keyboard
    await message.answer(
        user_confirm_text,
        reply_markup=get_bottom_reply_keyboard(is_admin_user=is_manager(user_id)),
    )


# ---------------------------------------------------------------------------
# Application Entrypoint
# ---------------------------------------------------------------------------
async def main() -> None:
    """Start polling."""
    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE" or not BOT_TOKEN:
        logger.warning(
            "⚠️ ВНИМАНИЕ: BOT_TOKEN не установлен! Задайте BOT_TOKEN в файле .env или переменных окружения."
        )

    logger.info("Starting %s Telegram Bot...", CLINIC_NAME)

    # Delete webhook if previously set to ensure polling works smoothly
    try:
        await bot.delete_webhook(drop_pending_updates=True)
    except Exception as exc:
        logger.warning("Webhook cleanup warning: %s", exc)

    # Start polling
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped.")
