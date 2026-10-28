import os
import asyncio
import logging
from telegram import Update, ReplyKeyboardRemove
from telegram.request import HTTPXRequest
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)
from database import init_db, get_connection

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8855696578:AAGFnOBmCVVmOgh8Cu7fils9zMcT2fLDBV4")

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

# --- PythonAnywhere Proxy Ayarı ---
# Ücretsiz hesaplarda Telegram bağlantısı bu proxy üzerinden yapılmak zorundadır:
PA_PROXY = "http://proxy.server:3128"
request_proxy = HTTPXRequest(proxy=PA_PROXY)

KEYWORD, BRAND, GENDER, SIZE, COLOR, PRICE = range(6)

# ... (Aradaki diyalog fonksiyonları aynı kalıyor) ...

def main():
    init_db()
    # ApplicationBuilder'a request=request_proxy parametresini ekliyoruz:
    app = ApplicationBuilder().token(BOT_TOKEN).request(request_proxy).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("yeni", new_alert)],
        states={
            KEYWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_keyword)],
            BRAND: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_brand)],
            GENDER: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_gender)],
            SIZE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_size)],
            COLOR: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_color)],
            PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_price)],
        },
        fallbacks=[CommandHandler("iptal", cancel)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv)

    print("🤖 Bot PythonAnywhere proxy üzerinden aktif...")
    app.run_polling()

if __name__ == "__main__":
    main()
