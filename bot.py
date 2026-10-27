import asyncio
import logging
from telegram import Update, ReplyKeyboardRemove
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)
from database import init_db, create_alert
from bot_scanner import scan_and_notify

# please replace this with your actual bot token from BotFather:
BOT_TOKEN = "8855696578:AAGFnOBmCVVmOgh8Cu7fils9zMcT2fLDBV4"

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

KEYWORD, BRAND, SIZE, COLOR, PRICE = range(5)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "👋 *Welcome to the Poland Deal Hunter Bot!*\n\n"
        "1. Step: What product are you looking for? (e.g., jacket, boots, backpack)",
        parse_mode="Markdown"
    )
    return KEYWORD

async def get_keyword(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["keyword"] = update.message.text.strip()
    await update.message.reply_text("2. Step: What is your preferred brand? (e.g., Nike, The North Face or 'all')")
    return BRAND

async def get_brand(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["brand"] = update.message.text.strip()
    await update.message.reply_text("3. Step: What is your preferred size? (e.g., M, L, 43 or 'all')")
    return SIZE

async def get_size(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["size"] = update.message.text.strip()
    await update.message.reply_text("4. Step: What is your preferred color? (e.g., czarny or 'all')")
    return COLOR

async def get_color(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["color"] = update.message.text.strip()
    await update.message.reply_text("5. Step: What is your maximum budget in PLN? (Just the number, e.g., 250)")
    return PRICE

async def get_price(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        max_price = float(update.message.text.strip().replace(",", "."))
        context.user_data["max_price"] = max_price
    except ValueError:
        await update.message.reply_text("Please enter only a number (e.g., 250).")
        return PRICE

    user_id = update.effective_user.id
    keyword = context.user_data["keyword"]
    brand = context.user_data["brand"]
    size = context.user_data["size"]
    color = context.user_data["color"]

    # 1. save the alert to the database
    alert_id = create_alert(user_id, keyword, brand, size, color, max_price)

    await update.message.reply_text(
        "✅ *Alarm Saved to Database!*\n"
        "🔍 Scanning sites, suitable products will be sent here shortly...",
        parse_mode="Markdown"
    )

    # 2. Run the crawler in the background and send results to Telegram
    search_query = f"{keyword} {brand if brand.lower() != 'hepsi' else ''}".strip()
    asyncio.create_task(scan_and_notify(BOT_TOKEN, alert_id, user_id, search_query, max_price))

    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Operation cancelled.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

def main():
    init_db()
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            KEYWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_keyword)],
            BRAND: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_brand)],
            SIZE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_size)],
            COLOR: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_color)],
            PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_price)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(conv_handler)
    print("🤖 Bot is running, you can type /start on Telegram...")
    app.run_polling()

if __name__ == "__main__":
    main()