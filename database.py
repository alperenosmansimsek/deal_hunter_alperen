import sqlite3

DB_NAME = "deals_bot.db"

def get_connection():
    """connects to the SQLite database and returns the connection object."""
    conn = sqlite3.connect(DB_NAME)
    #  Set row factory to return rows as dictionaries for easier access
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """creates tables from scratch."""
    conn = get_connection()
    cursor = conn.cursor()

    # Table 1: The alert monitors that users set up to track specific products or keywords (e.g., Nike jacket, max 300 PLN)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS alert_monitors (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        keyword TEXT NOT NULL,
        brand TEXT,
        size TEXT,
        gender TEXT,
        color TEXT,
        max_price REAL NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        is_active BOOLEAN DEFAULT 1
    )
    """)

    # Table 2: The products that the bot has scraped, which we will use in Power BI and filters
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS scraped_products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        alert_id INTEGER,
        platform TEXT NOT NULL,
        title TEXT NOT NULL,
        brand TEXT,
        size TEXT,
        color TEXT,
        price REAL NOT NULL,
        original_price REAL,
        discount_rate REAL,
        product_url TEXT UNIQUE NOT NULL,
        scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(alert_id) REFERENCES alert_monitors(id)
    )
    """)

    conn.commit()
    conn.close()
    print("✅ Tables created successfully!")

def seed_sample_data():
    """Inserts sample data for Power BI and SQL practice."""
    conn = get_connection()
    cursor = conn.cursor()

    # Insert a sample user alert (e.g., Nike jacket, max 300 PLN)
    cursor.execute("""
    INSERT INTO alert_monitors (user_id, keyword, brand, size, gender, color, max_price)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (12345678, "kurtka", "Nike", "L", "men", "czarny", 300.0))
    
    alert_id = cursor.lastrowid

    # Sample scraped discounted products
    sample_products = [
        (alert_id, "ceneo.pl", "Nike Sportswear Down Jacket", "Nike", "L", "czarny", 249.99, 450.0, 44.4, "https://ceneo.pl/sample1"),
        (alert_id, "allegro.pl", "Kurtka Zimowa Nike Therma-FIT", "Nike", "L", "czarny", 289.00, 399.0, 27.5, "https://allegro.pl/sample2"),
        (alert_id, "vinted.pl", "Kurtka puchowa Nike Windrunner nowa z metką", "Nike", "L", "czarny", 180.00, 350.0, 48.5, "https://vinted.pl/sample3"),
    ]

    cursor.executemany("""
    INSERT OR IGNORE INTO scraped_products
    (alert_id, platform, title, brand, size, color, price, original_price, discount_rate, product_url)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, sample_products)

    conn.commit()
    conn.close()
    print("✅ Sample test products added to the database!")

if __name__ == "__main__":
    init_db()
    seed_sample_data()
    
def save_scraped_products(alert_id: int, products: list):
    """
    Adds scraped products to the database. If the product link (product_url) already exists, it does not add duplicates.
    If the product link (product_url) already exists, it does not add duplicates.
    """
    conn = get_connection()
    cursor = conn.cursor()
    new_items_count = 0

    for item in products:
        try:
            # product_url is unique, so if it already exists, the INSERT will fail and we can skip it
            cursor.execute("""
            INSERT INTO scraped_products 
            (alert_id, platform, title, price, product_url)
            VALUES (?, ?, ?, ?, ?)
            """, (
                alert_id,
                item["platform"],
                item["title"],
                item["price"],
                item["url"]
            ))
            new_items_count += 1
        except sqlite3.IntegrityError:
            # The product_url already exists in the database, so we skip this item
            continue

    conn.commit()
    conn.close()
    return new_items_count

def create_alert(user_id: int, keyword: str, brand: str, size: str, color: str, max_price: float) -> int:
    """
    Creates a new alert monitor in the database and returns the new alert's ID.
    """
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