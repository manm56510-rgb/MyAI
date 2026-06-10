# 🤖 Ukrainian Helper Bot

Telegram бот для управління підписками, балансом та генерацією контенту.

## 📋 Функціональність

### 👤 Користувачі
- 💰 Баланс HelpCoins
- ⭐ Обмін зірок на HelpCoins
- 🎁 Підписки (Generator, Plus)
- 📊 Переглядання особистих даних

### 🔧 Команди Власника
- `/help` - Всі команди для власника
- `/setbalance @username <кількість>` - Встановити баланс
- `/setmybalance <кількість>` - Встановити собі баланс
- `/givegenerator @username <permanent/3d>` - Дати Generator
- `/takegenerator @username` - Забрати Generator
- `/giveplus @username <permanent/3d>` - Дати Plus
- `/takeplus @username` - Забрати Plus

### 💎 Підписки
- **Generator** - Генерація зображень та відео за текстом (18,000 HelpCoins)
- **Plus** - Преміум можливості на 5 днів (500,000 HelpCoins)

## 📦 Встановлення

1. Клонуйте репозиторій:
```bash
git clone https://github.com/manm56510-rgb/MyAI.git
cd MyAI
```

2. Встановіть залежності:
```bash
pip install -r requirements.txt
```

3. Запустіть бота:
```bash
python main.py
```

## 🔑 Конфігурація

Відредагуйте `main.py`:
- `OWNER_ID` - Ваш Telegram ID (8080673594)
- `BOT_TOKEN` - Токен вашого бота
- `COMPANY_NAME` - Назва компанії (UkraineAI)
- `BOT_NAME` - Назва бота (Ukrainian Helper)

## 📝 Структура

- `main.py` - Основний файл бота
- `requirements.txt` - Залежності
- `users_data.json` - Дані користувачів (створюється автоматично)

## ⚠️ Важливо

- **ЗМІНІТЬ ТОКЕН** перед розповсюдженням коду!
- Зберігайте токен безпечно
- ID Власника - це ваш Telegram ID

## 📞 Підтримка

Компанія: **UkraineAI**
Бот: **Ukrainian Helper**

---
Made with ❤️ by Copilot
