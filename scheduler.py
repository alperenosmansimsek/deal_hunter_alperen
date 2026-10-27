import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from database import get_connection
from bot_scanner import scan_and_notify

# write your bot token here (from BotFather):
BOT_TOKEN = "8855696578:AAGFnOBmCVVmOgh8Cu7fils9zMcT2fLDBV4"

async def scheduled_deals_job():
    """searches for deals based on active alerts in the database and sends them to users via Telegram."""
    print("\n⏰ [the scheduler] Starting the scheduled deals check...")
    
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, user_id, keyword, brand, max_price 
        FROM alert_monitors 
        WHERE is_active = 1
    """)
    alerts = cursor.fetchall()
    conn.close()

    if not alerts:
        print("⚠️ No active alerts found for scanning.")
        return

    for alert in alerts:
        alert_id = alert["id"]
        user_id = alert["user_id"]
        query = f"{alert['keyword']} {alert['brand'] if alert['brand'].lower() != 'hepsi' else ''}".strip()
        max_price = alert["max_price"]

        print(f"🔄 Scanning: '{query}' (User: {user_id})")
        try:
            await scan_and_notify(BOT_TOKEN, alert_id, user_id, query, max_price)
            # wait a bit between alerts to avoid hitting rate limits
            await asyncio.sleep(3)
        except Exception as e:
            print(f"❌ Error occurred (Alert {alert_id}): {e}")

    print("✅ [the scheduler] Scan completed!\n")

async def main():
    scheduler = AsyncIOScheduler()
    
    # we schedule the job to run every day at 09:00 and 19:00
    scheduler.add_job(scheduled_deals_job, "cron", hour="9,19", minute=0)
    
    # for testing purposes, you can also run the job immediately when the script starts
    scheduler.add_job(scheduled_deals_job, "date")
    
    scheduler.start()
    print("🚀 The scheduler is running 24/7 (Every day at 09:00 and 19:00)...")

    # this keeps the script running indefinitely so that the scheduler can keep working
    while True:
        await asyncio.sleep(1000)

if __name__ == "__main__":
    asyncio.run(main())
