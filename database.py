import sqlite3
import os
from khayyam import JalaliDatetime

def get_db_connection():
    db_path = os.path.join(os.path.dirname(__file__), 'prices_kashan.db')
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def create_tables():
    conn = get_db_connection()
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS vendors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_number INTEGER UNIQUE NOT NULL,
            name TEXT NOT NULL,
            chat_id TEXT,
            active INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            unit TEXT DEFAULT 'کیلوگرم'
        );

        CREATE TABLE IF NOT EXISTS prices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vendor_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            price INTEGER NOT NULL,
            date TEXT NOT NULL,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (vendor_id) REFERENCES vendors (id),
            FOREIGN KEY (product_id) REFERENCES products (id),
            UNIQUE(vendor_id, product_id, date)
        );

        CREATE TABLE IF NOT EXISTS user_states (
            chat_id TEXT PRIMARY KEY,
            state TEXT,
            data TEXT
        );
    ''')
    conn.commit()
    conn.close()

def seed_initial_data():
    conn = get_db_connection()
    cursor = conn.cursor()

    products = [
        ('خیار', 'کیلوگرم'), ('گوجه فرنگی', 'کیلوگرم'), ('سیب زمینی', 'کیلوگرم'),
        ('سیب درختی', 'کیلوگرم'), ('پیاز زرد', 'کیلوگرم'), ('سبزی خوردن', 'دسته'),
        ('بادمجان', 'کیلوگرم'), ('کدو حلوایی', 'عدد'), ('هویج', 'کیلوگرم'), ('لیمو شیرین', 'کیلوگرم')
    ]
    cursor.executemany("INSERT OR IGNORE INTO products (name, unit) VALUES (?, ?)", products)

    vendors = [(1, 'غرفه احمدی'), (2, 'غرفه رضایی'), (5, 'غرفه کریمی')]
    cursor.executemany("INSERT OR IGNORE INTO vendors (room_number, name) VALUES (?, ?)", vendors)

    conn.commit()
    conn.close()
    print("داده‌های اولیه اضافه شد.")

def get_today_jalali():
    return JalaliDatetime.now().strftime('%Y/%m/%d')