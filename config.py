import os

# ===================== BOT CONFIGURATION =====================

# Telegram Bot Token
BOT_TOKEN = "8333266020:AAHri7MjXz3jjoFSiG5HRoztOGiy2zqTGTA"

# Bot username (without @)
BOT_USERNAME = "nakedonly_bot"

# ===================== REQUIRED CHANNEL SUBSCRIPTION =====================

CHANNEL_ID = "-1003348954642"

CHANNEL_URL = "https://t.me/+D10Qqf6fy6RlY2My"

# ===================== ADMIN CONFIGURATION =====================

ADMIN_IDS = [1876714755, 8576622389, 200558743]

# ===================== SUPPORT CONFIGURATION =====================

SUPPORT_URL = "https://t.me/nakedonly_support"

TERMS_URL = "https://telegra.ph/Polzovatelskoe-soglashenie-08-15-10"

PRIVACY_URL = "https://telegra.ph/Politika-konfidencialnosti-08-15-17"

ADMIN_CHAT_ID = -1005019186934

# ===================== PLATEGA CONFIGURATION =====================

PLATEGA_URL = "https://app.platega.io"
PLATEGA_MERCHANT_ID = "e6157015-e7e9-48be-b65e-1bb5932326dc"
PLATEGA_API_SECRET = "Djtzaj3up7VUeiq7KCHEd9fOjeOoHclZOatuOUm55gM6ne2CCLOAoSFCfHxzvfRTFGUXuDcDXA2tJM4jLxKXo9NvpSRv8QsJ5tCG"

PLATEGA_RETURN_URL = "https://t.me/nakedonly_bot"

PLATEGA_CHECK_INTERVAL = 12

PLATEGA_METHOD_SBP = 2        # СБП QR
PLATEGA_METHOD_INTERNATIONAL = 12  # UA/KZ/AZN/UZS

# ===================== PRICING CONFIGURATION =====================

PRICES = {
    6: 300,
    15: 800,
    30: 1000,
    50: 1500,
    150: 3750
}

DISCOUNTS = {
    6: None,
    15: "🔥 -20%",
    30: "🔥 -30%",
    50: "🔥 -40%",
    150: "🔥 -50%"
}

USDT_RUB_RATE = 80.0

# ===================== REFERRAL CONFIGURATION =====================

REFERRAL_COMMISSION = 50

EXCHANGE_DISCOUNT = 30

CREDIT_PRICE_RUB = 50

# ===================== WITHDRAWAL CONFIGURATION =====================

USDT_COMMISSION_PERCENT = 1.01
USDT_FIXED_FEE = 450.0
USDT_MIN_AMOUNT = 3500.0

# ===================== DATABASE CONFIGURATION =====================

DATABASE_PATH = "bot_database.db"

# ===================== MEDIA PATHS =====================

WELCOME_IMAGE = "media/welcome.jpg"
PHOTO_INSTRUCTION_IMAGE = "media/buy.jpg"

# ===================== UNDRESS API CONFIGURATION =====================

UNDRESS_API_KEY = "7698615ef8283080e448ef36d571b8b9"

UNDRESS_API_URL = "https://api.undresswith.ai/undress_api/undress"
UNDRESS_CHECK_URL = "https://api.undresswith.ai/undress_api/check_item"

UNDRESS_PROMPT = "Nude"
UNDRESS_AI_MODEL = 2
UNDRESS_NUM_IMAGES = 1

# ===================== STREAMPAY CONFIGURATION =====================

API_BASE_URL = "https://api.streampay.org"
STREAMPAY_STORE_ID = int(os.getenv("STREAMPAY_STORE_ID", "0"))
STREAMPAY_PUBLIC_KEY_HEX = os.getenv("STREAMPAY_PUBLIC_KEY", "")
STREAMPAY_PRIVATE_KEY_HEX = os.getenv("STREAMPAY_PRIVATE_KEY", "")
STREAMPAY_WEBHOOK_PORT = int(os.getenv("STREAMPAY_WEBHOOK_PORT", "8081"))

# ===================== SCENARIO PROMPTS =====================

SCENARIO_PROMPTS = {
    "finish": "Кончим",
    "threesome": "Тройничок (не сексуальный контент)",
    "lingerie": "Примерим сексуальное белье? Без интима"
}

