import asyncio
from telegram import Bot
from async_crawler import search_all_sites
from database import get_connection, save_scraped_products

async def scan_and_notify(bot_token: str, alert_id: int, user_id: int, query: str, max_price: float):
    """scans all sites for the given query and sends new deals to the user via Telegram."""
    bot = Bot(token=bot_token)
    
    # 1. scan all sites for the given query
    products = await search_all_sites(query, max_price)
    if not products:
        await bot.send_message(chat_id=user_id, text=f"🔍 '{query}' no suitable products found.")
        return

    # 2. save the found products to the database and filter out already existing ones
    conn = get_connection()
    cursor = conn.cursor()
    new_products = []

    for item in products:
        try:
            cursor.execute("""
            INSERT INTO scraped_products (alert_id, platform, title, price, product_url)
            VALUES (?, ?, ?, ?, ?)
            """, (alert_id, item["platform"], item["title"], item["price"], item["url"]))
            new_products.append(item)
        except Exception:
            # skip if the product already exists in the database (due to unique constraint on product_url)
            continue

    conn.commit()
    conn.close()

    # 3. send a notification to the user if there are new products
    if not new_products:
        await bot.send_message(chat_id=user_id, text=f"ℹ️ '{query}' no new deals found (existing products are already registered).")
        return

    await bot.send_message(
        chat_id=user_id, 
        text=f"🔥 *'{query}' found {len(new_products)} new deals!*", 
        parse_mode="Markdown"
    )

    for item in new_products[:5]:  # send only the first 5 new products to avoid spamming
        message = (
            f"🏷️ *{item['title']}*\n"
            f"🏪 Store: {item['platform']}\n"
            f"💰 Price: *{item['price']} PLN*\n"
            f"🔗 [View Product]({item['url']})"
        )
        await bot.send_message(chat_id=user_id, text=message, parse_mode="Markdown")