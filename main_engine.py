import asyncio
from async_crawler import search_all_sites
from database import get_connection, save_scraped_products

async def run_deals_check():
    """
    It fetches all active alerts from the database, searches for products on all configured sites, and saves the found products back to the database.
    """
    conn = get_connection()
    cursor = conn.cursor()

    # Pull all active alerts from the database
    cursor.execute("SELECT id, keyword, brand, max_price FROM alert_monitors WHERE is_active = 1")
    alerts = cursor.fetchall()
    conn.close()

    if not alerts:
        print("⚠️ There are no active search alerts registered!")
        return

    for alert in alerts:
        alert_id = alert["id"]
        search_query = f"{alert['keyword']} {alert['brand'] if alert['brand'] != 'hepsi' else ''}".strip()
        max_p = alert["max_price"]

        print(f"\n🎯 [Alarm #{alert_id}] searching: '{search_query}' (Budget: {max_p} PLN)")
        
        # run the search on all sites and get the found products
        found_products = await search_all_sites(search_query, max_p)
        print(f"📦 Found a total of {len(found_products)} suitable products.")

        # save the found products to the database
        saved_count = save_scraped_products(alert_id, found_products)
        print(f"💾 {saved_count} new products added to the database!")

if __name__ == "__main__":
    print("🚀 The Deal Checking Engine is starting...")
    asyncio.run(run_deals_check())