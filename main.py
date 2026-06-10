import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from datetime import datetime, timedelta
import json
import os

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
STARS_TO_HELPCOINS = 1
GENERATOR_COST = 18000
PLUS_COST = 500000
PLUS_DURATION = 5  # днів

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
                "has_plus": False,
                "plus_expiry": None,
                "partner_enabled": False,
                "earnings": 0
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

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data.set_username(user.id, user.username or user.first_name)
    
    keyboard = [
        [InlineKeyboardButton("💰 Баланс", callback_data="balance")],
        [InlineKeyboardButton("⭐ Обміняти зірки", callback_data="exchange_stars")],
        [InlineKeyboardButton("🎁 Підписки", callback_data="subscriptions")],
        [InlineKeyboardButton("📊 Мої дані", callback_data="my_data")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"🤖 Ласкаво просимо до {BOT_NAME}!\n\n"
        f"Компанія: {COMPANY_NAME}\n\n"
        f"Оберіть опцію нижче:",
        reply_markup=reply_markup
    )

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
/givegenerator @username <тип> - Дати доступ (permanent/3d)
/takegenerator @username - Забрати доступ
Приклад: /givegenerator @john permanent

⭐ ПІДПИСКА PLUS:
/giveplus @username <тип> - Дати Plus (permanent/3d)
/takeplus @username - Забрати Plus
Приклад: /giveplus @john 3d

Вартість Plus: {PLUS_COST:,} HelpCoins на {PLUS_DURATION} днів
Вартість Generator: {GENERATOR_COST:,} HelpCoins

📱 ПАРТНЕРСЬКА ПРОГРАМА:
/partner_enable - Увімкнути дохід
/partner_disable - Вимкнути дохід
/earnings - Переглянути заробіток

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
        
        # Пошук користувача за username або ID
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

# Функція пошуку користувача
def find_user_id(identifier):
    """Пошук ID користувача за username або ID"""
    # Якщо це числовий ID
    try:
        return int(identifier.lstrip("@"))
    except ValueError:
        pass
    
    # Пошук за username
    for user_id_str, user_info in user_data.users.items():
        if user_info.get("username", "").lower() == identifier.lstrip("@").lower():
            return int(user_id_str)
    
    return None

# Callback кнопки
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "balance":
        user = user_data.get_user(query.from_user.id)
        await query.edit_message_text(f"💰 Ваш баланс: {user['balance']:,} HelpCoins")
    
    elif query.data == "exchange_stars":
        keyboard = [
            [InlineKeyboardButton("⭐ Обміняти", callback_data="do_exchange")],
            [InlineKeyboardButton("◀️ Назад", callback_data="back")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            f"⭐ ОБМІН ЗІРОК\n\n"
            f"Коефіцієнт: 1 ⭐ = {STARS_TO_HELPCOINS} HelpCoin\n\n"
            f"Натисніть кнопку для обміну зірок на HelpCoins",
            reply_markup=reply_markup
        )
    
    elif query.data == "do_exchange":
        # Тут повинна бути логіка роботи зі Telegram Stars API
        await query.edit_message_text("✅ Обмін зірок включено в підписці Generator")
    
    elif query.data == "subscriptions":
        keyboard = [
            [InlineKeyboardButton("🎯 Generator", callback_data="sub_generator")],
            [InlineKeyboardButton("💎 Plus", callback_data="sub_plus")],
            [InlineKeyboardButton("◀️ Назад", callback_data="back")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("🎁 ПІДПИСКИ", reply_markup=reply_markup)
    
    elif query.data == "sub_generator":
        user = user_data.get_user(query.from_user.id)
        if user["has_generator"]:
            await query.edit_message_text("✅ Ви маєте доступ до Generator!\n\n💰 Вартість: {GENERATOR_COST:,} HelpCoins")
        else:
            keyboard = [[InlineKeyboardButton(f"🎯 Купити за {GENERATOR_COST:,} HelpCoins", callback_data="buy_generator")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                f"🎯 GENERATOR\n\n"
                f"Генерація зображень та відео за текстом\n\n"
                f"Вартість: {GENERATOR_COST:,} HelpCoins",
                reply_markup=reply_markup
            )
    
    elif query.data == "sub_plus":
        user = user_data.get_user(query.from_user.id)
        if user["has_plus"]:
            await query.edit_message_text("✅ Ви маєте Plus!")
        else:
            keyboard = [[InlineKeyboardButton(f"💎 Купити Plus за {PLUS_COST:,} HelpCoins", callback_data="buy_plus")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                f"💎 PLUS\n\n"
                f"Тривалість: {PLUS_DURATION} днів\n\n"
                f"Вартість: {PLUS_COST:,} HelpCoins",
                reply_markup=reply_markup
            )
    
    elif query.data == "buy_generator":
        user = user_data.get_user(query.from_user.id)
        if user["balance"] >= GENERATOR_COST:
            user["has_generator"] = True
            user["generator_type"] = "3d"
            user["generator_expiry"] = (datetime.now() + timedelta(days=3)).isoformat()
            user["balance"] -= GENERATOR_COST
            user_data.save_data()
            await query.edit_message_text("✅ Generator активовано на 3 дні!")
        else:
            await query.edit_message_text(f"❌ Недостатньо коштів!\n\nПотрібно: {GENERATOR_COST:,} HelpCoins\nЄ: {user['balance']:,} HelpCoins")
    
    elif query.data == "buy_plus":
        user = user_data.get_user(query.from_user.id)
        if user["balance"] >= PLUS_COST:
            user["has_plus"] = True
            user["plus_expiry"] = (datetime.now() + timedelta(days=PLUS_DURATION)).isoformat()
            user["balance"] -= PLUS_COST
            user_data.save_data()
            await query.edit_message_text(f"✅ Plus активовано на {PLUS_DURATION} днів!")
        else:
            await query.edit_message_text(f"❌ Недостатньо коштів!\n\nПотрібно: {PLUS_COST:,} HelpCoins\nЄ: {user['balance']:,} HelpCoins")
    
    elif query.data == "my_data":
        user = user_data.get_user(query.from_user.id)
        generator_status = "✅ Має" if user["has_generator"] else "❌ Немає"
        plus_status = "✅ Має" if user["has_plus"] else "❌ Немає"
        
        await query.edit_message_text(
            f"📊 ВАШІ ДАНІ\n\n"
            f"👤 Юзернейм: @{user['username']}\n"
            f"💰 Баланс: {user['balance']:,} HelpCoins\n"
            f"⭐ Зірок: {user['stars']}\n"
            f"🎯 Generator: {generator_status}\n"
            f"💎 Plus: {plus_status}"
        )
    
    elif query.data == "back":
        keyboard = [
            [InlineKeyboardButton("💰 Баланс", callback_data="balance")],
            [InlineKeyboardButton("⭐ Обміняти зірки", callback_data="exchange_stars")],
            [InlineKeyboardButton("🎁 Підписки", callback_data="subscriptions")],
            [InlineKeyboardButton("📊 Мої дані", callback_data="my_data")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("🤖 Оберіть опцію:", reply_markup=reply_markup)

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
    
    # Callback кнопки
    app.add_handler(CallbackQueryHandler(button_callback))
    
    logger.info("🤖 Бот запущено!")
    app.run_polling()

if __name__ == '__main__':
    main()
