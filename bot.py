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

BOT_TOKEN = "8855696578:AAGFnOBmCVVmOgh8Cu7fils9zMcT2fLDBV4"

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

# PythonAnywhere Zorunlu Proxy Ayarı
PA_PROXY = "http://proxy.server:3128"
request_proxy = HTTPXRequest(proxy=PA_PROXY)

KEYWORD, BRAND, GENDER, SIZE, COLOR, PRICE = range(6)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "🤖 *İndirim Avcısı Botu Hazır!*\n\n"
        "➕ `/yeni` - Yeni bir ürün odası aç ve takibe başla\n"
        "📋 `/alarmlarim` - Aktif aramalarını listele\n"
        "❌ `/sil <id>` - Bir alarmı kapat\n"
        "🚫 `/iptal` - Girişi durdur"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

async def new_alert(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("1️⃣ *Hangi ürünü arıyorsun?* (Örn: `kurtka`, `buty`, `plecak`)", parse_mode="Markdown")
    return KEYWORD

async def get_keyword(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["keyword"] = update.message.text.strip()
    await update.message.reply_text("2️⃣ *Markalar neler?* (Virgülle ayırabilirsin, örn: `Nike, Adidas, Salomon` veya `hepsi`)", parse_mode="Markdown")
    return BRAND

async def get_brand(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["brand"] = update.message.text.strip()
    await update.message.reply_text("3️⃣ *Cinsiyet/Kategori nedir?* (Örn: `meskie`, `damskie`, `unisex` veya `hepsi`)", parse_mode="Markdown")
    return GENDER

async def get_gender(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["gender"] = update.message.text.strip()
    await update.message.reply_text("4️⃣ *Beden / Numara nedir?* (Örn: `M, L` veya `43, 44` ya da `hepsi`)", parse_mode="Markdown")
    return SIZE

async def get_size(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["size"] = update.message.text.strip()
    await update.message.reply_text("5️⃣ *Renk nedir?* (Örn: `czarny, czerwony` veya `hepsi`)", parse_mode="Markdown")
    return COLOR

async def get_color(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["color"] = update.message.text.strip()
    await update.message.reply_text("6️⃣ *Maksimum bütçen kaç PLN?* (Sadece sayı, örn: `300`)", parse_mode="Markdown")
    return PRICE

async def get_price(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        max_p = float(update.message.text.strip().replace(",", "."))
    except ValueError:
        await update.message.reply_text("Lütfen sadece sayı yazın (Örn: 250).")
        return PRICE

    kw = context.user_data.get("keyword", "")
    br = context.user_data.get("brand", "")
    gen = context.user_data.get("gender", "")
    sz = context.user_data.get("size", "")
    cl = context.user_data.get("color", "")
    chat_id = update.effective_chat.id

    topic_name = f"{kw.capitalize()} | {br[:15]} | {max_p} PLN"
    thread_id = None
    try:
        forum_topic = await context.bot.create_forum_topic(chat_id=chat_id, name=topic_name)
        thread_id = forum_topic.message_thread_id
    except Exception as e:
        logging.warning(f"Topic acilamadi: {e}")

    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
        INSERT INTO alert_monitors (user_id, keyword, brand, gender, size, color, max_price)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (chat_id, kw, br, gen, sz, cl, max_p))
        alert_id = cursor.lastrowid
        conn.commit()
        conn.close()
    except Exception as e:
        alert_id = 1
        logging.error(f"DB Kayit Hatasi: {e}")

    welcome_msg = (
        f"🎯 *Filtreleriniz Alındı! (Takip ID: #{alert_id})*\n\n"
        f"🔍 *Ürün:* {kw}\n"
        f"🏷️ *Marka:* {br}\n"
        f"🚻 *Kategori:* {gen}\n"
        f"📏 *Beden:* {sz}\n"
        f"🎨 *Renk:* {cl}\n"
        f"💰 *Maks Fiyat:* {max_p} PLN\n\n"
        "⚡ Günde 2 kez otomatik tarama yapılarak indirimler doğrudan buraya iletilecektir.\n"
        "Yeni bir arama odası açmak için dilediğiniz zaman tekrar `/yeni` yazabilirsiniz."
    )

    if thread_id:
        await context.bot.send_message(chat_id=chat_id, message_thread_id=thread_id, text=welcome_msg, parse_mode="Markdown")
    else:
        await update.message.reply_text(welcome_msg, parse_mode="Markdown")

    return ConversationHandler.END

async def list_alerts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, keyword, brand, max_price FROM alert_monitors WHERE user_id = ? AND is_active = 1", (chat_id,))
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        await update.message.reply_text("📋 Kayıtlı aktif alarmın yok. `/yeni` ile oluşturabilirsin.", parse_mode="Markdown")
        return

    msg = "📋 *Aktif Alarmların:*\n\n"
    for r in rows:
        msg += f"🔹 [ID: #{r['id']}] {r['keyword']} ({r['brand']}) - Maks: {r['max_price']} PLN\n"
    msg += "\nBir alarmı kaldırmak için: `/sil <id>`"
    await update.message.reply_text(msg, parse_mode="Markdown")

async def delete_alert(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if not context.args:
        await update.message.reply_text("Silmek istediğin ID'yi yaz. Örn: `/sil 1`", parse_mode="Markdown")
        return
    try:
        a_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Geçersiz ID.")
        return

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE alert_monitors SET is_active = 0 WHERE id = ? AND user_id = ?", (a_id, chat_id))
    conn.commit()
    conn.close()
    await update.message.reply_text(f"#{a_id} numaralı alarm kapatıldı.")

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("İşlem iptal edildi.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

def main():
    init_db()
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
    app.add_handler(CommandHandler("alarmlarim", list_alerts))
    app.add_handler(CommandHandler("sil", delete_alert))
    app.add_handler(conv)

    print("🤖 Bot sorunsuz çalışıyor...")
    app.run_polling()

if __name__ == "__main__":
    main()
