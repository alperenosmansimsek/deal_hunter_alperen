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
from database import init_db, get_connection, create_alert
from async_crawler import search_all_sites

# BOTFATHER TOKENINI DOGRUDAN BURAYA YAZ:
BOT_TOKEN = "8855696578:AAGFnOBmCVVmOgh8Cu7fils9zMcT2fLDBV4"

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

KEYWORD, BRAND, SIZE, COLOR, PRICE = range(5)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "🤖 *Polonya Fırsat Takip Botu Aktif*\n\n"
        "Komutlar:\n"
        "➕ `/yeni` - Yeni indirim alarmı kur\n"
        "📋 `/alarmlarim` - Mevcut alarmlarını gör\n"
        "❌ `/sil <id>` - Alarmı iptal et\n"
        "🔍 `/tara` - Mevcut alarmları şimdi manuel tara"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

async def new_alert(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("1️⃣ Aranacak ürün/kategori nedir? (Örn: kurtka, buty, plecak)")
    return KEYWORD

async def get_keyword(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["keyword"] = update.message.text.strip()
    await update.message.reply_text("2️⃣ Marka nedir? (Örn: Nike, The North Face veya 'hepsi')")
    return BRAND

async def get_brand(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["brand"] = update.message.text.strip()
    await update.message.reply_text("3️⃣ Beden/Numara tercihin? (Örn: M, L, 43 veya 'hepsi')")
    return SIZE

async def get_size(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["size"] = update.message.text.strip()
    await update.message.reply_text("4️⃣ Renk tercihin? (Örn: czarny veya 'hepsi')")
    return COLOR

async def get_color(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["color"] = update.message.text.strip()
    await update.message.reply_text("5️⃣ Maksimum bütçen kaç PLN? (Örn: 300)")
    return PRICE

async def get_price(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    raw_val = update.message.text.strip().replace(",", ".")
    try:
        max_p = float(raw_val)
    except ValueError:
        await update.message.reply_text("Lütfen sadece rakam girin (Örn: 250).")
        return PRICE

    user_id = update.effective_user.id
    kw = context.user_data["keyword"]
    br = context.user_data["brand"]
    sz = context.user_data["size"]
    cl = context.user_data["color"]

    alert_id = create_alert(user_id, kw, br, sz, cl, max_p)

    await update.message.reply_text(
        f"✅ *Alarm Kaydedildi (ID: #{alert_id})*\n"
        f"Ürün: {kw} | Marka: {br} | Bütçe: {max_p} PLN\n"
        "İlk arama başlatılıyor, bulunan indirimler birazdan listelenecek...",
        parse_mode="Markdown"
    )

    # Anlık ilk taramayı tetikle
    query = f"{kw} {br if br.lower() != 'hepsi' else ''}".strip()
    asyncio.create_task(run_scan_and_send(context.bot, alert_id, user_id, query, max_p))

    return ConversationHandler.END

async def run_scan_and_send(bot, alert_id: int, user_id: int, query: str, max_p: float):
    products = await search_all_sites(query, max_p)
    if not products:
        await bot.send_message(chat_id=user_id, text=f"🔍 '{query}' için henüz uygun fiyatlı ürün bulunamadı.")
        return

    conn = get_connection()
    cursor = conn.cursor()
    new_found = []

    for p in products:
        try:
            cursor.execute("""
            INSERT INTO scraped_products (alert_id, platform, title, price, product_url)
            VALUES (?, ?, ?, ?, ?)
            """, (alert_id, p["platform"], p["title"], p["price"], p["url"]))
            new_found.append(p)
        except Exception:
            continue
    conn.commit()
    conn.close()

    if not new_found:
        await bot.send_message(chat_id=user_id, text=f"ℹ️ '{query}' için yeni bir indirim yok.")
        return

    await bot.send_message(chat_id=user_id, text=f"🔥 *'{query}' İçin {len(new_found)} Yeni Fırsat!*", parse_mode="Markdown")
    for item in new_found[:5]:
        text = (
            f"🏷️ *{item['title']}*\n"
            f"🏪 Mağaza: {item['platform']}\n"
            f"💰 Fiyat: *{item['price']} PLN*\n"
            f"🔗 [Ürünü Gör]({item['url']})"
        )
        await bot.send_message(chat_id=user_id, text=text, parse_mode="Markdown")

async def list_alerts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, keyword, brand, max_price FROM alert_monitors WHERE user_id = ? AND is_active = 1", (user_id,))
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        await update.message.reply_text("Kayıtlı aktif alarmın yok. `/yeni` yazarak ekleyebilirsin.", parse_mode="Markdown")
        return

    msg = "📋 *Aktif Alarmların:*\n\n"
    for r in rows:
        msg += f"🔹 [ID: {r['id']}] {r['keyword']} ({r['brand']}) - Maks: {r['max_price']} PLN\n"
    msg += "\nSilmek için: `/sil <id>`"
    await update.message.reply_text(msg, parse_mode="Markdown")

async def delete_alert(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not context.args:
        await update.message.reply_text("Silmek istediğin ID'yi belirt: Örn: `/sil 1`", parse_mode="Markdown")
        return
    try:
        a_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("ID bir sayı olmalıdır.")
        return

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE alert_monitors SET is_active = 0 WHERE id = ? AND user_id = ?", (a_id, user_id))
    conn.commit()
    conn.close()
    await update.message.reply_text(f"#{a_id} numaralı alarm kapatıldı.")

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

    print("🤖 Bot çalışıyor. Telegram'dan mesaj atabilirsin.")
    app.run_polling()

if __name__ == "__main__":
    main()
