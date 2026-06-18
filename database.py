import sqlite3
from datetime import datetime

DB_NAME = "nomer_bot.db"

def get_conn():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn()
    c = conn.cursor()
    
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            user_id INTEGER UNIQUE,
            full_name TEXT,
            username TEXT,
            phone TEXT DEFAULT NULL,
            balance INTEGER DEFAULT 0,
            referral_count INTEGER DEFAULT 0,
            referral_earnings INTEGER DEFAULT 0,
            referred_by INTEGER DEFAULT NULL,
            is_blocked INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    c.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            order_id TEXT,
            phone TEXT,
            country_code TEXT,
            country_name TEXT,
            price INTEGER,
            status TEXT DEFAULT 'waiting',
            code TEXT DEFAULT NULL,
            password TEXT DEFAULT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    c.execute("""
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount INTEGER,
            status TEXT DEFAULT 'pending',
            admin_message_id INTEGER DEFAULT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    c.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    
    # Default settings
    defaults = {
        "card_number": "8600 0000 0000 0000",
        "card_owner": "Bot Egasi",
        "referral_percent": "10",
        "price_markup": "2000",
        "support_username": "@admin",
        "proof_channel_id": "",
        "api_key": "60aae6d18ef867e1c58e1e5f"
    }
    for k, v in defaults.items():
        c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v))
    
    conn.commit()
    conn.close()

# USER
def get_user(user_id):
    conn = get_conn()
    user = conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
    conn.close()
    return user

def save_phone(user_id, phone):
    conn = get_conn()
    conn.execute("UPDATE users SET phone=? WHERE user_id=?", (phone, user_id))
    conn.commit()
    conn.close()

def phone_exists(phone):
    conn = get_conn()
    row = conn.execute("SELECT user_id FROM users WHERE phone=?", (phone,)).fetchone()
    conn.close()
    return row is not None

def add_user(user_id, full_name, username, referred_by=None):
    conn = get_conn()
    conn.execute(
        "INSERT OR IGNORE INTO users (user_id, full_name, username, referred_by) VALUES (?,?,?,?)",
        (user_id, full_name, username, referred_by)
    )
    conn.commit()
    conn.close()

def update_balance(user_id, amount):
    conn = get_conn()
    conn.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (amount, user_id))
    conn.commit()
    conn.close()

def set_balance(user_id, amount):
    conn = get_conn()
    conn.execute("UPDATE users SET balance=? WHERE user_id=?", (amount, user_id))
    conn.commit()
    conn.close()

def get_all_users():
    conn = get_conn()
    users = conn.execute("SELECT * FROM users WHERE is_blocked=0").fetchall()
    conn.close()
    return users

def get_user_count():
    conn = get_conn()
    count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    conn.close()
    return count

def block_user(user_id):
    conn = get_conn()
    conn.execute("UPDATE users SET is_blocked=1 WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()

def unblock_user(user_id):
    conn = get_conn()
    conn.execute("UPDATE users SET is_blocked=0 WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()

def search_user(query):
    conn = get_conn()
    try:
        uid = int(query)
        user = conn.execute("SELECT * FROM users WHERE user_id=?", (uid,)).fetchone()
    except:
        user = conn.execute("SELECT * FROM users WHERE username LIKE ?", (f"%{query}%",)).fetchone()
    conn.close()
    return user

# ORDERS
def add_order(user_id, order_id, phone, country_code, country_name, price):
    conn = get_conn()
    conn.execute(
        "INSERT INTO orders (user_id, order_id, phone, country_code, country_name, price) VALUES (?,?,?,?,?,?)",
        (user_id, order_id, phone, country_code, country_name, price)
    )
    conn.commit()
    conn.close()

def get_order(order_id):
    conn = get_conn()
    order = conn.execute("SELECT * FROM orders WHERE order_id=?", (order_id,)).fetchone()
    conn.close()
    return order

def update_order_status(order_id, status, code=None, password=None):
    conn = get_conn()
    conn.execute(
        "UPDATE orders SET status=?, code=?, password=? WHERE order_id=?",
        (status, code, password, order_id)
    )
    conn.commit()
    conn.close()

def get_user_orders(user_id):
    conn = get_conn()
    orders = conn.execute(
        "SELECT * FROM orders WHERE user_id=? ORDER BY created_at DESC",
        (user_id,)
    ).fetchall()
    conn.close()
    return orders

def get_total_orders():
    conn = get_conn()
    count = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
    conn.close()
    return count

def get_total_revenue():
    conn = get_conn()
    total = conn.execute("SELECT SUM(price) FROM orders WHERE status='finished'").fetchone()[0]
    conn.close()
    return total or 0

def get_today_orders():
    conn = get_conn()
    today = datetime.now().strftime("%Y-%m-%d")
    count = conn.execute(
        "SELECT COUNT(*) FROM orders WHERE created_at LIKE ?", (f"{today}%",)
    ).fetchone()[0]
    conn.close()
    return count

# PAYMENTS
def add_payment(user_id, amount):
    conn = get_conn()
    c = conn.cursor()
    c.execute("INSERT INTO payments (user_id, amount) VALUES (?,?)", (user_id, amount))
    payment_id = c.lastrowid
    conn.commit()
    conn.close()
    return payment_id

def get_payment(payment_id):
    conn = get_conn()
    payment = conn.execute("SELECT * FROM payments WHERE id=?", (payment_id,)).fetchone()
    conn.close()
    return payment

def update_payment(payment_id, status, admin_message_id=None):
    conn = get_conn()
    conn.execute(
        "UPDATE payments SET status=?, admin_message_id=? WHERE id=?",
        (status, admin_message_id, payment_id)
    )
    conn.commit()
    conn.close()

# SETTINGS
def get_setting(key):
    conn = get_conn()
    row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    conn.close()
    return row[0] if row else None

def set_setting(key, value):
    conn = get_conn()
    conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?,?)", (key, value))
    conn.commit()
    conn.close()

# REFERRAL
def add_referral_earning(referrer_id, amount):
    conn = get_conn()
    conn.execute(
        "UPDATE users SET referral_count=referral_count+1, referral_earnings=referral_earnings+?, balance=balance+? WHERE user_id=?",
        (amount, amount, referrer_id)
    )
    conn.commit()
    conn.close()

# RATING
def get_top_buyers(limit=5):
    conn = get_conn()
    rows = conn.execute("""
        SELECT u.user_id, u.full_name, u.username, COUNT(o.id) as order_count
        FROM users u
        JOIN orders o ON u.user_id = o.user_id
        WHERE o.status = 'finished'
        AND o.created_at >= datetime('now', '-30 days')
        GROUP BY u.user_id
        ORDER BY order_count DESC
        LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return rows

def reset_rating():
    conn = get_conn()
    conn.execute("UPDATE settings SET value=? WHERE key='rating_reset_date'", 
                 (datetime.datetime.now().strftime('%Y-%m-%d'),))
    conn.commit()
    conn.close()

def get_rating_days_left():
    conn = get_conn()
    row = conn.execute("SELECT value FROM settings WHERE key='rating_reset_date'").fetchone()
    conn.close()
    if not row:
        return 30
    reset_date = datetime.datetime.strptime(row[0], '%Y-%m-%d')
    next_reset = reset_date + datetime.timedelta(days=30)
    days_left = (next_reset - datetime.datetime.now()).days
    return max(0, days_left)
