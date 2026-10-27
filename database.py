import sqlite3

DB_NAME = "deals_bot.db"

def get_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    
    # Kullanıcı takip alarmları
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS alert_monitors (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        keyword TEXT NOT NULL,
        brand TEXT,
        size TEXT,
        color TEXT,
        max_price REAL NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        is_active BOOLEAN DEFAULT 1
    )
    """)

    # Taranan ve gönderilen ürünler (mükerrerliği önlemek için URL UNIQUE)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS scraped_products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        alert_id INTEGER,
        platform TEXT NOT NULL,
        title TEXT NOT NULL,
        price REAL NOT NULL,
        product_url TEXT UNIQUE NOT NULL,
        scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(alert_id) REFERENCES alert_monitors(id)
    )
    """)
    conn.commit()
    conn.close()

def create_alert(user_id: int, keyword: str, brand: str, size: str, color: str, max_price: float) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO alert_monitors (user_id, keyword, brand, size, color, max_price)
    VALUES (?, ?, ?, ?, ?, ?)
    """, (user_id, keyword, brand, size, color, max_price))
    alert_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return alert_id

if __name__ == "__main__":
    init_db()
    print("Veritabanı tabloları hazırlandı.")
