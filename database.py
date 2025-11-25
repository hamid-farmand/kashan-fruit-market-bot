import sqlite3
from khayyam import JalaliDatetime

DATABASE = "kashan_market.db"

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def create_tables():
    conn = get_db_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS vendors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id TEXT UNIQUE,
            name TEXT NOT NULL,
            room_number INTEGER UNIQUE,
            active INTEGER DEFAULT 1
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            unit TEXT DEFAULT 'کیلوگرم'
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS prices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vendor_id INTEGER,
            product_id INTEGER,
            price INTEGER,
            date TEXT,
            UNIQUE(vendor_id, product_id, date),
            FOREIGN KEY(vendor_id) REFERENCES vendors(id),
            FOREIGN KEY(product_id) REFERENCES products(id)
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS user_states (
            chat_id TEXT PRIMARY KEY,
            state TEXT,
            data TEXT
        )
    ''')
    # جدول مشترکین برای ارسال روزانه
    conn.execute('''
        CREATE TABLE IF NOT EXISTS subscribers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id TEXT UNIQUE NOT NULL,
            subscribed_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def get_today_jalali():
    return JalaliDatetime.now().strftime('%Y/%m/%d')

def seed_initial_data():
    conn = get_db_connection()
    # محصولات اولیه
    products = [
        "خیار", "گوجه فرنگی", "سیب زمینی", "پیاز", "سیب", "پرتقال",
        "موز", "انار", "هندوانه", "خربزه", "کاهو", "سبزی خوردن"
    ]
    for p in products:
        conn.execute("INSERT OR IGNORE INTO products (name) VALUES (?)", (p,))
    
    conn.commit()
    conn.close()

if __name__ == "__main__":
    create_tables()
    seed_initial_data()
    print("دیتابیس و داده‌های اولیه با موفقیت ایجاد شد!")