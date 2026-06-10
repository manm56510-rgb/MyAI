import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters, PreCheckoutQueryHandler
from datetime import datetime, timedelta
import json
import os
from transformers import pipeline

# Налаштування логування
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Конфігурація
OWNER_ID = 8080673594
BOT_TOKEN = "8891884892:AAGhfErbFqhUxkP5-ITf6mOTSZ9aY6Yops4"
COMPANY_NAME = "UkraineAI"
BOT_NAME = "Ukrainian Helper"

# Файл для зберігання даних користувачів
DATA_FILE = "users_data.json"

# Стандартні значення
DEFAULT_BALANCE = 0
STARS_TO_HELPCOINS = 100  # 1 зірка = 100 HelpCoins
GENERATOR_COST = 18000
PLUS_COST = 500000
PLUS_DURATION = 5  # днів

# Ініціалізація AI моделі
print("⏳ Завантаження AI моделі... (перший запуск може тривати 1-2 хвилини)")
try:
    qa_pipeline = pipeline("question-answering", model="deepset/roberta-base-squad2")
    text_generation = pipeline("text-generation", model="gpt2")
    logger.info("✅ AI моделі успішно завантажені")
except Exception as e:
    logger.warning(f"⚠️ Помилка завантаження моделей: {e}")
    qa_pipeline = None
    text_generation = None

class UserData:
    def __init__(self):
        self.users = self.load_data()
    
    def load_data(self):
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return {}
        return {}
    
    def save_data(self):
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.users, f, ensure_ascii=False, indent=2)
    
    def get_user(self, user_id):
        user_id_str = str(user_id)
        if user_id_str not in self.users:
            self.users[user_id_str] = {
                "username": "Unknown",
                "balance": DEFAULT_BALANCE,
                "stars": 0,
                "has_generator": False,
                "generator_type": None,  # "3d" або "permanent"
                "generator_expiry": None,
                "has_plus": False,
                "plus_expiry": None,
                "partner_enabled": False,
                "earnings": 0,
                "ai_requests": 0
            }
            self.save_data()
        return self.users[user_id_str]
    
    def set_balance(self, user_id, amount):
        user = self.get_user(user_id)
        user["balance"] = amount
        self.save_data()
    
    def add_balance(self, user_id, amount):
        user = self.get_user(user_id)
        user["balance"] += amount
        self.save_data()
    
    def set_username(self, user_id, username):
        user = self.get_user(user_id)
        user["username"] = username
        self.save_data()

user_data = UserData()

def get_main_keyboard():
    """Повертає головну клавіатуру"""
    keyboard = [
        [InlineKeyboardButton("💬 Запитати AI", callback_data="ask_ai")],
        [InlineKeyboardButton("💰 Баланс", callback_data="balance")],
        [InlineKeyboardButton("⭐ Обміняти зірки", callback_data="exchange_stars")],
        [InlineKeyboardButton("🎁 Підписки", callback_data="subscriptions")],
        [InlineKeyboardButton("📊 Мої дані", callback_data="my_data")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_back_keyboard():
    """Повертає кнопку назад"""
    keyboard = [[InlineKeyboardButton("👈 Назад", callback_data="back_to_menu")]]
    return InlineKeyboardMarkup(keyboard)

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data.set_username(user.id, user.username or user.first_name)
    
    await update.message.reply_text(
        f"🤖 Ласкаво просимо до {BOT_NAME}!\n\n"
        f"Компанія: {COMPANY_NAME}\n\n"
        f"💬 Пишіть запитання - я відповім вам!\n\n"
        f"Оберіть опцію нижче:",
        reply_markup=get_main_keyboard()
    )

# Обробка текстових повідомлень (запитання до AI)
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = user_data.get_user(user_id)
    question = update.message.text
    
    # Перевірка, чи користувач має доступ до AI
    has_generator = user["has_generator"]
    has_plus = user["has_plus"]
    
    # Перевірка терміну дії Generator
    if has_generator and user.get("generator_type") == "3d":
        expiry = user.get("generator_expiry")
        if expiry:
            expiry_date = datetime.fromisoformat(expiry)
            if datetime.now() > expiry_date:
                user["has_generator"] = False
                user["generator_expiry"] = None
                user_data.save_data()
                has_generator = False
    
    # Перевірка терміну дії Plus
    if has_plus and user.get("plus_expiry"):
        expiry_date = datetime.fromisoformat(user["plus_expiry"])
        if datetime.now() > expiry_date:
            user["has_plus"] = False
            user["plus_expiry"] = None
            user_data.save_data()
            has_plus = False
    
    # Якщо немає жодної підписки
    if not has_generator and not has_plus:
        keyboard = [
            [InlineKeyboardButton(f"🎯 Generator - {GENERATOR_COST:,} HelpCoins", callback_data="buy_generator_direct")],
            [InlineKeyboardButton(f"💎 Plus - {PLUS_COST:,} HelpCoins", callback_data="buy_plus_direct")],
            [InlineKeyboardButton("💬 Запитати AI", callback_data="ask_ai")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            f"❌ Потрібна підписка Generator або Plus для використання AI!\n\n"
            f"Оберіть підписку:",
            reply_markup=reply_markup
        )
        return
    
    # Відправка повідомлення про обробку
    processing_msg = await update.message.reply_text("⏳ Обробляю ваше запитання...")
    
    try:
        # Генерування відповіді AI
        response = generate_ai_response(question)
        
        # Збільшення лічильника запитань
        user["ai_requests"] += 1
        user_data.save_data()
        
        # Редагування повідомлення з відповіддю
        keyboard = [
            [InlineKeyboardButton("💬 Запитати AI", callback_data="ask_ai")],
            [InlineKeyboardButton("👈 Назад", callback_data="back_to_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await processing_msg.edit_text(
            f"🤖 <b>Відповідь AI:</b>\n\n"
            f"{response}",
            parse_mode="HTML",
            reply_markup=reply_markup
        )
    except Exception as e:
        logger.error(f"Помилка при обробці запитання: {e}")
        await processing_msg.edit_text(
            f"❌ Помилка при обробці запитання.\n\n"
            f"Спробуйте пізніше або скоротіть запитання."
        )

def generate_ai_response(question):
    """Генерування відповіді на запитання"""
    try:
        # Спроба використати модель для відповідей на запитання
        if qa_pipeline:
            # Контекст для відповідей
            context = f"""
            Це штучний інтелект для Telegram бота Ukrainian Helper компанії UkraineAI.
            Відповідай коротко і по суті українською мовою.
            {question}
            """
            
            try:
                result = qa_pipeline(question=question, context=context)
                answer = result.get('answer', '')
                if answer:
                    return f"{answer}"
            except:
                pass
        
        # Якщо перший метод не спрацював, використовуємо text-generation
        if text_generation:
            response = text_generation(question, max_length=150, num_return_sequences=1)
            if response:
                return response[0]['generated_text']
        
        # Якщо нічого не спрацювало - відповідь за замовчуванням
        return generate_smart_response(question)
    
    except Exception as e:
        logger.error(f"Помилка при генеруванні AI відповіді: {e}")
        return generate_smart_response(question)

def generate_smart_response(question):
    """Генерування розумної відповіді без AI моделей"""
    question_lower = question.lower()
    
    # Словник базових відповідей
    responses = {
        "привіт": "👋 Привіт! Я Ukrainian Helper - штучний інтелект компанії UkraineAI. Чим я можу вам допомогти?",
        "як дела": "😊 Чудово! Готовий допомогти вам з будь-якими запитаннями. Що вас цікавить?",
        "хто ти": "🤖 Я Ukrainian Helper - AI асистент бота UkraineAI. Я готовий відповідати на ваші запитання!",
        "скільки": "🤔 Це залежить від контексту. Розкажіть більше деталей, і я спробую допомогти!",
        "допомога": "📞 Я тут, щоб допомогти! Запитуйте що завгодно, і я постараюсь відповісти.",
        "спасибо": "😊 Будь ласка! Рад був допомогти!",
        "дякую": "😊 Будь ласка! Будь коли готовий допомогти!",
    }
    
    # Пошук ключових слів у запитанні
    for key, value in responses.items():
        if key in question_lower:
            return value
    
    # Якщо ключові слова не знайдені
    default_responses = [
        f"🤔 Цікаве запитання! \"{question}\" - це дуже цікаво. Я аналізую...",
        f"💭 Ви запитали про: \"{question}\" - це чудове питання!",
        f"📝 Ваше запитання: \"{question}\" - я над цим думаю...",
        f"🧠 Розумію ваше запитання. Щодо \"{question}\", то це залежить від багатьох факторів.",
    ]
    
    import random
    return random.choice(default_responses)

# Команда /help (тільки для власника)
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("❌ Ця команда доступна тільки для власника бота.")
        return
    
    help_text = f"""
🔧 КОМАНДИ ВЛАСНИКА БОТА (@{context.bot.username})

💰 УПРАВЛІННЯ БАЛАНСОМ:
/setbalance @username <кількість> - Встановити баланс користувачу
/setmybalance <кількість> - Встановити собі баланс
Приклад: /setbalance @john 5000

🎁 ГЕНЕРАТОР (Generator):
/givegenerator @username <permanent/3d> - Дати доступ
/takegenerator @username - Забрати доступ
Приклад: /givegenerator @john permanent

⭐ ПІДПИСКА PLUS:
/giveplus @username <permanent/3d> - Дати Plus
/takeplus @username - Забрати Plus
Приклад: /giveplus @john 3d

Вартість Plus: {PLUS_COST:,} HelpCoins на {PLUS_DURATION} днів
Вартість Generator: {GENERATOR_COST:,} HelpCoins

⚠️ ID СПОСОБ:
Усі команди також працюють з ID:
/setbalance 123456789 5000
/givegenerator 123456789 permanent
    """
    
    await update.message.reply_text(help_text)

# Команда /setbalance
async def setbalance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("❌ Доступна тільки власнику.")
        return
    
    if len(context.args) < 2:
        await update.message.reply_text("❌ Використання: /setbalance @username <кількість>\nАбо: /setbalance <ID> <кількість>")
        return
    
    try:
        identifier = context.args[0]
        amount = int(context.args[1])
        
        target_id = find_user_id(identifier)
        if not target_id:
            await update.message.reply_text("❌ Користувача не знайдено.")
            return
        
        user_data.set_balance(target_id, amount)
        await update.message.reply_text(f"✅ Баланс встановлено: {amount:,} HelpCoins")
    except ValueError:
        await update.message.reply_text("❌ Кількість має бути числом.")

# Команда /setmybalance
async def setmybalance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 1:
        await update.message.reply_text("❌ Використання: /setmybalance <кількість>")
        return
    
    try:
        amount = int(context.args[0])
        user_data.set_balance(update.effective_user.id, amount)
        await update.message.reply_text(f"✅ Ваш баланс встановлено на {amount:,} HelpCoins")
    except ValueError:
        await update.message.reply_text("❌ Кількість має бути числом.")

# Команда /givegenerator
async def givegenerator(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("❌ Доступна тільки власнику.")
        return
    
    if len(context.args) < 2:
        await update.message.reply_text("❌ Використання: /givegenerator @username <permanent/3d>\nАбо: /givegenerator <ID> <permanent/3d>")
        return
    
    identifier = context.args[0]
    gen_type = context.args[1].lower()
    
    if gen_type not in ["permanent", "3d"]:
        await update.message.reply_text("❌ Тип має бути 'permanent' або '3d'")
        return
    
    target_id = find_user_id(identifier)
    if not target_id:
        await update.message.reply_text("❌ Користувача не знайдено.")
        return
    
    user = user_data.get_user(target_id)
    user["has_generator"] = True
    user["generator_type"] = gen_type
    if gen_type == "3d":
        user["generator_expiry"] = (datetime.now() + timedelta(days=3)).isoformat()
    else:
        user["generator_expiry"] = None
    user_data.save_data()
    
    await update.message.reply_text(f"✅ Generator видано користувачу ({gen_type})")

# Команда /takegenerator
async def takegenerator(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("❌ Доступна тільки власнику.")
        return
    
    if len(context.args) < 1:
        await update.message.reply_text("❌ Використання: /takegenerator @username\nАбо: /takegenerator <ID>")
        return
    
    identifier = context.args[0]
    target_id = find_user_id(identifier)
    if not target_id:
        await update.message.reply_text("❌ Користувача не знайдено.")
        return
    
    user = user_data.get_user(target_id)
    user["has_generator"] = False
    user["generator_type"] = None
    user["generator_expiry"] = None
    user_data.save_data()
    
    await update.message.reply_text(f"✅ Generator забрано у користувача")

# Команда /giveplus
async def giveplus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("❌ Доступна тільки власнику.")
        return
    
    if len(context.args) < 2:
        await update.message.reply_text("❌ Використання: /giveplus @username <permanent/3d>\nАбо: /giveplus <ID> <permanent/3d>")
        return
    
    identifier = context.args[0]
    plus_type = context.args[1].lower()
    
    if plus_type not in ["permanent", "3d"]:
        await update.message.reply_text("❌ Тип має бути 'permanent' або '3d'")
        return
    
    target_id = find_user_id(identifier)
    if not target_id:
        await update.message.reply_text("❌ Користувача не знайдено.")
        return
    
    user = user_data.get_user(target_id)
    user["has_plus"] = True
    if plus_type == "3d":
        user["plus_expiry"] = (datetime.now() + timedelta(days=PLUS_DURATION)).isoformat()
    else:
        user["plus_expiry"] = None
    user_data.save_data()
    
    await update.message.reply_text(f"✅ Plus видано користувачу ({plus_type})")

# Команда /takeplus
async def takeplus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("❌ Доступна тільки власнику.")
        return
    
    if len(context.args) < 1:
        await update.message.reply_text("❌ Використання: /takeplus @username\nАбо: /takeplus <ID>")
        return
    
    identifier = context.args[0]
    target_id = find_user_id(identifier)
    if not target_id:
        await update.message.reply_text("❌ Користувача не знайдено.")
        return
    
    user = user_data.get_user(target_id)
    user["has_plus"] = False
    user["plus_expiry"] = None
    user_data.save_data()
    
    await update.message.reply_text(f"✅ Plus забрано у користувача")

# Команда /helpplus
async def helpplus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = user_data.get_user(update.effective_user.id)
    
    if not user["has_plus"]:
        keyboard = [[InlineKeyboardButton(f"🎁 Купити Plus за {PLUS_COST:,} HelpCoins", callback_data="buy_plus")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            f"💎 ПІДПИСКА PLUS\n\n"
            f"Можливості:\n"
            f"✨ Вам потрібна підписка Plus",
            reply_markup=reply_markup
        )
    else:
        expiry = user.get("plus_expiry")
        if expiry:
            expiry_date = datetime.fromisoformat(expiry)
            days_left = (expiry_date - datetime.now()).days
            await update.message.reply_text(f"✅ У вас активна підписка Plus!\nДнів залишилось: {days_left}")
        else:
            await update.message.reply_text("✅ У вас постійна підписка Plus!")

# Обробка платежів зірками
async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Відповідь на попередню перевірку платежу"""
    query = update.pre_checkout_query
    # Відповіді "OK" на попередню перевірку
    await query.answer(ok=True)

async def successful_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обробка успішного платежу зірками"""
    user_id = update.effective_user.id
    user = user_data.get_user(user_id)
    
    # Отримуємо кількість зірок
    payload = update.message.successful_payment.invoice_payload
    
    if payload == "buy_stars_1":
        # 1 зірка = 100 HelpCoins
        stars_amount = 1
        helpcoins = STARS_TO_HELPCOINS
    elif payload == "buy_stars_5":
        # 5 зірок = 500 HelpCoins
        stars_amount = 5
        helpcoins = STARS_TO_HELPCOINS * 5
    elif payload == "buy_stars_10":
        # 10 зірок = 1000 HelpCoins
        stars_amount = 10
        helpcoins = STARS_TO_HELPCOINS * 10
    else:
        stars_amount = 1
        helpcoins = STARS_TO_HELPCOINS
    
    # Додаємо баланс
    user["balance"] += helpcoins
    user["stars"] += stars_amount
    user_data.save_data()
    
    keyboard = [
        [InlineKeyboardButton("💬 Запитати AI", callback_data="ask_ai")],
        [InlineKeyboardButton("👈 Назад", callback_data="back_to_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"✅ Платіж успішно оброблено!\n\n"
        f"⭐ Отримано зірок: {stars_amount}\n"
        f"💰 Отримано HelpCoins: {helpcoins:,}\n"
        f"💵 Новий баланс: {user['balance']:,} HelpCoins",
        reply_markup=reply_markup
    )

# Функція пошуку користувача
def find_user_id(identifier):
    """Пошук ID користувача за username або ID"""
    try:
        return int(identifier.lstrip("@"))
    except ValueError:
        pass
    
    for user_id_str, user_info in user_data.users.items():
        if user_info.get("username", "").lower() == identifier.lstrip("@").lower():
            return int(user_id_str)
    
    return None

# Callback кнопки
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "ask_ai":
        user = user_data.get_user(query.from_user.id)
        has_generator = user["has_generator"]
        has_plus = user["has_plus"]
        
        # Перевірка терміну дії підписок
        if has_generator and user.get("generator_type") == "3d":
            expiry = user.get("generator_expiry")
            if expiry:
                expiry_date = datetime.fromisoformat(expiry)
                if datetime.now() > expiry_date:
                    user["has_generator"] = False
                    user["generator_expiry"] = None
                    user_data.save_data()
                    has_generator = False
        
        if has_plus and user.get("plus_expiry"):
            expiry_date = datetime.fromisoformat(user["plus_expiry"])
            if datetime.now() > expiry_date:
                user["has_plus"] = False
                user["plus_expiry"] = None
                user_data.save_data()
                has_plus = False
        
        if has_generator or has_plus:
            keyboard = [
                [InlineKeyboardButton("💬 Запитати AI", callback_data="ask_ai")],
                [InlineKeyboardButton("👈 Назад", callback_data="back_to_menu")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text("💬 Напишіть своє запитання, і я вам відповім!\n\nПросто пишіть в чат 👇", reply_markup=reply_markup)
        else:
            keyboard = [
                [InlineKeyboardButton(f"🎯 Generator", callback_data="buy_generator_direct")],
                [InlineKeyboardButton(f"💎 Plus", callback_data="buy_plus_direct")],
                [InlineKeyboardButton("💬 Запитати AI", callback_data="ask_ai")],
                [InlineKeyboardButton("👈 Назад", callback_data="back_to_menu")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                f"❌ Потрібна підписка для AI!\n\n"
                f"🎯 Generator: {GENERATOR_COST:,} HelpCoins (на 3 дні)\n"
                f"💎 Plus: {PLUS_COST:,} HelpCoins (на {PLUS_DURATION} днів)",
                reply_markup=reply_markup
            )
    
    elif query.data == "balance":
        user = user_data.get_user(query.from_user.id)
        keyboard = [
            [InlineKeyboardButton("💬 Запитати AI", callback_data="ask_ai")],
            [InlineKeyboardButton("👈 Назад", callback_data="back_to_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(f"💰 Ваш баланс: {user['balance']:,} HelpCoins", reply_markup=reply_markup)
    
    elif query.data == "exchange_stars":
        keyboard = [
            [InlineKeyboardButton("⭐ 1 зірка = 100 HelpCoins", callback_data="buy_stars_1")],
            [InlineKeyboardButton("⭐ 5 зірок = 500 HelpCoins", callback_data="buy_stars_5")],
            [InlineKeyboardButton("⭐ 10 зірок = 1000 HelpCoins", callback_data="buy_stars_10")],
            [InlineKeyboardButton("💬 Запитати AI", callback_data="ask_ai")],
            [InlineKeyboardButton("👈 Назад", callback_data="back_to_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            f"⭐ ОБМІН TELEGRAM ЗІРОК\n\n"
            f"Оберіть кількість зірок для обміну:\n\n"
            f"1 ⭐ = {STARS_TO_HELPCOINS} HelpCoins\n"
            f"5 ⭐ = {STARS_TO_HELPCOINS * 5} HelpCoins\n"
            f"10 ⭐ = {STARS_TO_HELPCOINS * 10} HelpCoins",
            reply_markup=reply_markup
        )
    
    elif query.data == "buy_stars_1":
        await send_invoice(update, context, 1)
    elif query.data == "buy_stars_5":
        await send_invoice(update, context, 5)
    elif query.data == "buy_stars_10":
        await send_invoice(update, context, 10)
    
    elif query.data == "subscriptions":
        keyboard = [
            [InlineKeyboardButton("🎯 Generator", callback_data="sub_generator")],
            [InlineKeyboardButton("💎 Plus", callback_data="sub_plus")],
            [InlineKeyboardButton("💬 Запитати AI", callback_data="ask_ai")],
            [InlineKeyboardButton("👈 Назад", callback_data="back_to_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("🎁 ПІДПИСКИ", reply_markup=reply_markup)
    
    elif query.data == "sub_generator":
        user = user_data.get_user(query.from_user.id)
        if user["has_generator"]:
            gen_type = user.get("generator_type", "unknown")
            if gen_type == "3d" and user.get("generator_expiry"):
                expiry_date = datetime.fromisoformat(user["generator_expiry"])
                days_left = (expiry_date - datetime.now()).days
                keyboard = [
                    [InlineKeyboardButton("💬 Запитати AI", callback_data="ask_ai")],
                    [InlineKeyboardButton("👈 Назад", callback_data="subscriptions")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await query.edit_message_text(f"✅ Ви маєте Generator!\n\n🎯 Тип: {gen_type}\nДнів залишилось: {days_left}", reply_markup=reply_markup)
            else:
                keyboard = [
                    [InlineKeyboardButton("💬 Запитати AI", callback_data="ask_ai")],
                    [InlineKeyboardButton("👈 Назад", callback_data="subscriptions")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await query.edit_message_text(f"✅ Ви маєте постійний Generator!", reply_markup=reply_markup)
        else:
            keyboard = [
                [InlineKeyboardButton(f"🎯 Купити за {GENERATOR_COST:,} HelpCoins", callback_data="buy_generator_direct")],
                [InlineKeyboardButton("💬 Запитати AI", callback_data="ask_ai")],
                [InlineKeyboardButton("👈 Назад", callback_data="subscriptions")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                f"🎯 GENERATOR\n\n"
                f"🤖 AI асистент + Генерація контенту\n\n"
                f"Вартість: {GENERATOR_COST:,} HelpCoins на 3 дні",
                reply_markup=reply_markup
            )
    
    elif query.data == "sub_plus":
        user = user_data.get_user(query.from_user.id)
        if user["has_plus"]:
            expiry = user.get("plus_expiry")
            if expiry:
                expiry_date = datetime.fromisoformat(expiry)
                days_left = (expiry_date - datetime.now()).days
                keyboard = [
                    [InlineKeyboardButton("💬 Запитати AI", callback_data="ask_ai")],
                    [InlineKeyboardButton("👈 Назад", callback_data="subscriptions")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await query.edit_message_text(f"✅ Ви маєте Plus!\n\nДнів залишилось: {days_left}", reply_markup=reply_markup)
            else:
                keyboard = [
                    [InlineKeyboardButton("💬 Запитати AI", callback_data="ask_ai")],
                    [InlineKeyboardButton("👈 Назад", callback_data="subscriptions")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await query.edit_message_text("✅ Ви маєте постійний Plus!", reply_markup=reply_markup)
        else:
            keyboard = [
                [InlineKeyboardButton(f"💎 Купити Plus за {PLUS_COST:,} HelpCoins", callback_data="buy_plus_direct")],
                [InlineKeyboardButton("💬 Запитати AI", callback_data="ask_ai")],
                [InlineKeyboardButton("👈 Назад", callback_data="subscriptions")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                f"💎 PLUS\n\n"
                f"🤖 Безліміт AI запитань\n\n"
                f"Тривалість: {PLUS_DURATION} днів\n\n"
                f"Вартість: {PLUS_COST:,} HelpCoins",
                reply_markup=reply_markup
            )
    
    elif query.data == "buy_generator_direct":
        user = user_data.get_user(query.from_user.id)
        if user["balance"] >= GENERATOR_COST:
            user["has_generator"] = True
            user["generator_type"] = "3d"
            user["generator_expiry"] = (datetime.now() + timedelta(days=3)).isoformat()
            user["balance"] -= GENERATOR_COST
            user_data.save_data()
            keyboard = [
                [InlineKeyboardButton("💬 Запитати AI", callback_data="ask_ai")],
                [InlineKeyboardButton("👈 Назад", callback_data="back_to_menu")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text("✅ Generator активовано на 3 дні!", reply_markup=reply_markup)
        else:
            keyboard = [
                [InlineKeyboardButton("💬 Запитати AI", callback_data="ask_ai")],
                [InlineKeyboardButton("👈 Назад", callback_data="back_to_menu")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(f"❌ Недостатньо коштів!\n\nПотрібно: {GENERATOR_COST:,} HelpCoins\nЄ: {user['balance']:,} HelpCoins", reply_markup=reply_markup)
    
    elif query.data == "buy_generator":
        user = user_data.get_user(query.from_user.id)
        if user["balance"] >= GENERATOR_COST:
            user["has_generator"] = True
            user["generator_type"] = "3d"
            user["generator_expiry"] = (datetime.now() + timedelta(days=3)).isoformat()
            user["balance"] -= GENERATOR_COST
            user_data.save_data()
            keyboard = [
                [InlineKeyboardButton("💬 Запитати AI", callback_data="ask_ai")],
                [InlineKeyboardButton("👈 Назад", callback_data="back_to_menu")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text("✅ Generator активовано на 3 дні!", reply_markup=reply_markup)
        else:
            keyboard = [
                [InlineKeyboardButton("💬 Запитати AI", callback_data="ask_ai")],
                [InlineKeyboardButton("👈 Назад", callback_data="back_to_menu")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(f"❌ Недостатньо коштів!\n\nПотрібно: {GENERATOR_COST:,} HelpCoins\nЄ: {user['balance']:,} HelpCoins", reply_markup=reply_markup)
    
    elif query.data == "buy_plus_direct":
        user = user_data.get_user(query.from_user.id)
        if user["balance"] >= PLUS_COST:
            user["has_plus"] = True
            user["plus_expiry"] = (datetime.now() + timedelta(days=PLUS_DURATION)).isoformat()
            user["balance"] -= PLUS_COST
            user_data.save_data()
            keyboard = [
                [InlineKeyboardButton("💬 Запитати AI", callback_data="ask_ai")],
                [InlineKeyboardButton("👈 Назад", callback_data="back_to_menu")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(f"✅ Plus активовано на {PLUS_DURATION} днів!", reply_markup=reply_markup)
        else:
            keyboard = [
                [InlineKeyboardButton("💬 Запитати AI", callback_data="ask_ai")],
                [InlineKeyboardButton("👈 Назад", callback_data="back_to_menu")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(f"❌ Недостатньо коштів!\n\nПотрібно: {PLUS_COST:,} HelpCoins\nЄ: {user['balance']:,} HelpCoins", reply_markup=reply_markup)
    
    elif query.data == "buy_plus":
        user = user_data.get_user(query.from_user.id)
        if user["balance"] >= PLUS_COST:
            user["has_plus"] = True
            user["plus_expiry"] = (datetime.now() + timedelta(days=PLUS_DURATION)).isoformat()
            user["balance"] -= PLUS_COST
            user_data.save_data()
            keyboard = [
                [InlineKeyboardButton("💬 Запитати AI", callback_data="ask_ai")],
                [InlineKeyboardButton("👈 Назад", callback_data="back_to_menu")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(f"✅ Plus активовано на {PLUS_DURATION} днів!", reply_markup=reply_markup)
        else:
            keyboard = [
                [InlineKeyboardButton("💬 Запитати AI", callback_data="ask_ai")],
                [InlineKeyboardButton("👈 Назад", callback_data="back_to_menu")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(f"❌ Недостатньо коштів!\n\nПотрібно: {PLUS_COST:,} HelpCoins\nЄ: {user['balance']:,} HelpCoins", reply_markup=reply_markup)
    
    elif query.data == "my_data":
        user = user_data.get_user(query.from_user.id)
        generator_status = "✅ Має" if user["has_generator"] else "❌ Немає"
        plus_status = "✅ Має" if user["has_plus"] else "❌ Немає"
        
        keyboard = [
            [InlineKeyboardButton("💬 Запитати AI", callback_data="ask_ai")],
            [InlineKeyboardButton("👈 Назад", callback_data="back_to_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"📊 ВАШІ ДАНІ\n\n"
            f"👤 Юзернейм: @{user['username']}\n"
            f"💰 Баланс: {user['balance']:,} HelpCoins\n"
            f"⭐ Зірок: {user['stars']}\n"
            f"🎯 Generator: {generator_status}\n"
            f"💎 Plus: {plus_status}\n"
            f"🤖 AI запитань: {user['ai_requests']}",
            reply_markup=reply_markup
        )
    
    elif query.data == "back_to_menu":
        await query.edit_message_text(
            f"🤖 Оберіть опцію:",
            reply_markup=get_main_keyboard()
        )

async def send_invoice(update: Update, context: ContextTypes.DEFAULT_TYPE, stars: int):
    """Відправка інвойсу для покупки зірок"""
    if stars == 1:
        payload = "buy_stars_1"
        title = "1 ⭐ Telegram Star"
        description = "Купити 1 Telegram зірку"
        price = 1  # 1 Telegram Star = 1 USD
    elif stars == 5:
        payload = "buy_stars_5"
        title = "5 ⭐ Telegram Stars"
        description = "Купити 5 Telegram зірок"
        price = 5
    elif stars == 10:
        payload = "buy_stars_10"
        title = "10 ⭐ Telegram Stars"
        description = "Купити 10 Telegram зірок"
        price = 10
    else:
        return
    
    await context.bot.send_invoice(
        chat_id=update.callback_query.from_user.id,
        title=title,
        description=description,
        payload=payload,
        provider_token="",  # Залишити пусто - Telegram Stars не потребує provider_token
        currency="XTR",  # XTR - валюта Telegram Stars
        prices=[LabeledPrice(label=f"Buy {stars} ⭐", amount=stars)],
    )

def main():
    """Запуск бота"""
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Команди
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("setbalance", setbalance))
    app.add_handler(CommandHandler("setmybalance", setmybalance))
    app.add_handler(CommandHandler("givegenerator", givegenerator))
    app.add_handler(CommandHandler("takegenerator", takegenerator))
    app.add_handler(CommandHandler("giveplus", giveplus))
    app.add_handler(CommandHandler("takeplus", takeplus))
    app.add_handler(CommandHandler("helpplus", helpplus))
    
    # Обробка текстових повідомлень (запитання до AI)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Обробка платежів
    app.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_callback))
    
    # Callback кнопки
    app.add_handler(CallbackQueryHandler(button_callback))
    
    logger.info("🤖 Бот запущено!")
    app.run_polling()

if __name__ == '__main__':
    main()
