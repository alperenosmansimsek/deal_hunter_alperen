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
from async_crawler import search_all_sites_multi

BOT_TOKEN = "8855696578:AAGFnOBmCVVmOgh8Cu7fils9zMcT2fLDBV4"

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

# Adımlar (Cinsiyet eklendi)
KEYWORD, BRAND, GENDER, SIZE, COLOR, PRICE = range(6)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "🤖 *Polonya İndirim Avcısı Botu (Çoklu Filtre Sürümü)*\n\n"
        "Komutlar:\n"
        "➕ `/yeni` - Yeni indirim alarmı oluştur\n"
        "📋 `/alarmlarim` - Aktif alarmlarını gör\n"
        "❌ `/sil <id>` - Bir alarmı kapat\n"
        "🚫 `/iptal` - Girişi durdur"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

async def new_alert(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "1️⃣ *Hangi ürünü arıyorsun?*\n"
        "Örnek: `kurtka`, `buty`, `plecak`",
        parse_mode="Markdown"
    )
    return KEYWORD

async def get_keyword(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["keyword"] = update.message.text.strip()
    await update.message.reply_text(
        "2️⃣ *Markalar neler? (İstediğin kadar yazabilirsin)*\n"
        "Birden fazlaysa virgülle ayır veya `hepsi` yaz.\n"
        "Örnek: `Nike, Adidas, Salomon, The North Face`",
        parse_mode="Markdown"
    )
    return BRAND

async def get_brand(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["brand"] = update.message.text.strip()
    await update.message.reply_text(
        "3️⃣ *Hedef cinsiyet/kategori nedir?*\n"
        "Örnek: `meskie` (erkek), `damskie` (kadın), `dzieciece` (çocuk), `unisex` veya `hepsi`",
        parse_mode="Markdown"
    )
    return GENDER

async def get_gender(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["gender"] = update.message.text.strip()
    await update.message.reply_text(
        "4️⃣ *Beden / Numara tercihlerin neler?*\n"
        "Birden fazlaysa virgülle ayır veya `hepsi` yaz.\n"
        "Örnek: `M, L, XL` veya `43, 44, 45`",
        parse_mode="Markdown"
    )
    return SIZE

async def get_size(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["size"] = update.message.text.strip()
    await update.message.reply_text(
        "5️⃣ *Renk tercihlerin neler?*\n"
        "Birden fazlaysa virgülle ayır veya `hepsi` yaz.\n"
        "Örnek: `czarny, czerwony, granatowy`",
        parse_mode="Markdown"
    )
    return COLOR

async def get_color(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["color"] = update.message.text.strip()
    await update.message.reply_text(
        "6️⃣ *Maksimum bütçen kaç PLN?*\n"
        "Sadece sayı yaz (Örn: `350`)",
        parse_mode="Markdown"
    )
    return PRICE

async def get_price(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    raw_val = update.message.text.strip().replace(",", ".")
    try:
        max_p = float(raw_val)
    except ValueError:
        await update.message.reply_text("Lütfen geçerli bir sayı girin (Örn: 300).")
        return PRICE

    user_id = update.effective_user.id
    kw = context.user_data["keyword"]
    br = context.user_data["brand"]
    gen = context.user_data["gender"]
    sz = context.user_data["size"]
    cl = context.user_data["color"]

    alert_id = create_alert(user_id, kw, br, gen, sz, cl, max_p)

    summary = (
        f"✅ *Çoklu Filtreli Alarm Kuruldu! (ID: #{alert_id})*\n\n"
        f"🔍 *Ürün:* {kw}\n"
        f"🏷️ *Markalar:* {br}\n"
        f"🚻 *Cinsiyet:* {gen}\n"
        f"📏 *Bedenler:* {sz}\n"
        f"🎨 *Renkler:* {cl}\n"
        f"💰 *Maks Fiyat:* {max_p} PLN\n\n"
        "🚀 Tüm siteler taranıyor, eşleşen fırsatlar dökülecek..."
    )
    await update.message.reply_text(summary, parse_mode="Markdown")

    # Arka planda taramayı başlat
    asyncio.create_task(run_scan_and_send(context.bot, alert_id, user_id, kw, br, gen, sz, cl, max_p))
    return ConversationHandler.END

async def run_scan_and_send(bot, alert_id: int, user_id: int, kw: str, br: str, gen: str, sz: str, cl: str, max_p: float):
    # Çoklu filtreleri temiz listelere ayırıyoruz
    brands_list = [b.strip() for b in br.split(",") if b.strip()] if br.lower() != "hepsi" else []
    sizes_list = [s.strip() for s in sz.split(",") if s.strip()] if sz.lower() != "hepsi" else []
    colors_list = [c.strip() for c in cl.split(",") if c.strip()] if cl.lower() != "hepsi" else []
    gender_val = gen if gen.lower() != "hepsi" else ""

    products = await search_all_sites_multi(kw, brands_list, gender_val, sizes_list, colors_list, max_p)

    if not products:
        await bot.send_message(chat_id=user_id, text=f"🔍 Kriterlerine uygun yeni ürün bulunamadı.")
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
        await bot.send_message(chat_id=user_id, text="ℹ️ Kriterlere uygun ürünler zaten daha önce bildirilmişti.")
        return

    await bot.send_message(chat_id=user_id, text=f"🔥 *{len(new_found)} Yeni Fırsat Yakalandı!*", parse_mode="Markdown")
    for item in new_found[:8]:
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
    cursor.execute("SELECT id, keyword, brand, gender, size, max_price FROM alert_monitors WHERE user_id = ? AND is_active = 1", (user_id,))
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        await update.message.reply_text("Kayıtlı aktif alarmın yok. `/yeni` yazarak ekleyebilirsin.", parse_mode="Markdown")
        return

    msg = "📋 *Aktif Alarmların:*\n\n"
    for r in rows:
        msg += f"🔹 [ID: {r['id']}] {r['keyword']} | Marka: {r['brand']} | Cinsiyet: {r['gender']} | Beden: {r['size']} | Maks: {r['max_price']} PLN\n"
    msg += "\nSilmek için: `/sil <id>`"
    await update.message.reply_text(msg, parse_mode="Markdown")

async def delete_alert(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not context.args:
        await update.message.reply_text("Silmek istediğin ID'yi yaz. Örn: `/sil 1`", parse_mode="Markdown")
        return
    try:
        a_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("ID sadece sayı olmalıdır.")
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

    print("🤖 Çoklu filtreli bot dinlemede...")
    app.run_polling()

if __name__ == "__main__":
    main()
