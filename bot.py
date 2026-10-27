import os
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
from database import init_db, get_connection

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "BURAYA_BOTFATHER_TOKENINI_YAZ")

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

KEYWORD, BRAND, GENDER, SIZE, COLOR, PRICE = range(6)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "🤖 *İndirim Avcısı Kanal Yöneticisi*\n\n"
        "➕ `/yeni` - Yeni bir ürün odası aç ve takibe başla\n"
        "📋 `/alarmlarim` - Aktif takipleri listele\n"
        "🚫 `/iptal` - İşlemi durdur"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

async def new_alert(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("1️⃣ Aranacak ürün nedir? (Örn: `kurtka`, `buty`)", parse_mode="Markdown")
    return KEYWORD

async def get_keyword(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["keyword"] = update.message.text.strip()
    await update.message.reply_text("2️⃣ Markalar neler? (Virgülle ayırabilirsin, örn: `Nike, Adidas` veya `hepsi`)", parse_mode="Markdown")
    return BRAND

async def get_brand(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["brand"] = update.message.text.strip()
    await update.message.reply_text("3️⃣ Cinsiyet/Kategori nedir? (Örn: `meskie`, `damskie`, `unisex` veya `hepsi`)", parse_mode="Markdown")
    return GENDER

async def get_gender(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["gender"] = update.message.text.strip()
    await update.message.reply_text("4️⃣ Beden / Numara nedir? (Örn: `M, L` veya `43, 44` ya da `hepsi`)", parse_mode="Markdown")
    return SIZE

async def get_size(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["size"] = update.message.text.strip()
    await update.message.reply_text("5️⃣ Renk nedir? (Örn: `czarny, czerwony` veya `hepsi`)", parse_mode="Markdown")
    return COLOR

async def get_color(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["color"] = update.message.text.strip()
    await update.message.reply_text("6️⃣ Maksimum bütçen kaç PLN? (Sadece sayı, örn: `300`)", parse_mode="Markdown")
    return PRICE

async def get_price(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        max_p = float(update.message.text.strip().replace(",", "."))
    except ValueError:
        await update.message.reply_text("Lütfen geçerli bir sayı girin.")
        return PRICE

    kw = context.user_data["keyword"]
    br = context.user_data["brand"]
    gen = context.user_data["gender"]
    sz = context.user_data["size"]
    cl = context.user_data["color"]
    chat_id = update.effective_chat.id

    # Telegram grubunda otomatik yeni bir Konu (Forum Topic) açıyoruz
    topic_name = f"{kw.capitalize()} | {br} | {sz} | Max {max_p} PLN"
    thread_id = None
    
    try:
        # Eğer bot bir forum grubundaysa doğrudan o ürüne özel oda açar
        forum_topic = await context.bot.create_forum_topic(chat_id=chat_id, name=topic_name)
        thread_id = forum_topic.message_thread_id
    except Exception:
        # Normal özel sohbetteyse thread oluşturulamaz, standart devam eder
        thread_id = None

    # Veritabanına kaydet
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO alert_monitors (user_id, keyword, brand, gender, size, color, max_price)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (chat_id, kw, br, gen, sz, cl, max_p))
    alert_id = cursor.lastrowid
    conn.commit()
    conn.close()

    welcome_msg = (
        f"🎯 *Filtreleriniz Alınmıştır ve Takip Başlatıldı! (Alarm #{alert_id})*\n\n"
        f"🔍 *Ürün:* {kw}\n"
        f"🏷️ *Marka:* {br}\n"
        f"🚻 *Kategori:* {gen}\n"
        f"📏 *Beden:* {sz}\n"
        f"🎨 *Renk:* {cl}\n"
        f"💰 *Maksimum Fiyat:* {max_p} PLN\n\n"
        "⚡ Bu kriterlere uygun indirimler günde 2 kez taranarak doğrudan bu odaya iletilecektir."
    )

    if thread_id:
        await context.bot.send_message(chat_id=chat_id, message_thread_id=thread_id, text=welcome_msg, parse_mode="Markdown")
    else:
        await update.message.reply_text(welcome_msg, parse_mode="Markdown")

    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("İşlem iptal edildi.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

def main():
    init_db()
    app = ApplicationBuilder().token(BOT_TOKEN).build()

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

    print("🤖 Bot aktif...")
    app.run_polling()

if __name__ == "__main__":
    main()
