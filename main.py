import logging
import sqlite3
import json
import os
import time
import asyncio
from functools import wraps
from datetime import datetime, timedelta
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, ContextTypes, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ConversationHandler
from translations import T, LANG_NAMES

load_dotenv()

DASHBOARD_URL = os.getenv("DASHBOARD_URL", "https://sokchhorn-bot.fly.dev/").rstrip("/") + "/"

LANG_FILE = "lang_prefs.json"
lang_cache = {}

def load_langs():
    global lang_cache
    try:
        with open(LANG_FILE, 'r') as f:
            lang_cache = json.load(f)
    except:
        lang_cache = {}

def save_langs():
    with open(LANG_FILE, 'w') as f:
        json.dump(lang_cache, f)

def get_lang(chat_id):
    return lang_cache.get(str(chat_id), 'en')

def set_lang(chat_id, lang):
    lang_cache[str(chat_id)] = lang
    save_langs()

async def guard_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    chat_id = update.effective_chat.id
    await query.answer(text=_('msg_type_instead', chat_id), show_alert=True)
    return None

def escape_md(text):
    if text is None: return ''
    for ch in ('_', '*', '`', '['):
        text = text.replace(ch, '\\' + ch)
    return text

def is_owner(context):
    uid = context.user_data.get('_uid')
    return uid in ADMIN_IDS

def is_staff(context):
    return False

def check_access(update, context):
    uid = update.effective_user.id
    if uid in ADMIN_IDS:
        context.user_data['unlocked'] = True
        return True
    return bool(context.user_data.get('unlocked'))

def require_access(func):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not check_access(update, context):
            context.user_data['awaiting_unlock'] = True
            await update.message.reply_text("🔒 Enter unlock PIN to access the bot.\nUse /start, enter the PIN, then try again.")
            return
        return await func(update, context)
    return wrapper

def _(key, chat_id=None, lang=None):
    if lang is None and chat_id is not None:
        lang = get_lang(chat_id)
    if lang is None:
        lang = 'en'
    entry = T.get(key, {})
    if lang in entry:
        return entry[lang]
    return entry.get('en', key)

def _f(key, chat_id=None, lang=None, **kwargs):
    s = _(key, chat_id, lang)
    if kwargs:
        return s.format(**kwargs)
    return s

def clear_user_data(context):
    unlocked = context.user_data.pop('unlocked', None)
    context.user_data.clear()
    if unlocked:
        context.user_data['unlocked'] = True

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

DB_PATH = "inventory.db"
ADMIN_IDS = {7185846273}

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS items (
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, category TEXT NOT NULL,
        quantity INTEGER NOT NULL, price REAL)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS sales (
        id INTEGER PRIMARY KEY AUTOINCREMENT, item_id INTEGER NOT NULL, category TEXT NOT NULL,
        quantity INTEGER NOT NULL, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (item_id) REFERENCES items (id))''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS customers (
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, phone TEXT, credit REAL DEFAULT 0)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT, customer_id INTEGER NOT NULL, amount REAL NOT NULL,
        description TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (customer_id) REFERENCES customers (id))''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS brands (
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL, emoji TEXT NOT NULL DEFAULT '📦', color TEXT NOT NULL DEFAULT '⚪')''')
    try:
        cursor.execute("ALTER TABLE brands ADD COLUMN color TEXT NOT NULL DEFAULT '⚪'")
    except:
        pass
    cursor.execute('''CREATE TABLE IF NOT EXISTS product_groups (
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL, emoji TEXT NOT NULL DEFAULT '📦', color TEXT NOT NULL DEFAULT '⚪')''')
    try:
        cursor.execute("ALTER TABLE items ADD COLUMN group_name TEXT")
    except:
        pass
    try:
        cursor.execute("ALTER TABLE items ADD COLUMN ram TEXT")
    except:
        pass
    try:
        cursor.execute("ALTER TABLE items ADD COLUMN rom TEXT")
    except:
        pass
    try:
        cursor.execute("ALTER TABLE items ADD COLUMN cost_price REAL")
    except:
        pass
    try:
        cursor.execute("ALTER TABLE items ADD COLUMN product_code TEXT")
    except:
        pass
    try:
        cursor.execute("ALTER TABLE items ADD COLUMN barcode TEXT")
    except:
        pass
    cursor.execute('''CREATE TABLE IF NOT EXISTS receipts (
        id INTEGER PRIMARY KEY AUTOINCREMENT, receipt_no TEXT UNIQUE NOT NULL,
        customer_id INTEGER, customer_name TEXT, total_amount REAL,
        discount REAL DEFAULT 0, payment_method TEXT DEFAULT 'cash',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    try:
        cursor.execute("ALTER TABLE sales ADD COLUMN receipt_id INTEGER")
    except:
        pass
    cursor.execute('''CREATE TABLE IF NOT EXISTS stock_movements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        item_id INTEGER, item_name TEXT, item_category TEXT,
        change_type TEXT NOT NULL, qty_before INTEGER DEFAULT 0,
        qty_change INTEGER DEFAULT 0, qty_after INTEGER DEFAULT 0,
        price REAL, reference TEXT, created_by TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    try:
        cursor.execute("ALTER TABLE customers ADD COLUMN location TEXT")
    except:
        pass
    try:
        cursor.execute("ALTER TABLE customers ADD COLUMN phone2 TEXT")
    except:
        pass
    try:
        cursor.execute("ALTER TABLE customers ADD COLUMN phone3 TEXT")
    except:
        pass
    try:
        cursor.execute("ALTER TABLE sales ADD COLUMN imei TEXT")
    except:
        pass
    try:
        cursor.execute("ALTER TABLE sales ADD COLUMN sellout_price TEXT")
    except:
        pass
    try:
        cursor.execute("ALTER TABLE sales ADD COLUMN delivery_fee TEXT")
    except:
        pass
    try:
        cursor.execute("ALTER TABLE sales ADD COLUMN special_note TEXT")
    except:
        pass
    try:
        cursor.execute("ALTER TABLE sales ADD COLUMN returned INTEGER DEFAULT 0")
    except:
        pass
    try:
        cursor.execute("ALTER TABLE sales ADD COLUMN returned_at DATETIME")
    except:
        pass
    try:
        cursor.execute("ALTER TABLE sales ADD COLUMN return_reason TEXT")
    except:
        pass
    try:
        cursor.execute("ALTER TABLE sales ADD COLUMN created_by TEXT")
    except:
        pass
    cursor.execute('''CREATE TABLE IF NOT EXISTS payment_schedules (
        id INTEGER PRIMARY KEY AUTOINCREMENT, customer_id INTEGER NOT NULL,
        transaction_id INTEGER, due_date TEXT NOT NULL, amount REAL NOT NULL,
        status TEXT DEFAULT 'pending', notes TEXT,
        FOREIGN KEY (customer_id) REFERENCES customers (id),
        FOREIGN KEY (transaction_id) REFERENCES transactions (id))''')
    try:
        cursor.execute("ALTER TABLE payment_schedules ADD COLUMN created_by TEXT")
    except:
        pass
    cursor.execute('''CREATE TABLE IF NOT EXISTS staff (
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
        role TEXT DEFAULT 'staff', pin TEXT NOT NULL)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS customer_sales (
        id INTEGER PRIMARY KEY AUTOINCREMENT, customer_id INTEGER NOT NULL,
        item_id INTEGER NOT NULL, quantity INTEGER DEFAULT 1,
        price_paid REAL, note TEXT, sale_date TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (customer_id) REFERENCES customers (id),
        FOREIGN KEY (item_id) REFERENCES items (id))''')
    try:
        cursor.execute("ALTER TABLE customer_sales ADD COLUMN created_by TEXT")
    except:
        pass
    cursor.execute('''CREATE TABLE IF NOT EXISTS bot_config (
        key TEXT PRIMARY KEY, value TEXT NOT NULL)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS item_imeis (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        item_id INTEGER NOT NULL,
        imei TEXT NOT NULL UNIQUE,
        sold INTEGER DEFAULT 0,
        FOREIGN KEY (item_id) REFERENCES items(id))''')
    cursor.execute("INSERT OR IGNORE INTO bot_config (key, value) VALUES ('unlock_pin', '123321')")
    cursor.execute("INSERT OR IGNORE INTO bot_config (key, value) VALUES ('bot_unlock_pin', '123321')")
    cursor.execute("INSERT OR IGNORE INTO bot_config (key, value) VALUES ('stock_alert_threshold', '5')")
    cursor.execute("INSERT OR IGNORE INTO bot_config (key, value) VALUES ('alert_chat_ids', '7185846273')")
    cursor.execute("INSERT OR IGNORE INTO bot_config (key, value) VALUES ('alert_interval_hours', '0')")
    cursor.execute("INSERT OR IGNORE INTO bot_config (key, value) VALUES ('last_alert_time', '0')")
    cursor.execute("INSERT OR IGNORE INTO bot_config (key, value) VALUES ('bill_alert_days', '7')")
    cursor.execute("INSERT OR IGNORE INTO bot_config (key, value) VALUES ('last_bill_alert_time', '0')")
    cursor.execute("INSERT OR IGNORE INTO bot_config (key, value) VALUES ('alert_bill_payment', '1')")
    cursor.execute("INSERT OR IGNORE INTO bot_config (key, value) VALUES ('alert_stock_runout', '1')")
    cursor.execute("INSERT OR IGNORE INTO bot_config (key, value) VALUES ('alert_import', '1')")
    cursor.execute("INSERT OR IGNORE INTO bot_config (key, value) VALUES ('bot_user_level', 'admin')")
    cursor.execute('''CREATE TABLE IF NOT EXISTS notification_users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id INTEGER UNIQUE NOT NULL,
        name TEXT DEFAULT '',
        stock_alerts INTEGER DEFAULT 1,
        bill_alerts INTEGER DEFAULT 1,
        import_alerts INTEGER DEFAULT 1,
        active INTEGER DEFAULT 1,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    # Migrate existing alert_chat_ids into notification_users
    existing = conn.execute("SELECT value FROM bot_config WHERE key='alert_chat_ids'").fetchone()
    if existing:
        ids = [int(x.strip()) for x in existing[0].split(',') if x.strip().isdigit()]
        for cid in ids:
            conn.execute("INSERT OR IGNORE INTO notification_users (chat_id) VALUES (?)", (cid,))
    conn.commit()
    conn.close()
    seed_brands()
    seed_product_groups()
    load_langs()

BRANDS_DATA = [
    ("Samsung", "📱", "🔵"), ("Apple", "🍎", "⚪"), ("Xiaomi", "📱", "🟠"),
    ("Oppo", "📱", "🟢"), ("Vivo", "📱", "🔵"), ("Realme", "📱", "🟡"),
    ("Huawei", "📱", "🔴"), ("Nokia", "📱", "🔵"), ("Sony", "🎮", "⚫"),
    ("LG", "📱", "🔴"), ("Google", "🔍", "🟢"), ("OnePlus", "📱", "🔴"),
    ("Asus", "💻", "🔵"), ("Lenovo", "💻", "🔵"), ("Motorola", "📱", "⚫"),
    ("Honor", "📱", "🔵"), ("Tecno", "📱", "🔵"), ("Infinix", "📱", "🟢"),
    ("BlackBerry", "📱", "⚫"), ("Panasonic", "📱", "🔵"), ("TCL", "📱", "🔴"),
    ("ZTE", "📱", "🔵"), ("Meizu", "📱", "🔵"), ("LeEco", "📱", "🔴"),
    ("Smartphone", "📱", "📱"), ("Tablet", "📟", "🔵"), ("Smartwatch", "⌚", "⚫"),
    ("Laptop", "💻", "⚫"), ("Desktop", "🖥️", "⚫"), ("Monitor", "🖥️", "⚫"),
    ("Headphone", "🎧", "⚫"), ("Earphone", "🎧", "⚪"), ("Speaker", "🔊", "⚫"),
    ("Charger", "🔌", "⚪"), ("Power Bank", "🔋", "🟠"), ("Cable", "🔗", "⚫"),
    ("Case", "📦", "🟡"), ("Screen Protector", "🛡️", "⚪"),
    ("Memory Card", "💾", "🟡"), ("SIM Card", "💳", "🟡"),
    ("Adapter", "🔌", "⚪"), ("Battery", "🔋", "🟢"),
    ("Keyboard", "⌨️", "⚫"), ("Mouse", "🖱️", "⚫"),
    ("Second Hand Phone", "📱", "🟤"), ("Second Hand Tablet", "📟", "🟤"),
    ("Second Hand Laptop", "💻", "🟤"), ("Second Hand Watch", "⌚", "🟤"),
    ("Second Hand Accessory", "🎧", "🟤"), ("Accessory", "🎧", "🟣"),
    ("Service", "🔧", "🔵"), ("Repair", "🛠️", "🟠"),
]

def seed_brands():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    existing = c.execute("SELECT COUNT(*) FROM brands").fetchone()[0]
    if existing == 0:
        for name, emoji, color in BRANDS_DATA:
            c.execute("INSERT OR IGNORE INTO brands (name,emoji,color) VALUES (?,?,?)", (name,emoji,color))
        conn.commit()
    conn.close()

GROUPS_DATA = [
    ("Smart Phone", "📱", "🔵"), ("Accessories", "🎧", "🟣"),
    ("Case", "📦", "🟡"), ("Wholesale Consumer", "🛒", "🟢"),
    ("Other", "📁", "⚪"),
]

def seed_product_groups():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    existing = c.execute("SELECT COUNT(*) FROM product_groups").fetchone()[0]
    if existing == 0:
        for name, emoji, color in GROUPS_DATA:
            c.execute("INSERT OR IGNORE INTO product_groups (name,emoji,color) VALUES (?,?,?)", (name,emoji,color))
        conn.commit()
    conn.close()

class Database:
    @staticmethod
    def add_item(name, category, quantity, price=None, group_name=None, ram=None, rom=None, cost_price=None, product_code=None):
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("INSERT INTO items (name,category,quantity,price,group_name,ram,rom,cost_price,product_code) VALUES (?,?,?,?,?,?,?,?,?)",
                  (name,category,quantity,price,group_name,ram,rom,cost_price,product_code))
        last_id = c.lastrowid
        conn.commit(); conn.close()
        return last_id
    @staticmethod
    def update_item_quantity(item_id, change, cost_price=None):
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        if cost_price is not None:
            c.execute("UPDATE items SET quantity = quantity + ?, cost_price = ? WHERE id = ?", (change, cost_price, item_id))
        else:
            c.execute("UPDATE items SET quantity = quantity + ? WHERE id = ?", (change, item_id))
        conn.commit(); conn.close()
    @staticmethod
    def save_item_imeis(item_id, imeis):
        if not imeis: return
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        for imei in imeis:
            try: c.execute("INSERT OR IGNORE INTO item_imeis (item_id, imei) VALUES (?, ?)", (item_id, imei))
            except: pass
        conn.commit(); conn.close()
    @staticmethod
    def find_imei(imei):
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("SELECT item_id, sold FROM item_imeis WHERE imei=?", (imei,))
        row = c.fetchone(); conn.close(); return row
    @staticmethod
    def mark_imei_sold(imei):
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("UPDATE item_imeis SET sold=1 WHERE imei=?", (imei,))
        conn.commit(); conn.close()
    @staticmethod
    def get_item_imeis(item_id):
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("SELECT imei, sold FROM item_imeis WHERE item_id=? ORDER BY id", (item_id,))
        rows = c.fetchall(); conn.close(); return rows
    @staticmethod
    def get_item(item_id):
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("SELECT id,name,category,quantity,price,group_name,ram,rom,cost_price,product_code FROM items WHERE id=?", (item_id,))
        item = c.fetchone(); conn.close(); return item
    @staticmethod
    def find_items_by_code(code):
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("SELECT id,name,category,quantity,price,group_name,ram,rom,cost_price,product_code FROM items WHERE product_code=? AND quantity>0", (code,))
        items = c.fetchall(); conn.close(); return items
    @staticmethod
    def list_items(category=None):
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        if category: c.execute("SELECT id,name,category,quantity,price,group_name,ram,rom,cost_price FROM items WHERE category=?", (category,))
        else: c.execute("SELECT id,name,category,quantity,price,group_name,ram,rom,cost_price FROM items")
        items = c.fetchall(); conn.close(); return items
    @staticmethod
    def list_items_by_brand(brand):
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("SELECT id,name,quantity,price,group_name,ram,rom,cost_price FROM items WHERE category=? AND quantity>0", (brand,))
        items = c.fetchall(); conn.close(); return items
    @staticmethod
    def find_item(brand, name, ram='', rom=''):
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("SELECT id,name,quantity,price,cost_price,product_code FROM items WHERE category=? AND name=? AND ram=? AND rom=?", (brand,name,ram,rom))
        item = c.fetchone(); conn.close(); return item
    @staticmethod
    def record_sale(item_id, category, quantity):
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("INSERT INTO sales (item_id,category,quantity) VALUES (?,?,?)", (item_id,category,quantity))
        conn.commit(); conn.close()
    @staticmethod
    def record_sellout(item_id, category, quantity, sellout_price, delivery_fee=0, note='', imei=''):
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        cur = c.execute("SELECT quantity FROM items WHERE id = ?", (item_id,))
        row = cur.fetchone()
        if not row or row[0] < quantity:
            conn.close()
            return False
        c.execute("INSERT INTO sales (item_id,category,quantity,sellout_price,delivery_fee,special_note,imei) VALUES (?,?,?,?,?,?,?)",
                  (item_id,category,quantity,str(sellout_price),str(delivery_fee),note,imei))
        c.execute("UPDATE items SET quantity = quantity - ? WHERE id = ?", (quantity, item_id))
        conn.commit(); conn.close()
        return True
    @staticmethod
    def get_sales_report(category=None, start_date=None, end_date=None):
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        q = "SELECT s.timestamp,i.name,s.category,s.quantity,i.price,s.sellout_price,s.delivery_fee,i.cost_price,s.imei FROM sales s JOIN items i ON s.item_id=i.id"
        conds = []; params = []
        if category: conds.append("s.category=?"); params.append(category)
        if start_date and end_date: conds.append("s.timestamp BETWEEN ? AND ?"); params.extend([start_date,end_date])
        if conds: q += " WHERE " + " AND ".join(conds)
        q += " ORDER BY s.id DESC"
        c.execute(q, params); rows = c.fetchall(); conn.close(); return rows
    @staticmethod
    def add_customer(name, location=None, phone=None, phone2=None, phone3=None):
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("INSERT INTO customers (name,location,phone,phone2,phone3) VALUES (?,?,?,?,?)",
                  (name,location,phone,phone2,phone3))
        conn.commit(); conn.close()
    @staticmethod
    def get_customer(customer_id):
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("SELECT id,name,location,phone,phone2,phone3,credit FROM customers WHERE id=?", (customer_id,))
        cust = c.fetchone(); conn.close(); return cust
    @staticmethod
    def record_transaction(customer_id, amount, description=None):
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("INSERT INTO transactions (customer_id,amount,description) VALUES (?,?,?)", (customer_id,amount,description))
        c.execute("UPDATE customers SET credit = credit + ? WHERE id=?", (amount,customer_id))
        conn.commit(); conn.close()
    @staticmethod
    def get_customer_balance(customer_id):
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("SELECT credit FROM customers WHERE id=?", (customer_id,))
        bal = c.fetchone(); conn.close(); return bal[0] if bal else 0
    @staticmethod
    def record_customer_sale(customer_id, items_data, note='', sale_date=None):
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        date = sale_date or datetime.now().strftime('%Y-%m-%d')
        failures = []
        for item_id, qty, price in items_data:
            cur = c.execute("SELECT quantity FROM items WHERE id = ?", (item_id,))
            row = cur.fetchone()
            if not row or row[0] < qty:
                failures.append(item_id)
                continue
            c.execute("INSERT INTO customer_sales (customer_id,item_id,quantity,price_paid,note,sale_date) VALUES (?,?,?,?,?,?)",
                      (customer_id,item_id,qty,price,note,date))
            c.execute("UPDATE items SET quantity = quantity - ? WHERE id = ?", (qty, item_id))
        conn.commit(); conn.close()
        return failures
    @staticmethod
    def list_customers():
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("SELECT id,name,phone,phone2,phone3,credit,location FROM customers")
        custs = c.fetchall(); conn.close(); return custs
    @staticmethod
    def get_customer_transactions(customer_id):
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("SELECT id,timestamp,amount,description FROM transactions WHERE customer_id=? ORDER BY timestamp DESC", (customer_id,))
        rows = c.fetchall(); conn.close(); return rows
    @staticmethod
    def add_brand(name, emoji, color='⚪'):
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO brands (name,emoji,color) VALUES (?,?,?)", (name,emoji,color))
        conn.commit(); conn.close()
    @staticmethod
    def list_brands():
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("SELECT id,name,emoji,color FROM brands")
        rows = c.fetchall(); conn.close(); return rows
    @staticmethod
    def get_brand_emoji(name):
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("SELECT emoji FROM brands WHERE name=?", (name,))
        row = c.fetchone(); conn.close(); return row[0] if row else '📦'
    @staticmethod
    def get_brand_color(name):
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("SELECT color FROM brands WHERE name=?", (name,))
        row = c.fetchone(); conn.close(); return row[0] if row else '⚪'
    @staticmethod
    def get_brand_display(name):
        return f"{Database.get_brand_color(name)}{Database.get_brand_emoji(name)}"
    @staticmethod
    def delete_brand(name):
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("DELETE FROM brands WHERE name=?", (name,))
        deleted = c.rowcount
        conn.commit(); conn.close(); return deleted > 0
    @staticmethod
    def list_groups():
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("SELECT id,name,emoji,color FROM product_groups")
        rows = c.fetchall(); conn.close(); return rows
    @staticmethod
    def get_group_emoji(name):
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("SELECT emoji FROM product_groups WHERE name=?", (name,))
        row = c.fetchone(); conn.close(); return row[0] if row else '📦'
    @staticmethod
    def get_group_color(name):
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("SELECT color FROM product_groups WHERE name=?", (name,))
        row = c.fetchone(); conn.close(); return row[0] if row else '⚪'
    @staticmethod
    def get_group_display(name):
        return f"{Database.get_group_color(name)}{Database.get_group_emoji(name)}"
    @staticmethod
    def list_items_by_group(group_name):
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("SELECT id,name,category,quantity,price,group_name,ram,rom,cost_price FROM items WHERE group_name=? AND quantity>0", (group_name,))
        items = c.fetchall(); conn.close(); return items
    @staticmethod
    def record_debt_with_due(customer_id, amount, description, due_days):
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("INSERT INTO transactions (customer_id,amount,description) VALUES (?,?,?)", (customer_id,amount,description))
        txn_id = c.lastrowid
        from datetime import timedelta
        due = (datetime.now() + timedelta(days=int(due_days))).strftime('%Y-%m-%d')
        c.execute("INSERT INTO payment_schedules (customer_id,transaction_id,due_date,amount,notes) VALUES (?,?,?,?,?)",
                  (customer_id,txn_id,due,amount,description))
        c.execute("UPDATE customers SET credit = credit + ? WHERE id=?", (amount,customer_id))
        conn.commit(); conn.close()
        return due
    @staticmethod
    def record_debt_with_date(customer_id, amount, note, debt_date):
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("INSERT INTO transactions (customer_id,amount,description) VALUES (?,?,?)", (customer_id,amount,note or "Debt recorded"))
        txn_id = c.lastrowid
        c.execute("INSERT INTO payment_schedules (customer_id,transaction_id,due_date,amount,notes) VALUES (?,?,?,?,?)",
                  (customer_id,txn_id,debt_date,amount,note))
        c.execute("UPDATE customers SET credit = credit + ? WHERE id=?", (amount,customer_id))
        conn.commit(); conn.close()
    @staticmethod
    def get_overdue_report():
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        today = datetime.now().strftime('%Y-%m-%d')
        c.execute("""SELECT ps.id,c.id,c.name,ps.amount,ps.due_date,ps.status
                     FROM payment_schedules ps JOIN customers c ON ps.customer_id=c.id
                     WHERE ps.status='pending' ORDER BY ps.due_date ASC""")
        rows = c.fetchall(); conn.close(); return rows
    @staticmethod
    def get_paid_report():
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("""SELECT ps.id,c.id,c.name,ps.amount,ps.due_date,ps.status
                     FROM payment_schedules ps JOIN customers c ON ps.customer_id=c.id
                     WHERE ps.status='paid' ORDER BY ps.due_date DESC LIMIT 5""")
        rows = c.fetchall(); conn.close(); return rows
    @staticmethod
    def get_customer_schedules(customer_id):
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("SELECT id,amount,due_date,status,notes FROM payment_schedules WHERE customer_id=? ORDER BY due_date ASC", (customer_id,))
        rows = c.fetchall(); conn.close(); return rows
    @staticmethod
    def mark_schedule_paid(schedule_id):
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("UPDATE payment_schedules SET status='paid' WHERE id=?", (schedule_id,))
        conn.commit(); conn.close()
    @staticmethod
    def get_customer_unpaid_schedules(customer_id):
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("SELECT id,amount,due_date,notes FROM payment_schedules WHERE customer_id=? AND status='pending' ORDER BY due_date ASC", (customer_id,))
        rows = c.fetchall(); conn.close(); return rows
    @staticmethod
    def pay_schedule(schedule_id, paid_amount):
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("SELECT amount FROM payment_schedules WHERE id=?", (schedule_id,))
        row = c.fetchone()
        if not row: conn.close(); return
        total = row[0]
        if paid_amount >= total:
            c.execute("UPDATE payment_schedules SET status='paid' WHERE id=?", (schedule_id,))
        else:
            remaining = total - paid_amount
            c.execute("UPDATE payment_schedules SET status='partial' WHERE id=?", (schedule_id,))
            c.execute("INSERT INTO payment_schedules (customer_id,transaction_id,due_date,amount,notes,status) SELECT customer_id,transaction_id,due_date,?,notes||' (partial remnant)','pending' FROM payment_schedules WHERE id=?", (remaining, schedule_id))
        conn.commit(); conn.close()
    @staticmethod
    def add_staff(name, role, pin):
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("INSERT INTO staff (name,role,pin) VALUES (?,?,?)", (name,role,pin))
        conn.commit(); conn.close()

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, chat_id=None):
    if chat_id is None:
        chat_id = update.effective_chat.id
    uid = update.effective_user.id
    context.user_data['_uid'] = uid
    if uid in ADMIN_IDS:
        context.user_data['unlocked'] = True
    if not context.user_data.get('unlocked'):
        context.user_data['awaiting_unlock'] = True
        context.user_data['menu_after_unlock'] = True
        kb = [
            [InlineKeyboardButton(_('btn_start', chat_id), callback_data="menu_main")],
            [InlineKeyboardButton(_('btn_language', chat_id), callback_data="menu_language")],
        ]
        await update.message.reply_text("🔒 Enter unlock PIN to access the bot:", reply_markup=InlineKeyboardMarkup(kb))
        return
    keyboard = [
        [InlineKeyboardButton(_('btn_inventory', chat_id), callback_data="menu_inventory")],
        [InlineKeyboardButton(_('btn_sellout', chat_id), callback_data="menu_sellout")],
        [InlineKeyboardButton(_('btn_customers', chat_id), callback_data="menu_customers")],
        [InlineKeyboardButton(_('btn_import', chat_id), callback_data="menu_import")],
        [InlineKeyboardButton(_('btn_language', chat_id), callback_data="menu_language")],
    ]
    if DASHBOARD_URL.startswith("https://"):
        keyboard.insert(-1, [InlineKeyboardButton(_('btn_dashboard', chat_id), url=DASHBOARD_URL)])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        _('main_title', chat_id),
        reply_markup=reply_markup, parse_mode='Markdown'
    )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    context.user_data.pop('awaiting_unlock', None)
    await show_main_menu(update, context, chat_id)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start(update, context)

async def menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    chat_id = update.effective_chat.id
    context.user_data['_uid'] = update.effective_user.id

    if data == "menu_main":
        uid = update.effective_user.id
        if uid in ADMIN_IDS:
            context.user_data['unlocked'] = True
        if not context.user_data.get('unlocked'):
            context.user_data['awaiting_unlock'] = True
            context.user_data['menu_after_unlock'] = True
            kb = [[InlineKeyboardButton(_('btn_language', chat_id), callback_data="menu_language")]]
            await query.edit_message_text("🔒 Enter unlock PIN to access the bot:", reply_markup=InlineKeyboardMarkup(kb))
            return
        context.user_data.pop('awaiting_unlock', None)
        keyboard = [
            [InlineKeyboardButton(_('btn_inventory', chat_id), callback_data="menu_inventory")],
            [InlineKeyboardButton(_('btn_sellout', chat_id), callback_data="menu_sellout")],
            [InlineKeyboardButton(_('btn_customers', chat_id), callback_data="menu_customers")],
            [InlineKeyboardButton(_('btn_import', chat_id), callback_data="menu_import")],
            [InlineKeyboardButton(_('btn_language', chat_id), callback_data="menu_language")],
        ]
        if DASHBOARD_URL.startswith("https://"):
            keyboard.insert(-1, [InlineKeyboardButton(_('btn_dashboard', chat_id), url=DASHBOARD_URL)])
        await query.edit_message_text(_('main_title_short', chat_id), reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        return

    elif data == "menu_language":
        keyboard = [
            [InlineKeyboardButton("🇬🇧 English", callback_data="lang_en")],
            [InlineKeyboardButton("🇰🇭 ភាសាខ្មែរ", callback_data="lang_km")],
            [InlineKeyboardButton(_('btn_back', chat_id), callback_data="menu_main")],
        ]
        await query.edit_message_text("🌐 *Select Language / ជ្រើសរើសភាសា*", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    elif data.startswith("lang_"):
        lang = data[5:]
        set_lang(chat_id, lang)
        await query.edit_message_text(_('msg_lang_changed', chat_id),
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(_('btn_menu', chat_id), callback_data="menu_main")]]))

    elif data == "menu_inventory":
        owner = is_owner(context)
        keyboard = [
            [InlineKeyboardButton(_('btn_inv_list', chat_id), callback_data="inv_list")],
            [InlineKeyboardButton(_('btn_inv_list_brand', chat_id), callback_data="inv_list_brand")],
        ]
        if owner:
            keyboard.append([InlineKeyboardButton(_('btn_inv_add', chat_id), callback_data="inv_add")])
            keyboard.append([InlineKeyboardButton(_('btn_inv_stock', chat_id), callback_data="inv_stock")])
            keyboard.append([InlineKeyboardButton(_('btn_inv_register_code', chat_id), callback_data="inv_register_code")])
        keyboard.append([InlineKeyboardButton(_('btn_inv_brands', chat_id), callback_data="inv_brands")])
        keyboard.append([InlineKeyboardButton(_('btn_back', chat_id), callback_data="menu_main")])
        await query.edit_message_text(_('inv_title', chat_id), reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    elif data == "menu_sellout":
        keyboard = [
            [InlineKeyboardButton(_('btn_sell_record', chat_id), callback_data="sell_record")],
            [InlineKeyboardButton(_('btn_sell_report', chat_id), callback_data="sell_report")],
            [InlineKeyboardButton(_('btn_back', chat_id), callback_data="menu_main")],
        ]
        await query.edit_message_text(_('sell_title', chat_id), reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    elif data == "menu_customers":
        keyboard = [
            [InlineKeyboardButton(_('btn_create_customer', chat_id), callback_data="import_customer")],
            [InlineKeyboardButton(_('btn_cust_balance', chat_id), callback_data="cust_balance")],
            [InlineKeyboardButton(_('btn_cust_buy_record', chat_id), callback_data="cust_buy_record")],
            [InlineKeyboardButton(_('btn_cust_history', chat_id), callback_data="cust_history")],
            [InlineKeyboardButton(_('btn_cust_debt', chat_id), callback_data="cust_debt")],
            [InlineKeyboardButton(_('btn_cust_payment', chat_id), callback_data="cust_payment")],
            [InlineKeyboardButton(_('btn_cust_report', chat_id), callback_data="cust_report")],
            [InlineKeyboardButton(_('btn_back', chat_id), callback_data="menu_main")],
        ]
        await query.edit_message_text(_('cust_title', chat_id), reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    elif data == "menu_import":
        keyboard = [
            [InlineKeyboardButton(_('btn_import_product', chat_id), callback_data="import_product")],
            [InlineKeyboardButton(_('btn_import_staff', chat_id), callback_data="import_staff")],
            [InlineKeyboardButton(_('btn_back', chat_id), callback_data="menu_main")],
        ]
        await query.edit_message_text(_('import_title', chat_id), reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    elif data == "cust_report":
        custs = Database.list_customers()
        if not custs:
            await query.edit_message_text(_('msg_no_customers', chat_id), reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(_('btn_back', chat_id), callback_data="menu_customers")]]))
            return
        resp = _('report_cust_outstanding', chat_id) + "\n"
        any_data = False
        for c in custs:
            bills = Database.get_customer_unpaid_schedules(c[0])
            if bills:
                any_data = True
                phones = ' / '.join(filter(None, [c[2], c[3], c[4]]))
                safe_name = escape_md(c[1])
                resp += f"\n{'─'*20}\n👤 {safe_name} | Bal: ${c[5]:.2f}\n📞 {escape_md(phones) or '—'}\n"
                for b in bills:
                    resp += f"  🔴 ${b[1]:.0f} (Due: {b[2]}) {escape_md(b[3]) or ''}\n"
        if not any_data:
            resp += _('msg_no_outstanding', chat_id)
        await query.edit_message_text(resp, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(_('btn_back', chat_id), callback_data="menu_customers")]]), parse_mode='Markdown')

    # --- Inventory actions ---
    elif data == "inv_list":
        items = Database.list_items()
        if not items:
            await query.edit_message_text(_('msg_no_items', chat_id), reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(_('btn_back', chat_id), callback_data="menu_inventory")]]))
            return
        owner = is_owner(context)
        resp = _('report_inv_all', chat_id) + "\n"
        total_inv = 0
        for i in items:
            disp = Database.get_brand_display(i[2])
            safe_cat = escape_md(i[2])
            safe_name = escape_md(i[1])
            safe_ram = escape_md(i[6])
            safe_rom = escape_md(i[7])
            spec = f" {safe_ram}/{safe_rom}" if i[6] or i[7] else ''
            cost = i[8] or 0
            inv = i[3] * cost
            total_inv += inv
            margin = (i[4] - cost) / cost * 100 if cost and i[4] else 0
            if owner:
                resp += f"ID:{i[0]} {disp} {safe_name}{spec} Qty:{i[3]} R:${i[4] or 'N/A'} C:${cost:.0f} /{margin:+.0f}%\n"
            else:
                resp += f"ID:{i[0]} {disp} {safe_name}{spec} Qty:{i[3]} R:${i[4] or 'N/A'}\n"
        if owner:
            resp += f"\n{'─'*20}\n💵 {_('total_investment', chat_id)}: ${total_inv:.0f}"
        await query.edit_message_text(resp, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(_('btn_back', chat_id), callback_data="menu_inventory")]]), parse_mode='Markdown')

    elif data == "inv_list_brand":
        brands = Database.list_brands()
        if not brands:
            await query.edit_message_text(_('msg_no_brands', chat_id), reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(_('btn_back', chat_id), callback_data="menu_inventory")]]))
            return
        keyboard = [[InlineKeyboardButton(f"{b[3]}{b[2]} {b[1]}", callback_data=f"inv_brand_{b[1]}")] for b in brands]
        keyboard.append([InlineKeyboardButton(_('btn_back', chat_id), callback_data="menu_inventory")])
        await query.edit_message_text(_('prompt_select_brand', chat_id), reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    elif data.startswith("inv_brand_"):
        brand = data[10:]
        items = Database.list_items(brand)
        if not items:
            await query.edit_message_text(_f('msg_no_items_brand', chat_id, brand=brand), reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(_('btn_back', chat_id), callback_data="inv_list_brand")]]))
            return
        owner = is_owner(context)
        resp = _f('report_inv_brand', chat_id, brand=escape_md(brand)) + "\n"
        total_inv = 0
        for i in items:
            spec = f" {i[6]}/{i[7]}" if i[6] or i[7] else ''
            cost = i[8] or 0
            inv = i[3] * cost
            total_inv += inv
            margin = (i[4] - cost) / cost * 100 if cost and i[4] else 0
            safe_name = escape_md(i[1])
            safe_ram = escape_md(i[6])
            safe_rom = escape_md(i[7])
            spec = f" {safe_ram}/{safe_rom}" if i[6] or i[7] else ''
            if owner:
                resp += f"ID:{i[0]} {safe_name}{spec} Qty:{i[3]} R:${i[4] or 'N/A'} C:${cost:.0f} /{margin:+.0f}%\n"
            else:
                resp += f"ID:{i[0]} {safe_name}{spec} Qty:{i[3]} R:${i[4] or 'N/A'}\n"
        if owner:
            resp += f"\n{'─'*20}\n💵 {_('total_investment', chat_id)}: ${total_inv:.0f}"
        await query.edit_message_text(resp, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(_('btn_back', chat_id), callback_data="inv_list_brand")]]), parse_mode='Markdown')

    elif data == "inv_stock":
        await start_add_stock(update, context)

    elif data == "inv_brands":
        brands = Database.list_brands()
        if not brands:
            await query.edit_message_text(_('msg_no_brands', chat_id), reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(_('btn_add_brand', chat_id), callback_data="inv_add_brand"), InlineKeyboardButton(_('btn_back', chat_id), callback_data="menu_inventory")]]))
            return
        resp = _('report_brands', chat_id) + "\n"
        for b in brands:
            resp += f"ID:{b[0]} {b[3]}{b[2]} {escape_md(b[1])}\n"
        resp += "\nTap below to add a brand:"
        await query.edit_message_text(resp, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(_('btn_add_brand', chat_id), callback_data="inv_add_brand")], [InlineKeyboardButton(_('btn_back', chat_id), callback_data="menu_inventory")]]), parse_mode='Markdown')

    elif data == "inv_add_brand":
        await start_add_brand(update, context)

    # --- Sellout actions ---
    elif data == "sell_record":
        await start_sell(update, context)

    elif data == "sell_report":
        sales = Database.get_sales_report()
        if not sales:
            await query.edit_message_text(_('msg_no_sales', chat_id), reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(_('btn_back', chat_id), callback_data="menu_sellout")]]))
            return
        show_owner = is_owner(context)
        resp = _('report_sales', chat_id) + "\n"
        ts = 0; tr = 0; tp = 0
        for s in sales[:10]:
            retail = s[4] or 0
            sellout = float(s[5]) if s[5] else retail * s[3]
            fee = float(s[6]) if s[6] else 0
            cost = s[7] or 0
            profit = (sellout - fee) - cost * s[3]
            imei = s[8] or ''
            line = f"{s[0][:10]} {escape_md(s[1])} x{s[3]} Sell:${sellout:.0f}"
            if imei: line += f" IMEI:{escape_md(imei)}"
            if show_owner: line += f" Profit:${profit:.0f}"
            resp += line + "\n"
            ts += s[3]; tr += sellout; tp += profit
        resp += f"\n{_('report_total_qty', chat_id)} {ts}\n{_('report_total_revenue', chat_id)} ${tr:.0f}"
        if show_owner:
            resp += f"\n{_('report_total_profit', chat_id)} ${tp:.0f}"
        await query.edit_message_text(resp, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(_('btn_back', chat_id), callback_data="menu_sellout")]]), parse_mode='Markdown')

    # --- Customer actions ---
    elif data == "cust_list":
        custs = Database.list_customers()
        if not custs:
            await query.edit_message_text(_('msg_no_customers', chat_id), reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(_('btn_back', chat_id), callback_data="menu_customers")]]))
            return
        resp = _('report_customers', chat_id) + "\n"
        for c in custs:
            phones = ' / '.join(filter(None, [c[2], c[3], c[4]]))
            safe_name = escape_md(c[1])
            resp += f"ID:{c[0]} {safe_name} {escape_md(c[6] or '')} {escape_md(phones) if phones else 'N/A'} Balance:${c[5]:.2f}\n"
        await query.edit_message_text(resp, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(_('btn_back', chat_id), callback_data="menu_customers")]]), parse_mode='Markdown')

    elif data == "cust_payment_report":
        await payment_report(update, context)

    # --- Import actions (handled by conversation entry points) ---

@require_access
async def add_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) < 3:
        msg = "Usage: /additem <name> <brand> <qty> [price] [group]"
        await update.message.reply_text(msg)
        return
    try:
        group = args[4] if len(args) > 4 else None
        price = float(args[3]) if len(args) > 3 else None
        Database.add_item(args[0], args[1], int(args[2]), price, group)
        disp = Database.get_brand_display(args[1])
        await update.message.reply_text(f"Added: {disp} {args[0]}, Qty: {args[2]}")
    except: await update.message.reply_text("Invalid input")

@require_access
async def import_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) < 2: await update.message.reply_text("Usage: /import <item_id> <quantity>"); return
    try:
        qty = int(args[1])
        if qty <= 0:
            await update.message.reply_text("❌ Quantity must be positive.")
            return
        Database.update_item_quantity(int(args[0]), qty)
        await update.message.reply_text(f"Added {qty} units to item {args[0]}")
    except: await update.message.reply_text("Invalid input")

@require_access
async def sell(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) < 2: await update.message.reply_text("Usage: /sell <item_id> <quantity>"); return
    try:
        item = Database.get_item(int(args[0]))
        if not item: await update.message.reply_text("Item not found"); return
        qty = int(args[1])
        if qty <= 0: await update.message.reply_text("❌ Quantity must be positive."); return
        if item[3] < qty: await update.message.reply_text(f"Insufficient stock. Available: {item[3]}"); return
        Database.update_item_quantity(item[0], -qty)
        Database.record_sale(item[0], item[2], qty)
        await update.message.reply_text(f"Sold {qty} units of {item[1]}")
    except: await update.message.reply_text("Invalid input")

@require_access
async def list_items(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cat = context.args[0] if context.args else None
    items = Database.list_items(cat)
    if not items: await update.message.reply_text("No items found"); return
    resp = "Inventory:\n"
    for i in items:
        disp = Database.get_brand_display(i[2])
        spec = f" {i[6]}/{i[7]}" if i[6] or i[7] else ''
        resp += f"ID:{i[0]} {disp}{i[1]}{spec} ({i[2]}) Qty:{i[3]} Retail:${i[4] or 'N/A'}\n"
    await update.message.reply_text(resp)

@require_access
async def report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args; cat=None; sd=None; ed=None
    if len(args)>=1: cat=args[0]
    if len(args)>=3: sd=args[1]; ed=args[2]
    sales = Database.get_sales_report(cat,sd,ed)
    if not sales: await update.message.reply_text("No sales found"); return
    resp = "Sales Report:\n"; ts=0; tr=0
    for s in sales:
        disp = Database.get_brand_display(s[2])
        price = s[4] or 0
        resp += f"Date:{s[0]} {disp}{s[1]} ({s[2]}) Qty:{s[3]} Price:{price} Total:{s[3]*price}\n"
        ts+=s[3]; tr+=s[3]*price
    resp += f"\nTotal Sales:{ts} Total Revenue:{tr}"
    await update.message.reply_text(resp)

@require_access
async def add_brand(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /addbrand <name> <emoji> [color]\nColor: 🔴🟠🟡🟢🔵🟣🟤⚫⚪\nExample: /addbrand Samsung 📱 🔵")
        return
    try:
        name = context.args[0]; emoji = context.args[1]
        if len(name) > 40:
            await update.message.reply_text("Brand name too long (max 40 characters).")
            return
        color = context.args[2] if len(context.args) > 2 else '⚪'
        Database.add_brand(name, emoji, color)
        await update.message.reply_text(f"Brand added: {color}{emoji} {name}")
    except: await update.message.reply_text("Invalid input")

@require_access
async def list_brands(update: Update, context: ContextTypes.DEFAULT_TYPE):
    brands = Database.list_brands()
    if not brands:
        await update.message.reply_text("No brands registered. Use /addbrand to add one.")
        return
    resp = "Registered Brands (color + emoji):\n"
    for b in brands:
        resp += f"ID:{b[0]} {b[3]}{b[2]} {b[1]}\n"
    await update.message.reply_text(resp)

@require_access
async def delete_brand(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 1:
        await update.message.reply_text("Usage: /deletebrand <name>\nUse /listbrands to see brand names.")
        return
    try:
        name = ' '.join(context.args)
        if Database.delete_brand(name):
            await update.message.reply_text(f"Brand deleted: {name}")
        else:
            await update.message.reply_text(f"Brand '{name}' not found.")
    except:
        await update.message.reply_text("Error deleting brand")

# Conversation states
ADD_GROUP, ADD_NAME, ADD_BRAND, ADD_RAM, ADD_ROM, ADD_QTY, ADD_PRICE = range(7)

async def start_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = update.effective_chat.id
    groups = Database.list_groups()
    keyboard = [[InlineKeyboardButton(f"{g[3]}{g[2]} {g[1]}", callback_data=f"selgroup_{g[1]}")] for g in groups]
    keyboard.append([InlineKeyboardButton(_('btn_cancel', chat_id), callback_data="menu_inventory")])
    await query.edit_message_text(_('prompt_select_group', chat_id), reply_markup=InlineKeyboardMarkup(keyboard))
    return ADD_GROUP

async def get_add_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = update.effective_chat.id
    group = query.data[9:]
    context.user_data['item_group'] = group
    await query.edit_message_text(f"{Database.get_group_display(group)} {group}\n{_('prompt_enter_name', chat_id)}",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(_('btn_cancel', chat_id), callback_data="menu_inventory")]]))
    return ADD_NAME

async def get_add_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['conv_state'] = ADD_NAME
    chat_id = update.effective_chat.id
    context.user_data['item_name'] = update.message.text
    brands = Database.list_brands()
    keyboard = [[InlineKeyboardButton(f"{b[3]}{b[2]} {b[1]}", callback_data=f"selbrand_{b[1]}")] for b in brands]
    keyboard.append([InlineKeyboardButton(_('btn_cancel', chat_id), callback_data="menu_inventory")])
    await update.message.reply_text(_('prompt_select_brand', chat_id), reply_markup=InlineKeyboardMarkup(keyboard))
    return ADD_BRAND

async def get_add_brand(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = update.effective_chat.id
    brand = query.data[9:]
    context.user_data['item_brand'] = brand
    disp = Database.get_brand_display(brand)
    group = context.user_data.get('item_group', '')
    group_disp = f"{Database.get_group_display(group)} {group}" if group else ''
    await query.edit_message_text(f"{group_disp}\n{disp} {brand}\n{_('prompt_enter_ram', chat_id)}")
    return ADD_RAM

async def get_add_ram(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['conv_state'] = ADD_RAM
    chat_id = update.effective_chat.id
    text = update.message.text.strip()
    context.user_data['item_ram'] = '' if text.lower() == 'skip' else text
    await update.message.reply_text(_('prompt_enter_rom', chat_id))
    return ADD_ROM

async def get_add_rom(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['conv_state'] = ADD_ROM
    chat_id = update.effective_chat.id
    text = update.message.text.strip()
    context.user_data['item_rom'] = '' if text.lower() == 'skip' else text
    await update.message.reply_text(_('prompt_enter_qty', chat_id))
    return ADD_QTY

async def get_add_qty(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['conv_state'] = ADD_QTY
    chat_id = update.effective_chat.id
    try:
        qty = int(update.message.text)
        if qty <= 0: raise ValueError
        context.user_data['item_qty'] = qty
        await update.message.reply_text(_('prompt_enter_sellin_price', chat_id))
        return ADD_PRICE
    except:
        await update.message.reply_text(_('msg_invalid_qty', chat_id))
        return ADD_QTY

async def get_add_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['conv_state'] = ADD_PRICE
    chat_id = update.effective_chat.id
    text = update.message.text
    price = None
    if text.lower() != 'skip':
        try:
            price = float(text)
            if price <= 0: raise ValueError
        except:
            await update.message.reply_text(_('msg_invalid_price_skip', chat_id))
            return ADD_PRICE
    name = context.user_data['item_name']
    brand = context.user_data['item_brand']
    qty = context.user_data['item_qty']
    group = context.user_data.get('item_group')
    ram = context.user_data.get('item_ram', '')
    rom = context.user_data.get('item_rom', '')
    Database.add_item(name, brand, qty, price, group, ram, rom, cost_price=price)
    disp = Database.get_brand_display(brand)
    group_disp = f"{Database.get_group_display(group)} {group} - " if group else ''
    spec = f" {ram}/{rom}" if ram or rom else ''
    await update.message.reply_text(f"✅ Added: {group_disp}{disp} {name}{spec}\nQty: {qty}{f', Cost: ${price}' if price else ''}",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(_('btn_menu', chat_id), callback_data="menu_main")]]))
    clear_user_data(context)
    return ConversationHandler.END

async def cancel_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await update.message.reply_text(_('msg_cancelled', chat_id))
    clear_user_data(context)
    return ConversationHandler.END

async def cancel_add_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = update.effective_chat.id
    await query.edit_message_text(_('msg_cancelled', chat_id))
    clear_user_data(context)
    return ConversationHandler.END

conv_handler_item = ConversationHandler(
    entry_points=[CallbackQueryHandler(start_add, pattern="^inv_add$")],
    states={
        ADD_GROUP: [CallbackQueryHandler(get_add_group, pattern="^selgroup_")],
        ADD_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_add_name), CallbackQueryHandler(guard_callback, pattern="^(?!menu_).*$")],
        ADD_BRAND: [CallbackQueryHandler(get_add_brand, pattern="^selbrand_")],
        ADD_RAM: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_add_ram), CallbackQueryHandler(guard_callback, pattern="^(?!menu_).*$")],
        ADD_ROM: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_add_rom), CallbackQueryHandler(guard_callback, pattern="^(?!menu_).*$")],
        ADD_QTY: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_add_qty), CallbackQueryHandler(guard_callback, pattern="^(?!menu_).*$")],
        ADD_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_add_price), CallbackQueryHandler(guard_callback, pattern="^(?!menu_).*$")],
    },
    fallbacks=[
        CommandHandler("cancel", cancel_add),
        CallbackQueryHandler(cancel_add_callback, pattern="^menu_inventory$"),
    ],
)

# Sellout conversation states
SEL_CODE, SEL_SPEC, SEL_PRICE, SEL_DELIVERY, SEL_FEE, SEL_NOTE = range(12, 18)

async def start_sell(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = update.effective_chat.id
    await query.edit_message_text("🔍 Enter/scan product code:")
    return SEL_CODE

async def get_sel_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['conv_state'] = SEL_CODE
    chat_id = update.effective_chat.id
    code = update.message.text.strip()
    if not code:
        await update.message.reply_text("❌ Enter/scan a product code or IMEI:")
        return SEL_CODE
    # Check IMEI first
    imei_row = Database.find_imei(code)
    if imei_row:
        item_id, sold = imei_row
        if sold:
            await update.message.reply_text("❌ This IMEI is already sold. Try another:")
            return SEL_CODE
        item = Database.get_item(item_id)
        if item and item[3] > 0:
            context.user_data['sel_item_id'] = item[0]
            context.user_data['sel_item_name'] = item[1]
            context.user_data['sel_item_brand'] = item[2]
            context.user_data['sel_retail'] = item[4] or 0
            context.user_data['sel_cost'] = item[8] or 0
            context.user_data['sel_group'] = item[5] or item[2]
            context.user_data['sel_scanned_imei'] = code
            spec = f" ({item[6]}/{item[7]})" if item[6] or item[7] else ''
            await update.message.reply_text(f"📱 IMEI found: {code}\n✅ {item[1]}{spec} ({item[2]})\n💰 Enter actual sell price:")
            return SEL_PRICE
        await update.message.reply_text("❌ Item not found or out of stock. Try again:")
        return SEL_CODE
    # Fallback to product code
    items = Database.find_items_by_code(code)
    if not items:
        await update.message.reply_text("❌ No product found with that code or IMEI. Try again or /cancel:")
        return SEL_CODE
    if len(items) == 1:
        item = items[0]
        context.user_data['sel_item_id'] = item[0]
        context.user_data['sel_item_name'] = item[1]
        context.user_data['sel_item_brand'] = item[2]
        context.user_data['sel_retail'] = item[4] or 0
        context.user_data['sel_cost'] = item[8] or 0
        context.user_data['sel_group'] = item[5] or item[2]
        spec = f" ({item[6]}/{item[7]})" if item[6] or item[7] else ''
        await update.message.reply_text(f"✅ {item[1]}{spec} ({item[2]})\n💰 Enter actual sell price:")
        return SEL_PRICE
    context.user_data['sel_code_items'] = items
    keyboard = []
    for i, item in enumerate(items):
        spec = f"{item[6]}/{item[7]}" if item[6] or item[7] else 'N/A'
        price = f"${item[4]:.2f}" if item[4] else '?'
        keyboard.append([InlineKeyboardButton(f"{spec} - {price}", callback_data=f"selcode_{i}")])
    await update.message.reply_text("Multiple specs found. Choose one:",
        reply_markup=InlineKeyboardMarkup(keyboard))
    return SEL_SPEC

async def get_sel_spec(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    idx = int(query.data[8:])
    items = context.user_data.get('sel_code_items', [])
    if idx < 0 or idx >= len(items):
        await query.edit_message_text("❌ Invalid selection.")
        return ConversationHandler.END
    item = items[idx]
    context.user_data['sel_item_id'] = item[0]
    context.user_data['sel_item_name'] = item[1]
    context.user_data['sel_item_brand'] = item[2]
    context.user_data['sel_retail'] = item[4] or 0
    context.user_data['sel_cost'] = item[8] or 0
    context.user_data['sel_group'] = item[5] or item[2]
    spec = f" ({item[6]}/{item[7]})" if item[6] or item[7] else ''
    context.user_data.pop('sel_code_items', None)
    await query.edit_message_text(f"✅ {item[1]}{spec} ({item[2]})\n💰 Enter actual sell price:")
    return SEL_PRICE

async def get_sel_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['conv_state'] = SEL_PRICE
    chat_id = update.effective_chat.id
    try:
        price = float(update.message.text)
        if price < 0:
            await update.message.reply_text("❌ Price cannot be negative. Enter again:")
            return SEL_PRICE
        context.user_data['sel_sellin'] = price
        keyboard = [
            [InlineKeyboardButton("✅ Yes", callback_data="sel_delivery_yes")],
            [InlineKeyboardButton("❌ No", callback_data="sel_delivery_no")],
        ]
        await update.message.reply_text(f"💰 Sell price: ${price:.2f}\n🚚 Delivery fee?", reply_markup=InlineKeyboardMarkup(keyboard))
        return SEL_DELIVERY
    except:
        await update.message.reply_text("❌ Invalid number. Enter sell price:")
        return SEL_PRICE

async def get_sel_delivery(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "sel_delivery_no":
        context.user_data['sel_fee'] = 0
        chat_id = update.effective_chat.id
        await query.edit_message_text("📝 Enter special note (or type 'skip'):")
        return SEL_NOTE
    else:
        chat_id = update.effective_chat.id
        await query.edit_message_text("💰 Enter delivery fee amount:")
        return SEL_FEE

async def get_sel_fee(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['conv_state'] = SEL_FEE
    chat_id = update.effective_chat.id
    try:
        fee = float(update.message.text)
        if fee < 0: raise ValueError
        context.user_data['sel_fee'] = fee
        await update.message.reply_text("📝 Enter special note (or type 'skip'):")
        return SEL_NOTE
    except:
        await update.message.reply_text("❌ Invalid amount. Enter delivery fee:")
        return SEL_FEE

async def get_sel_note(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['conv_state'] = SEL_NOTE
    chat_id = update.effective_chat.id
    text = update.message.text.strip()
    context.user_data['sel_policy'] = '' if text.lower() == 'skip' else text
    context.user_data['sel_discount'] = context.user_data.get('sel_retail', 0) - context.user_data.get('sel_sellin', 0)
    fee = context.user_data.get('sel_fee', 0)
    await complete_sellout(update.message, context, fee)
    return ConversationHandler.END

async def complete_sellout(query_or_msg, context, fee=None):
    item_id = context.user_data['sel_item_id']
    name = context.user_data['sel_item_name']
    brand = context.user_data['sel_item_brand']
    retail = context.user_data['sel_retail']
    sellin = context.user_data['sel_sellin']
    discount = context.user_data.get('sel_discount', retail - sellin)
    policy = context.user_data.get('sel_policy', '')
    fee = fee if fee is not None else context.user_data.get('sel_fee', 0)
    total = sellin + fee
    gname = context.user_data.get('sel_group', brand)
    gdisp = Database.get_group_display(gname)
    disp = Database.get_brand_display(brand)
    cost = context.user_data.get('sel_cost', 0)
    profit = sellin - cost - fee
    chat_id = query_or_msg.chat.id if hasattr(query_or_msg, 'chat') else None
    show_owner = is_owner(context)
    scanned_imei = context.user_data.get('sel_scanned_imei', '')
    ok = Database.record_sellout(item_id, brand, 1, sellin, fee, policy, scanned_imei)
    if not ok:
        if hasattr(query_or_msg, 'answer'):
            await query_or_msg.edit_message_text("❌ Out of stock. Sale not recorded.")
        else:
            await query_or_msg.reply_text("❌ Out of stock. Sale not recorded.")
        clear_user_data(context)
        return ConversationHandler.END
    if scanned_imei:
        Database.mark_imei_sold(scanned_imei)
    # Consolidated stock alert — check ALL low-stock items (respects interval)
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.execute("SELECT value FROM bot_config WHERE key='stock_alert_threshold'")
        threshold_row = cur.fetchone()
        cur = conn.execute("SELECT value FROM bot_config WHERE key='alert_interval_hours'")
        interval_row = cur.fetchone()
        cur = conn.execute("SELECT value FROM bot_config WHERE key='last_alert_time'")
        last_row = cur.fetchone()
        threshold = int(threshold_row[0]) if threshold_row else 5
        interval_hours = float(interval_row[0]) if interval_row else 0
        last_alert = float(last_row[0]) if last_row else 0
        now = time.time()
        if interval_hours <= 0 or (now - last_alert) >= interval_hours * 3600:
            target_ids = [r[0] for r in conn.execute("SELECT chat_id FROM notification_users WHERE stock_alerts=1 AND active=1").fetchall()]
            cur = conn.execute("SELECT i.name, i.category, i.quantity FROM items i WHERE i.quantity <= ? ORDER BY i.quantity ASC", (threshold,))
            low_items = cur.fetchall()
            if low_items:
                lines = [f"• {escape_md(item[1])} {escape_md(item[0])} — *{item[2]} left*" for item in low_items]
                msg = (
                    f"⚠️ *Low Stock Alert* (≤{threshold})\n\n"
                    + "\n".join(lines[:15])
                )
                if len(low_items) > 15:
                    msg += f"\n\n... and {len(low_items)-15} more items"
                for cid in target_ids:
                    try:
                        await context.application.bot.send_message(cid, msg, parse_mode='Markdown')
                    except Exception:
                        pass
                conn.execute("UPDATE bot_config SET value = ? WHERE key = 'last_alert_time'", (str(now),))
                conn.commit()
        conn.close()
    except Exception:
        pass
    report = (
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"✅ {_('report_sellout_header', chat_id)}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"{gdisp} {gname}\n"
        f"{disp} {name}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 {_('report_sellin', chat_id)}   ${sellin:.2f}\n")
    if show_owner and retail:
        report += f"🏷️ {_('report_retail', chat_id)} ${retail:.2f} (discount ${discount:.2f})\n"
    if show_owner:
        report += f"📊 {_('report_cost', chat_id)}     ${cost:.2f}\n"
        report += f"📈 {_('report_profit', chat_id)}         ${profit:.2f}\n"
    report += (
        f"📝 {_('report_policy', chat_id)} {policy or 'N/A'}\n"
        f"🚚 {_('report_delivery', chat_id)}   ${fee:.2f}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💵 {_('report_total_charged', chat_id)}  ${total:.2f}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"{datetime.now().strftime('%Y-%m-%d %H:%M')}"
    )
    if hasattr(query_or_msg, 'answer'):
        await query_or_msg.edit_message_text(report)
    else:
        await query_or_msg.reply_text(report)
    unlocked = context.user_data.pop('unlocked', None)
    clear_user_data(context)
    if unlocked:
        context.user_data['unlocked'] = True
    return ConversationHandler.END

async def cancel_sell(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await update.message.reply_text(_('msg_cancelled', chat_id))
    unlocked = context.user_data.pop('unlocked', None)
    clear_user_data(context)
    if unlocked:
        context.user_data['unlocked'] = True
    return ConversationHandler.END

async def cancel_sell_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = update.effective_chat.id
    await query.edit_message_text(_('msg_cancelled', chat_id))
    unlocked = context.user_data.pop('unlocked', None)
    clear_user_data(context)
    if unlocked:
        context.user_data['unlocked'] = True
    return ConversationHandler.END

conv_handler_sell = ConversationHandler(
    entry_points=[CallbackQueryHandler(start_sell, pattern="^sell_record$")],
    states={
        SEL_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_sel_code), CallbackQueryHandler(guard_callback, pattern="^(?!menu_).*$")],
        SEL_SPEC: [CallbackQueryHandler(get_sel_spec, pattern="^selcode_")],
        SEL_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_sel_price), CallbackQueryHandler(guard_callback, pattern="^(?!menu_).*$")],
        SEL_DELIVERY: [CallbackQueryHandler(get_sel_delivery, pattern="^sel_delivery_(yes|no)$")],
        SEL_FEE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_sel_fee), CallbackQueryHandler(guard_callback, pattern="^(?!menu_).*$")],
        SEL_NOTE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_sel_note), CallbackQueryHandler(guard_callback, pattern="^(?!menu_).*$")],
    },
    fallbacks=[
        CommandHandler("cancel", cancel_sell),
        CallbackQueryHandler(cancel_sell_callback, pattern="^menu_sellout$"),
    ],
)

# ──────────────────────────────
# ADD STOCK conversation
# ──────────────────────────────
STK_BRAND, STK_ITEM = range(18, 20)

async def start_add_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = update.effective_chat.id
    brands = Database.list_brands()
    keyboard = [[InlineKeyboardButton(f"{b[3]}{b[2]} {b[1]}", callback_data=f"stkbrand_{b[1]}")] for b in brands]
    keyboard.append([InlineKeyboardButton(_('btn_cancel', chat_id), callback_data="menu_inventory")])
    await query.edit_message_text(_('prompt_select_brand', chat_id), reply_markup=InlineKeyboardMarkup(keyboard))
    return STK_BRAND

async def get_stk_brand(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = update.effective_chat.id
    brand = query.data[9:]
    context.user_data['stk_brand'] = brand
    items = Database.list_items_by_brand(brand)
    if not items:
        await query.edit_message_text(_f('msg_no_items_brand', chat_id, brand=brand), reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(_('btn_cancel', chat_id), callback_data="menu_inventory")]]))
        return ConversationHandler.END
    keyboard = [[InlineKeyboardButton(f"{i[1]} (Stock: {i[2]})", callback_data=f"stkitem_{i[0]}")] for i in items]
    keyboard.append([InlineKeyboardButton(_('btn_cancel', chat_id), callback_data="menu_inventory")])
    await query.edit_message_text(f"{Database.get_brand_display(brand)} {brand}\n{_('prompt_select_item', chat_id)}", reply_markup=InlineKeyboardMarkup(keyboard))
    return STK_ITEM

async def get_stk_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = update.effective_chat.id
    item_id = int(query.data[8:])
    item = Database.get_item(item_id)
    if not item:
        await query.edit_message_text(_('msg_item_not_found', chat_id),
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(_('btn_cancel', chat_id), callback_data="menu_inventory")]]))
        return ConversationHandler.END
    name = item[1]
    brand = item[2]
    retail = item[4] or 0
    qty = item[3]
    cost = item[8] or 0
    spec = f" ({item[6]}/{item[7]})" if item[6] or item[7] else ''
    report = (
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📦 *{name}*{spec}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"{_('report_retail', chat_id)} ${retail:.2f}\n"
        f"{_('report_cost', chat_id)} ${cost:.2f}\n"
        f"📊 *Stock:* {qty}\n"
        f"━━━━━━━━━━━━━━━━━━━━"
    )
    await query.edit_message_text(report,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(_('btn_back', chat_id), callback_data="menu_inventory")]]))
    return ConversationHandler.END

conv_handler_stock = ConversationHandler(
    entry_points=[CallbackQueryHandler(start_add_stock, pattern="^inv_stock$")],
    states={
        STK_BRAND: [CallbackQueryHandler(get_stk_brand, pattern="^stkbrand_")],
        STK_ITEM: [CallbackQueryHandler(get_stk_item, pattern="^stkitem_")],
    },
    fallbacks=[CallbackQueryHandler(cancel_add_callback, pattern="^menu_inventory$")],
)

# ──────────────────────────────
# ADD BRAND conversation
# ──────────────────────────────
BRD_NAME, BRD_EMOJI, BRD_COLOR = range(20, 23)

async def start_add_brand(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = update.effective_chat.id
    await query.edit_message_text(_('prompt_enter_name', chat_id),
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(_('btn_cancel', chat_id), callback_data="menu_inventory")]]))
    return BRD_NAME

async def get_brd_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['conv_state'] = BRD_NAME
    chat_id = update.effective_chat.id
    if len(update.message.text) > 40:
        await update.message.reply_text("❌ Brand name too long (max 40 characters). Enter a shorter name:")
        return BRD_NAME
    context.user_data['brd_name'] = update.message.text
    await update.message.reply_text(_('prompt_enter_emoji', chat_id),
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(_('btn_cancel', chat_id), callback_data="menu_inventory")]]))
    return BRD_EMOJI

async def get_brd_emoji(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['conv_state'] = BRD_EMOJI
    chat_id = update.effective_chat.id
    context.user_data['brd_emoji'] = update.message.text
    colors = [("🔴","🔴"),("🟠","🟠"),("🟡","🟡"),("🟢","🟢"),("🔵","🔵"),
              ("🟣","🟣"),("🟤","🟤"),("⚫","⚫"),("⚪","⚪")]
    keyboard = [[InlineKeyboardButton(c[0], callback_data=f"brdcolor_{c[1]}")] for c in colors]
    await update.message.reply_text(_('prompt_select_color', chat_id), reply_markup=InlineKeyboardMarkup(keyboard))
    return BRD_COLOR

async def get_brd_color(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = update.effective_chat.id
    color = query.data[9:]
    name = context.user_data['brd_name']
    emoji = context.user_data['brd_emoji']
    Database.add_brand(name, emoji, color)
    await query.edit_message_text(f"✅ Brand added: {color}{emoji} {name}",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(_('btn_menu', chat_id), callback_data="menu_main")]]))
    clear_user_data(context)
    return ConversationHandler.END

async def brd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await update.message.reply_text(_('msg_cancelled', chat_id)); clear_user_data(context); return ConversationHandler.END

conv_handler_brand = ConversationHandler(
    entry_points=[CallbackQueryHandler(start_add_brand, pattern="^inv_add_brand$")],
    states={
        BRD_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_brd_name), CallbackQueryHandler(guard_callback, pattern="^(?!menu_).*$")],
        BRD_EMOJI: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_brd_emoji), CallbackQueryHandler(guard_callback, pattern="^(?!menu_).*$")],
        BRD_COLOR: [CallbackQueryHandler(get_brd_color, pattern="^brdcolor_")],
    },
    fallbacks=[CommandHandler("cancel", brd_cancel), CallbackQueryHandler(cancel_add_callback, pattern="^menu_inventory$")],
)

# ──────────────────────────────
# IMPORT PRODUCT conversation (group → brand → name → RAM → ROM → retail price)
# ──────────────────────────────
IP_GROUP, IP_BRAND, IP_NAME, IP_RAM, IP_ROM, IP_PRICE, IP_DUP_ACTION, IP_DUP_QTY, IP_QTY = range(23, 32)
IP_IMEI = 52

IP_CODE = 53

IP_COST = 54
async def start_import_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = update.effective_chat.id
    groups = Database.list_groups()
    keyboard = [[InlineKeyboardButton(f"{g[3]}{g[2]} {g[1]}", callback_data=f"ipgroup_{g[1]}")] for g in groups]
    keyboard.append([InlineKeyboardButton(_('btn_cancel', chat_id), callback_data="menu_import")])
    await query.edit_message_text(_('prompt_select_group', chat_id), reply_markup=InlineKeyboardMarkup(keyboard))
    return IP_GROUP

async def get_ip_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    chat_id = update.effective_chat.id
    context.user_data['ip_group'] = query.data[7:]
    brands = Database.list_brands()
    keyboard = [[InlineKeyboardButton(f"{b[3]}{b[2]} {b[1]}", callback_data=f"ipbrand_{b[1]}")] for b in brands]
    keyboard.append([InlineKeyboardButton(_('btn_cancel', chat_id), callback_data="menu_import")])
    gdisp = Database.get_group_display(context.user_data['ip_group'])
    await query.edit_message_text(f"{gdisp} {context.user_data['ip_group']}\n{_('prompt_select_brand', chat_id)}", reply_markup=InlineKeyboardMarkup(keyboard))
    return IP_BRAND

async def get_ip_brand(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    chat_id = update.effective_chat.id
    context.user_data['ip_brand'] = query.data[7:]
    disp = Database.get_brand_display(context.user_data['ip_brand'])
    await query.edit_message_text(f"{disp} {context.user_data['ip_brand']}\n{_('prompt_enter_name', chat_id)}",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(_('btn_cancel', chat_id), callback_data="menu_import")]]))
    return IP_NAME

async def get_ip_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['conv_state'] = IP_NAME
    chat_id = update.effective_chat.id
    context.user_data['ip_name'] = update.message.text
    await update.message.reply_text(_('prompt_enter_ram', chat_id))
    return IP_RAM

async def get_ip_ram(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['conv_state'] = IP_RAM
    chat_id = update.effective_chat.id
    text = update.message.text.strip()
    context.user_data['ip_ram'] = '' if text.lower() == 'skip' else text
    await update.message.reply_text(_('prompt_enter_rom', chat_id))
    return IP_ROM

async def get_ip_rom(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['conv_state'] = IP_ROM
    chat_id = update.effective_chat.id
    text = update.message.text.strip()
    context.user_data['ip_rom'] = '' if text.lower() == 'skip' else text
    await update.message.reply_text(_('prompt_enter_retail_price', chat_id))
    return IP_PRICE

async def get_ip_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['conv_state'] = IP_PRICE
    chat_id = update.effective_chat.id
    try:
        retail = float(update.message.text)
        if retail <= 0: raise ValueError
    except:
        await update.message.reply_text(_('msg_invalid_price', chat_id))
        return IP_PRICE
    context.user_data['ip_retail'] = retail
    await update.message.reply_text("💲 Enter cost price, or 'skip' to keep existing:")
    return IP_COST

async def get_ip_cost(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['conv_state'] = IP_COST
    chat_id = update.effective_chat.id
    text = update.message.text.strip()
    if text.lower() == 'skip':
        context.user_data.pop('ip_cost', None)
    else:
        try:
            cost = float(text)
            if cost <= 0: raise ValueError
            context.user_data['ip_cost'] = cost
        except:
            await update.message.reply_text(_('msg_invalid_price', chat_id))
            return IP_COST
    await update.message.reply_text("🔤 Enter product code (e.g., AP-IP14) or 'skip':")
    return IP_CODE

async def get_ip_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['conv_state'] = IP_CODE
    chat_id = update.effective_chat.id
    text = update.message.text.strip()
    context.user_data['ip_code'] = '' if text.lower() == 'skip' else text
    group = context.user_data['ip_group']
    brand = context.user_data['ip_brand']
    name = context.user_data['ip_name']
    ram = context.user_data.get('ip_ram', '')
    rom = context.user_data.get('ip_rom', '')
    retail = context.user_data['ip_retail']
    existing = Database.find_item(brand, name, ram, rom)
    if existing:
        spec = f" {ram}/{rom}" if ram or rom else ''
        old_retail = existing[3] or 0
        price_diff = old_retail != retail
        if price_diff:
            keyboard = [
                [InlineKeyboardButton(_('btn_add_stock', chat_id), callback_data="ipdup_stock")],
                [InlineKeyboardButton(_('btn_update_price_stock', chat_id), callback_data="ipdup_upd")],
                [InlineKeyboardButton(_('btn_create_new', chat_id), callback_data="ipdup_new")],
            ]
        else:
            keyboard = [
                [InlineKeyboardButton(_('btn_add_stock', chat_id), callback_data="ipdup_stock")],
                [InlineKeyboardButton(_('btn_create_new', chat_id), callback_data="ipdup_new")],
            ]
        await update.message.reply_text(
            _f('msg_product_exists_staff', chat_id, name=f"{name}{spec}", qty=existing[2],
               old_r=old_retail, new_r=retail),
            reply_markup=InlineKeyboardMarkup(keyboard))
        return IP_DUP_ACTION
    await update.message.reply_text(_('prompt_enter_qty', chat_id))
    return IP_QTY

async def get_ip_qty(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['conv_state'] = IP_QTY
    chat_id = update.effective_chat.id
    try:
        qty = int(update.message.text)
        if qty <= 0:
            await update.message.reply_text(_('msg_invalid_qty', chat_id))
            return IP_QTY
        context.user_data['ip_qty'] = qty
    except:
        await update.message.reply_text(_('msg_invalid_qty', chat_id))
        return IP_QTY
    context.user_data['ip_imeis'] = []
    context.user_data['ip_is_new'] = True
    await update.message.reply_text("📱 Enter IMEI number(s), one per line. Type 'done' to finish, or 'skip' to skip:")
    return IP_IMEI

async def get_ip_dup_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    chat_id = update.effective_chat.id
    if query.data == "ipdup_new":
        context.user_data['ip_create_new'] = True
        await query.edit_message_text(_('prompt_enter_qty', chat_id))
        return IP_QTY
    elif query.data == "ipdup_upd":
        await query.edit_message_text(_('prompt_enter_add_stock_qty', chat_id))
        context.user_data['ip_do_update_price'] = True
        return IP_DUP_QTY
    else:
        await query.edit_message_text(_('prompt_enter_add_stock_qty', chat_id))
        context.user_data['ip_do_update_price'] = False
        return IP_DUP_QTY
    return ConversationHandler.END

async def get_ip_dup_qty(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['conv_state'] = IP_DUP_QTY
    chat_id = update.effective_chat.id
    try:
        qty = int(update.message.text)
        if qty <= 0: raise ValueError
    except:
        await update.message.reply_text(_('msg_invalid_qty', chat_id))
        return IP_DUP_QTY
    context.user_data['ip_qty'] = qty
    context.user_data['ip_is_new'] = False
    context.user_data['ip_imeis'] = []
    await update.message.reply_text("📱 Enter IMEI number(s), one per line. Type 'done' to finish, or 'skip' to skip:")
    return IP_IMEI

async def get_ip_imei(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['conv_state'] = IP_IMEI
    chat_id = update.effective_chat.id
    text = update.message.text.strip()
    if text.lower() in ('skip', 'done'):
        imeis = context.user_data.pop('ip_imeis', [])
        qty = context.user_data.get('ip_qty', 1)
        brand = context.user_data.get('ip_brand')
        name = context.user_data.get('ip_name')
        ram = context.user_data.get('ip_ram', '')
        rom = context.user_data.get('ip_rom', '')
        if context.user_data.get('ip_is_new'):
            await finish_import_product(update.message, context, chat_id, qty)
            if imeis:
                new_id = context.user_data.get('ip_item_id')
                if new_id:
                    Database.save_item_imeis(new_id, imeis)
                    await update.message.reply_text(f"📱 {len(imeis)} IMEI(s) registered.")
        else:
            existing = Database.find_item(brand, name, ram, rom)
            if existing:
                code = context.user_data.get('ip_code', '')
                new_cost = context.user_data.get('ip_cost', existing[4] or 0)
                Database.update_item_quantity(existing[0], qty)
                old_qty = existing[2]
                old_cost = existing[4] or 0
                avg_cost = (old_qty * old_cost + qty * new_cost) / (old_qty + qty)
                if context.user_data.get('ip_do_update_price'):
                    new_retail = context.user_data['ip_retail']
                    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
                    c.execute("UPDATE items SET price=?, cost_price=?, product_code=COALESCE(NULLIF(product_code,''),?) WHERE id=?", (new_retail, avg_cost, code, existing[0]))
                    conn.commit(); conn.close()
                else:
                    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
                    c.execute("UPDATE items SET cost_price=?, product_code=COALESCE(NULLIF(product_code,''),?) WHERE id=?", (avg_cost, code, existing[0]))
                    conn.commit(); conn.close()
                if imeis:
                    Database.save_item_imeis(existing[0], imeis)
                disp = Database.get_brand_display(brand)
                spec = f" {ram}/{rom}" if ram or rom else ''
                code_line = f"\n🔤 Code: {code}" if code else ''
                msg = f"⬆️ {disp} {name}{spec}{code_line}\n+{qty} units (now {existing[2] + qty})\nCost: ${avg_cost:.2f}/unit"
                if context.user_data.get('ip_do_update_price'):
                    msg += f"\nRetail updated to ${context.user_data['ip_retail']:.2f}"
                if imeis:
                    msg += f"\n📱 {len(imeis)} IMEI(s) registered"
                await update.message.reply_text(msg,
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(_('btn_menu', chat_id), callback_data="menu_main")]]))
                await send_import_alert(context, name, disp, qty, f' (now {existing[2] + qty})')
        clear_user_data(context)
        return ConversationHandler.END
    if text.isdigit() and len(text) <= 15:
        imeis = context.user_data.get('ip_imeis', [])
        imeis.append(text)
        context.user_data['ip_imeis'] = imeis
        await update.message.reply_text(f"✅ Added IMEI: {text}\nEnter another IMEI, or type 'done' to finish:")
        return IP_IMEI
    await update.message.reply_text("❌ Invalid IMEI. Must be a 15-digit number. Try again, or type 'skip' to skip:")
    return IP_IMEI

async def finish_import_product(query_or_msg, context, chat_id, qty=0):
    group = context.user_data['ip_group']
    brand = context.user_data['ip_brand']
    name = context.user_data['ip_name']
    ram = context.user_data.get('ip_ram', '')
    rom = context.user_data.get('ip_rom', '')
    retail = context.user_data['ip_retail']
    code = context.user_data.get('ip_code', '')
    new_id = Database.add_item(name, brand, qty, price=retail, group_name=group, ram=ram, rom=rom, product_code=code)
    context.user_data['ip_item_id'] = new_id
    disp = Database.get_brand_display(brand)
    spec = f" {ram}/{rom}" if ram or rom else ''
    code_line = f"\n🔤 Code: {code}" if code else ''
    msg = f"✅ {disp} {name}{spec}{code_line}\n{_('report_retail', chat_id)} ${retail:.2f}\n📊 Stock: {qty}"
    if hasattr(query_or_msg, 'edit_message_text'):
        await query_or_msg.edit_message_text(msg,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(_('btn_menu', chat_id), callback_data="menu_main")]]))
    else:
        await query_or_msg.reply_text(msg,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(_('btn_menu', chat_id), callback_data="menu_main")]]))
    await send_import_alert(context, name, disp, qty, ' (new product)')

async def ip_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await update.message.reply_text(_('msg_cancelled', chat_id)); clear_user_data(context); return ConversationHandler.END

conv_handler_import_product = ConversationHandler(
    entry_points=[CallbackQueryHandler(start_import_product, pattern="^import_product$")],
    states={
        IP_GROUP: [CallbackQueryHandler(get_ip_group, pattern="^ipgroup_")],
        IP_BRAND: [CallbackQueryHandler(get_ip_brand, pattern="^ipbrand_")],
        IP_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_ip_name), CallbackQueryHandler(guard_callback, pattern="^(?!menu_).*$")],
        IP_RAM: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_ip_ram), CallbackQueryHandler(guard_callback, pattern="^(?!menu_).*$")],
        IP_ROM: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_ip_rom), CallbackQueryHandler(guard_callback, pattern="^(?!menu_).*$")],
        IP_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_ip_price), CallbackQueryHandler(guard_callback, pattern="^(?!menu_).*$")],
        IP_COST: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_ip_cost), CallbackQueryHandler(guard_callback, pattern="^(?!menu_).*$")],
        IP_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_ip_code), CallbackQueryHandler(guard_callback, pattern="^(?!menu_).*$")],
        IP_QTY: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_ip_qty), CallbackQueryHandler(guard_callback, pattern="^(?!menu_).*$")],
        IP_DUP_ACTION: [CallbackQueryHandler(get_ip_dup_action, pattern="^ipdup_")],
        IP_DUP_QTY: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_ip_dup_qty), CallbackQueryHandler(guard_callback, pattern="^(?!menu_).*$")],
        IP_IMEI: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_ip_imei), CallbackQueryHandler(guard_callback, pattern="^(?!menu_).*$")],
    },
    fallbacks=[CommandHandler("cancel", ip_cancel), CallbackQueryHandler(cancel_add_callback, pattern="^menu_import$")],
)

# ──────────────────────────────
# REGISTER PRODUCT CODE conversation
# ──────────────────────────────
RC_BRAND, RC_ITEM, RC_CODE = range(54, 57)

async def start_register_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = update.effective_chat.id
    brands = Database.list_brands()
    keyboard = [[InlineKeyboardButton(f"{b[3]}{b[2]} {b[1]}", callback_data=f"rcbrand_{b[1]}")] for b in brands]
    keyboard.append([InlineKeyboardButton(_('btn_cancel', chat_id), callback_data="menu_inventory")])
    await query.edit_message_text(_('prompt_select_brand', chat_id), reply_markup=InlineKeyboardMarkup(keyboard))
    return RC_BRAND

async def get_rc_brand(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = update.effective_chat.id
    brand = query.data[8:]
    context.user_data['rc_brand'] = brand
    items = Database.list_items_by_brand(brand)
    if not items:
        await query.edit_message_text(_f('msg_no_items_brand', chat_id, brand=brand),
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(_('btn_cancel', chat_id), callback_data="menu_inventory")]]))
        return ConversationHandler.END
    keyboard = [[InlineKeyboardButton(f"{i[1]} {f'({i[5]}/{i[6]})' if i[5] or i[6] else ''}", callback_data=f"rcitem_{i[0]}")] for i in items]
    keyboard.append([InlineKeyboardButton(_('btn_cancel', chat_id), callback_data="menu_inventory")])
    await query.edit_message_text(f"{Database.get_brand_display(brand)} {brand}\n{_('prompt_select_item', chat_id)}", reply_markup=InlineKeyboardMarkup(keyboard))
    return RC_ITEM

async def get_rc_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = update.effective_chat.id
    item_id = int(query.data[7:])
    item = Database.get_item(item_id)
    if not item:
        await query.edit_message_text(_('msg_item_not_found', chat_id),
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(_('btn_cancel', chat_id), callback_data="menu_inventory")]]))
        return ConversationHandler.END
    context.user_data['rc_item_id'] = item_id
    context.user_data['rc_item_name'] = item[1]
    context.user_data['rc_current_code'] = item[9] or ''
    spec = f" ({item[6]}/{item[7]})" if item[6] or item[7] else ''
    current = f"\nCurrent code: {item[9]}" if item[9] else ''
    await query.edit_message_text(f"📦 {item[1]}{spec}{current}\n🔤 Enter new product code (or 'skip' to keep current):")
    return RC_CODE

async def get_rc_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['conv_state'] = RC_CODE
    chat_id = update.effective_chat.id
    text = update.message.text.strip()
    if text.lower() == 'skip':
        await update.message.reply_text("ℹ️ Code unchanged.")
        clear_user_data(context)
        return ConversationHandler.END
    item_id = context.user_data['rc_item_id']
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("UPDATE items SET product_code=? WHERE id=?", (text, item_id))
    conn.commit(); conn.close()
    name = context.user_data['rc_item_name']
    await update.message.reply_text(f"✅ Code registered for {name}: {text}",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(_('btn_menu', chat_id), callback_data="menu_main")]]))
    clear_user_data(context)
    return ConversationHandler.END

async def rc_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await update.message.reply_text(_('msg_cancelled', chat_id)); clear_user_data(context); return ConversationHandler.END

conv_handler_register_code = ConversationHandler(
    entry_points=[CallbackQueryHandler(start_register_code, pattern="^inv_register_code$")],
    states={
        RC_BRAND: [CallbackQueryHandler(get_rc_brand, pattern="^rcbrand_")],
        RC_ITEM: [CallbackQueryHandler(get_rc_item, pattern="^rcitem_")],
        RC_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_rc_code), CallbackQueryHandler(guard_callback, pattern="^(?!menu_).*$")],
    },
    fallbacks=[CommandHandler("cancel", rc_cancel), CallbackQueryHandler(cancel_add_callback, pattern="^menu_inventory$")],
)

# ──────────────────────────────
# IMPORT CUSTOMER conversation
# ──────────────────────────────
IC_NAME, IC_LOC, IC_PH1, IC_MORE2, IC_PH2, IC_MORE3, IC_PH3 = range(32, 39)

async def start_import_customer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    chat_id = update.effective_chat.id
    await query.edit_message_text(_('prompt_enter_cust_name', chat_id),
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(_('btn_cancel', chat_id), callback_data="menu_import")]]))
    return IC_NAME

async def get_ic_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['conv_state'] = IC_NAME
    chat_id = update.effective_chat.id
    context.user_data['ic_name'] = update.message.text
    await update.message.reply_text(_('prompt_enter_location', chat_id))
    return IC_LOC

async def get_ic_loc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['conv_state'] = IC_LOC
    chat_id = update.effective_chat.id
    text = update.message.text
    context.user_data['ic_loc'] = None if text.lower() == 'skip' else text
    await update.message.reply_text(_('prompt_enter_phone', chat_id))
    return IC_PH1

async def get_ic_ph1(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['conv_state'] = IC_PH1
    chat_id = update.effective_chat.id
    text = update.message.text
    context.user_data['ic_ph1'] = None if text.lower() == 'skip' else text
    keyboard = [
        [InlineKeyboardButton(_('btn_more', chat_id), callback_data="ic_more2_yes")],
        [InlineKeyboardButton(_('btn_no', chat_id), callback_data="ic_more2_no")],
    ]
    await update.message.reply_text(_('prompt_ask_more_phone', chat_id), reply_markup=InlineKeyboardMarkup(keyboard))
    return IC_MORE2

async def get_ic_more2(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    chat_id = update.effective_chat.id
    if query.data == "ic_more2_no":
        return await finish_import_customer(query, context, chat_id)
    await query.edit_message_text(_('prompt_enter_phone2', chat_id))
    return IC_PH2

async def get_ic_ph2(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['conv_state'] = IC_PH2
    chat_id = update.effective_chat.id
    text = update.message.text
    context.user_data['ic_ph2'] = None if text.lower() == 'skip' else text
    keyboard = [
        [InlineKeyboardButton(_('btn_more', chat_id), callback_data="ic_more3_yes")],
        [InlineKeyboardButton(_('btn_no', chat_id), callback_data="ic_more3_no")],
    ]
    await update.message.reply_text(_('prompt_ask_more_phone', chat_id), reply_markup=InlineKeyboardMarkup(keyboard))
    return IC_MORE3

async def get_ic_more3(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    chat_id = update.effective_chat.id
    if query.data == "ic_more3_no":
        return await finish_import_customer(query, context, chat_id)
    await query.edit_message_text(_('prompt_enter_phone3', chat_id))
    return IC_PH3

async def get_ic_ph3(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['conv_state'] = IC_PH3
    chat_id = update.effective_chat.id
    text = update.message.text
    context.user_data['ic_ph3'] = None if text.lower() == 'skip' else text
    return await finish_import_customer(update.message, context, chat_id)

async def finish_import_customer(query_or_msg, context, chat_id):
    name = context.user_data['ic_name']
    loc = context.user_data.get('ic_loc')
    ph1 = context.user_data.get('ic_ph1')
    ph2 = context.user_data.get('ic_ph2')
    ph3 = context.user_data.get('ic_ph3')
    Database.add_customer(name, loc, ph1, ph2, ph3)
    msg = f"✅ {name}\n{_('profile_location', chat_id)} {loc or _('report_none', chat_id)}\n{_('profile_phone', chat_id)} {' / '.join(filter(None, [ph1, ph2, ph3])) or _('report_none', chat_id)}"
    if hasattr(query_or_msg, 'edit_message_text'):
        await query_or_msg.edit_message_text(msg, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(_('btn_menu', chat_id), callback_data="menu_main")]]))
    else:
        await query_or_msg.reply_text(msg, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(_('btn_menu', chat_id), callback_data="menu_main")]]))
    clear_user_data(context)
    return ConversationHandler.END

async def ic_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await update.message.reply_text(_('msg_cancelled', chat_id)); clear_user_data(context); return ConversationHandler.END

conv_handler_import_customer = ConversationHandler(
    entry_points=[CallbackQueryHandler(start_import_customer, pattern="^import_customer$")],
    states={
        IC_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_ic_name), CallbackQueryHandler(guard_callback, pattern="^(?!menu_).*$")],
        IC_LOC: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_ic_loc), CallbackQueryHandler(guard_callback, pattern="^(?!menu_).*$")],
        IC_PH1: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_ic_ph1), CallbackQueryHandler(guard_callback, pattern="^(?!menu_).*$")],
        IC_MORE2: [CallbackQueryHandler(get_ic_more2, pattern="^ic_more2_")],
        IC_PH2: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_ic_ph2), CallbackQueryHandler(guard_callback, pattern="^(?!menu_).*$")],
        IC_MORE3: [CallbackQueryHandler(get_ic_more3, pattern="^ic_more3_")],
        IC_PH3: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_ic_ph3), CallbackQueryHandler(guard_callback, pattern="^(?!menu_).*$")],
    },
    fallbacks=[CommandHandler("cancel", ic_cancel), CallbackQueryHandler(cancel_add_callback, pattern="^menu_import$")],
)

# ──────────────────────────────
# IMPORT STAFF conversation
# ──────────────────────────────
IS_NAME, IS_ROLE, IS_PIN = range(39, 42)

async def start_import_staff(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    chat_id = update.effective_chat.id
    await query.edit_message_text(_('prompt_enter_staff_name', chat_id),
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(_('btn_cancel', chat_id), callback_data="menu_import")]]))
    return IS_NAME

async def get_is_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['conv_state'] = IS_NAME
    chat_id = update.effective_chat.id
    context.user_data['is_name'] = update.message.text
    keyboard = [
        [InlineKeyboardButton("👑 Admin", callback_data="isrole_admin")],
        [InlineKeyboardButton("📋 Manager", callback_data="isrole_manager")],
        [InlineKeyboardButton("👤 Staff", callback_data="isrole_staff")],
    ]
    await update.message.reply_text(_('prompt_enter_role', chat_id), reply_markup=InlineKeyboardMarkup(keyboard))
    return IS_ROLE

async def get_is_role(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    chat_id = update.effective_chat.id
    context.user_data['is_role'] = query.data[7:]
    await query.edit_message_text(_('prompt_enter_pin', chat_id))
    return IS_PIN

async def get_is_pin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['conv_state'] = IS_PIN
    chat_id = update.effective_chat.id
    pin = update.message.text
    if not pin.isdigit() or len(pin) < 4:
        await update.message.reply_text(_('prompt_enter_pin', chat_id))
        return IS_PIN
    context.user_data['is_pin'] = pin
    name = context.user_data['is_name']
    role = context.user_data['is_role']
    Database.add_staff(name, role, pin)
    await update.message.reply_text(f"✅ {name} ({role})",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(_('btn_menu', chat_id), callback_data="menu_main")]]))
    clear_user_data(context)
    return ConversationHandler.END

async def is_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await update.message.reply_text(_('msg_cancelled', chat_id)); clear_user_data(context); return ConversationHandler.END

conv_handler_staff = ConversationHandler(
    entry_points=[CallbackQueryHandler(start_import_staff, pattern="^import_staff$")],
    states={
        IS_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_is_name), CallbackQueryHandler(guard_callback, pattern="^(?!menu_).*$")],
        IS_ROLE: [CallbackQueryHandler(get_is_role, pattern="^isrole_")],
        IS_PIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_is_pin), CallbackQueryHandler(guard_callback, pattern="^(?!menu_).*$")],
    },
    fallbacks=[CommandHandler("cancel", is_cancel), CallbackQueryHandler(cancel_add_callback, pattern="^menu_import$")],
)

# ──────────────────────────────
# RECORD DEBT conversation
# ──────────────────────────────
DEBT_CUST, DEBT_DATE, DEBT_DATE_INPUT, DEBT_AMT, DEBT_NOTE = range(42, 47)

async def start_debt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    chat_id = update.effective_chat.id
    custs = Database.list_customers()
    if not custs:
        await query.edit_message_text(_('msg_no_customers', chat_id),
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(_('btn_back', chat_id), callback_data="menu_customers")]]))
        return ConversationHandler.END
    keyboard = [[InlineKeyboardButton(f"{c[1]} (${c[5]:.2f})", callback_data=f"debtcust_{c[0]}")] for c in custs]
    keyboard.append([InlineKeyboardButton(_('btn_cancel', chat_id), callback_data="menu_customers")])
    await query.edit_message_text(_('prompt_select_customer', chat_id), reply_markup=InlineKeyboardMarkup(keyboard))
    return DEBT_CUST

async def get_debt_cust(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    chat_id = update.effective_chat.id
    context.user_data['debt_cust_id'] = int(query.data[9:])
    cust = Database.get_customer(context.user_data['debt_cust_id'])
    keyboard = [
        [InlineKeyboardButton(_('btn_today', chat_id), callback_data="debt_date_today")],
        [InlineKeyboardButton(_('btn_fill_date', chat_id), callback_data="debt_date_fill")],
    ]
    await query.edit_message_text(f"{cust[1]}\n{_('prompt_select_date', chat_id)}", reply_markup=InlineKeyboardMarkup(keyboard))
    return DEBT_DATE

async def get_debt_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    chat_id = update.effective_chat.id
    if query.data == "debt_date_today":
        context.user_data['debt_date'] = datetime.now().strftime('%Y-%m-%d')
        await query.edit_message_text(_('prompt_enter_debt_amt', chat_id))
        return DEBT_AMT
    else:
        await query.edit_message_text(_('prompt_enter_date', chat_id))
        return DEBT_DATE_INPUT

async def get_debt_date_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['conv_state'] = DEBT_DATE_INPUT
    chat_id = update.effective_chat.id
    text = update.message.text.strip()
    try:
        datetime.strptime(text, '%Y-%m-%d')
        context.user_data['debt_date'] = text
    except:
        await update.message.reply_text(_('msg_invalid_date', chat_id))
        return DEBT_DATE_INPUT
    await update.message.reply_text(_('prompt_enter_debt_amt', chat_id))
    return DEBT_AMT

async def get_debt_amt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['conv_state'] = DEBT_AMT
    chat_id = update.effective_chat.id
    try:
        context.user_data['debt_amt'] = float(update.message.text)
        if context.user_data['debt_amt'] <= 0: raise ValueError
    except:
        await update.message.reply_text(_('msg_invalid_number', chat_id)); return DEBT_AMT
    keyboard = [
        [InlineKeyboardButton(_('btn_no', chat_id), callback_data="debt_note_no")],
    ]
    await update.message.reply_text(_('prompt_enter_debt_note', chat_id), reply_markup=InlineKeyboardMarkup(keyboard))
    return DEBT_NOTE

async def get_debt_note(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['conv_state'] = DEBT_NOTE
    chat_id = update.effective_chat.id
    if hasattr(update, 'callback_query') and update.callback_query:
        query = update.callback_query; await query.answer()
        note = ''
        msg_obj = query
    else:
        text = update.message.text.strip()
        note = text
        msg_obj = update.message
    cid = context.user_data['debt_cust_id']
    amt = context.user_data['debt_amt']
    debt_date = context.user_data['debt_date']
    Database.record_debt_with_date(cid, amt, note, debt_date)
    cust = Database.get_customer(cid)
    bal = Database.get_customer_balance(cid)
    report = (
        f"✅ {_('debt_recorded', chat_id)}\n"
        f"{'─'*20}\n"
        f"{cust[1]}\n"
        f"{_('report_amount', chat_id)} ${amt:.2f}\n"
        f"{_('report_date', chat_id)} {debt_date}\n"
        f"{_('report_note', chat_id)} {note or '—'}\n"
        f"{'─'*20}\n"
        f"{_('profile_balance', chat_id)} ${bal:.2f}"
    )
    await msg_obj.reply_text(report,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(_('btn_menu', chat_id), callback_data="menu_main")]]))
    clear_user_data(context)
    return ConversationHandler.END

async def debt_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await update.message.reply_text(_('msg_cancelled', chat_id)); clear_user_data(context); return ConversationHandler.END

conv_handler_debt = ConversationHandler(
    entry_points=[CallbackQueryHandler(start_debt, pattern="^cust_debt$")],
    states={
        DEBT_CUST: [CallbackQueryHandler(get_debt_cust, pattern="^debtcust_")],
        DEBT_DATE: [CallbackQueryHandler(get_debt_date, pattern="^debt_date_")],
        DEBT_DATE_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_debt_date_input), CallbackQueryHandler(guard_callback, pattern="^(?!menu_).*$")],
        DEBT_AMT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_debt_amt), CallbackQueryHandler(guard_callback, pattern="^(?!menu_).*$")],
        DEBT_NOTE: [CallbackQueryHandler(get_debt_note, pattern="^debt_note_no$"), MessageHandler(filters.TEXT & ~filters.COMMAND, get_debt_note), CallbackQueryHandler(guard_callback, pattern="^(?!menu_).*$")],
    },
    fallbacks=[CommandHandler("cancel", debt_cancel), CallbackQueryHandler(cancel_add_callback, pattern="^menu_customers$")],
)

# ──────────────────────────────
# RECORD PAYMENT conversation
# ──────────────────────────────
PAY_CUST, PAY_BILL, PAY_AMT = range(47, 50)

async def start_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    chat_id = update.effective_chat.id
    custs = Database.list_customers()
    if not custs:
        await query.edit_message_text(_('msg_no_customers', chat_id), reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(_('btn_back', chat_id), callback_data="menu_customers")]]))
        return ConversationHandler.END
    keyboard = [[InlineKeyboardButton(f"{c[1]} (${c[5]:.2f})", callback_data=f"paycust_{c[0]}")] for c in custs]
    keyboard.append([InlineKeyboardButton(_('btn_cancel', chat_id), callback_data="menu_customers")])
    await query.edit_message_text(_('prompt_select_customer', chat_id), reply_markup=InlineKeyboardMarkup(keyboard))
    return PAY_CUST

async def get_pay_cust(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    chat_id = update.effective_chat.id
    cid = int(query.data[8:])
    context.user_data['pay_cust_id'] = cid
    cust = Database.get_customer(cid)
    bills = Database.get_customer_unpaid_schedules(cid)
    if not bills:
        await query.edit_message_text(f"{cust[1]}\n{_('msg_no_unpaid_bills', chat_id)}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(_('btn_back', chat_id), callback_data="menu_customers")]]))
        return ConversationHandler.END
    keyboard = [[InlineKeyboardButton(f"${b[1]:.0f} - Due: {b[2]} {b[3] or ''}", callback_data=f"paybill_{b[0]}")] for b in bills]
    keyboard.append([InlineKeyboardButton(_('btn_cancel', chat_id), callback_data="menu_customers")])
    await query.edit_message_text(f"{cust[1]}\n{_('prompt_select_bill', chat_id)}", reply_markup=InlineKeyboardMarkup(keyboard))
    return PAY_BILL

async def get_pay_bill(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    chat_id = update.effective_chat.id
    schedule_id = int(query.data[8:])
    context.user_data['pay_schedule_id'] = schedule_id
    await query.edit_message_text(_('prompt_enter_pay_amt', chat_id))
    return PAY_AMT

async def get_pay_amt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['conv_state'] = PAY_AMT
    chat_id = update.effective_chat.id
    try:
        amt = float(update.message.text)
        if amt <= 0: raise ValueError
    except:
        await update.message.reply_text(_('msg_invalid_number', chat_id)); return PAY_AMT
    cid = context.user_data['pay_cust_id']
    schedule_id = context.user_data['pay_schedule_id']
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute("SELECT amount FROM payment_schedules WHERE id=?", (schedule_id,)).fetchone()
    conn.close()
    total = row[0] if row else 0
    amt = min(amt, total)
    Database.pay_schedule(schedule_id, amt)
    Database.record_transaction(cid, -amt, f"Payment for bill #{schedule_id}")
    cust = Database.get_customer(cid)
    bal = Database.get_customer_balance(cid)
    await update.message.reply_text(
        f"✅ {cust[1]}\n${amt:.2f} paid\n{_('profile_balance', chat_id)} ${bal:.2f}",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(_('btn_menu', chat_id), callback_data="menu_main")]]))
    clear_user_data(context)
    return ConversationHandler.END

async def pay_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await update.message.reply_text(_('msg_cancelled', chat_id)); clear_user_data(context); return ConversationHandler.END

conv_handler_payment = ConversationHandler(
    entry_points=[CallbackQueryHandler(start_payment, pattern="^cust_payment$")],
    states={
        PAY_CUST: [CallbackQueryHandler(get_pay_cust, pattern="^paycust_")],
        PAY_BILL: [CallbackQueryHandler(get_pay_bill, pattern="^paybill_")],
        PAY_AMT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_pay_amt), CallbackQueryHandler(guard_callback, pattern="^(?!menu_).*$")],
    },
    fallbacks=[CommandHandler("cancel", pay_cancel), CallbackQueryHandler(cancel_add_callback, pattern="^menu_customers$")],
)

# ──────────────────────────────
# CHECK BALANCE conversation
# ──────────────────────────────
BAL_CUST = 49

async def start_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    chat_id = update.effective_chat.id
    custs = Database.list_customers()
    if not custs:
        await query.edit_message_text(_('msg_no_customers', chat_id), reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(_('btn_back', chat_id), callback_data="menu_customers")]]))
        return ConversationHandler.END
    keyboard = [[InlineKeyboardButton(f"{c[1]} (${c[5]:.2f})", callback_data=f"balcust_{c[0]}")] for c in custs]
    keyboard.append([InlineKeyboardButton(_('btn_cancel', chat_id), callback_data="menu_customers")])
    await query.edit_message_text(_('prompt_select_customer', chat_id), reply_markup=InlineKeyboardMarkup(keyboard))
    return BAL_CUST

async def get_bal_cust(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    chat_id = update.effective_chat.id
    cid = int(query.data[8:])
    cust = Database.get_customer(cid)
    bal = cust[6]
    phones = ' / '.join(filter(None, [cust[3], cust[4], cust[5]]))
    keyboard = [
        [InlineKeyboardButton(_('profile_inline_history', chat_id), callback_data=f"histcust_{cid}")],
        [InlineKeyboardButton(_('profile_inline_debt', chat_id), callback_data="cust_debt")],
        [InlineKeyboardButton(_('profile_inline_payment', chat_id), callback_data="cust_payment")],
        [InlineKeyboardButton(_('btn_back', chat_id), callback_data="menu_customers")],
    ]
    msg = f"👤 *{escape_md(cust[1])}*\n{_('profile_location', chat_id)} {escape_md(cust[2] or _('report_none', chat_id))}\n{_('profile_phone', chat_id)} {escape_md(phones or _('report_none', chat_id))}\n{_('profile_balance', chat_id)} ${bal:.2f}"
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    clear_user_data(context)
    return ConversationHandler.END

async def bal_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await update.message.reply_text(_('msg_cancelled', chat_id)); clear_user_data(context); return ConversationHandler.END

conv_handler_balance = ConversationHandler(
    entry_points=[CallbackQueryHandler(start_balance, pattern="^cust_balance$")],
    states={
        BAL_CUST: [CallbackQueryHandler(get_bal_cust, pattern="^balcust_")],
    },
    fallbacks=[CommandHandler("cancel", bal_cancel), CallbackQueryHandler(cancel_add_callback, pattern="^menu_customers$")],
)

# ──────────────────────────────
# TRANSACTION HISTORY conversation
# ──────────────────────────────
HIST_CUST = 50

async def start_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    chat_id = update.effective_chat.id
    custs = Database.list_customers()
    if not custs:
        await query.edit_message_text(_('msg_no_customers', chat_id), reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(_('btn_back', chat_id), callback_data="menu_customers")]]))
        return ConversationHandler.END
    keyboard = [[InlineKeyboardButton(f"{c[1]} (${c[5]:.2f})", callback_data=f"histcust_{c[0]}")] for c in custs]
    keyboard.append([InlineKeyboardButton(_('btn_cancel', chat_id), callback_data="menu_customers")])
    await query.edit_message_text(_('prompt_select_customer', chat_id), reply_markup=InlineKeyboardMarkup(keyboard))
    return HIST_CUST

async def get_hist_cust(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    chat_id = update.effective_chat.id
    cid = int(query.data[9:])
    txns = Database.get_customer_transactions(cid)
    if not txns:
        await query.edit_message_text(_('msg_no_transactions', chat_id),
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(_('btn_back', chat_id), callback_data="menu_customers")]]))
        return ConversationHandler.END
    resp = f"📖 *History:*\n"
    for t in txns:
        tp = "🔴 DEBT" if t[2] > 0 else "🟢 PAYMENT"
        resp += f"{t[1][:10]} {tp} ${abs(t[2]):.2f}\n{escape_md(t[3]) or ''}\n"
    await query.edit_message_text(resp, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(_('btn_back', chat_id), callback_data="menu_customers")]]), parse_mode='Markdown')
    clear_user_data(context)
    return ConversationHandler.END

async def hist_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await update.message.reply_text(_('msg_cancelled', chat_id)); clear_user_data(context); return ConversationHandler.END

conv_handler_history = ConversationHandler(
    entry_points=[CallbackQueryHandler(start_history, pattern="^cust_history$")],
    states={
        HIST_CUST: [CallbackQueryHandler(get_hist_cust, pattern="^histcust_")],
    },
    fallbacks=[CommandHandler("cancel", hist_cancel), CallbackQueryHandler(cancel_add_callback, pattern="^menu_customers$")],
)

# ──────────────────────────────
# PAYMENT REPORT (no conversation, just display)
# ──────────────────────────────
async def payment_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    chat_id = update.effective_chat.id
    rows = Database.get_overdue_report()
    paid = Database.get_paid_report()
    if not rows and not paid:
        await query.edit_message_text(_('msg_no_schedules', chat_id),
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(_('btn_back', chat_id), callback_data="menu_customers")]]))
        return
    today = datetime.now().strftime('%Y-%m-%d')
    overdue = [r for r in rows if r[4] < today and r[5] == 'pending']
    upcoming = [r for r in rows if r[4] >= today and r[5] == 'pending']
    resp = _('pay_report_title', chat_id) + "\n"
    if overdue:
        resp += "\n" + _('pay_overdue', chat_id) + "\n"
        for r in overdue[:10]:
            days = (datetime.now() - datetime.strptime(r[4], '%Y-%m-%d')).days
            resp += f"  {escape_md(r[2])} ${r[3]:.2f} ({_f('pay_days_overdue', chat_id, days=days)}, {_('pay_due', chat_id)} {r[4]})\n"
    if upcoming:
        resp += "\n" + _('pay_upcoming', chat_id) + "\n"
        for r in upcoming[:10]:
            days = (datetime.strptime(r[4], '%Y-%m-%d') - datetime.now()).days
            resp += f"  {escape_md(r[2])} ${r[3]:.2f} ({_('pay_due', chat_id)} {days}d, {r[4]})\n"
    if paid:
        resp += "\n" + _('pay_paid', chat_id) + "\n"
        for r in paid[:5]:
            resp += f"  {escape_md(r[2])} ${r[3]:.2f} ({_('pay_status_done', chat_id)})\n"
    await query.edit_message_text(resp, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(_('btn_back', chat_id), callback_data="menu_customers")]]), parse_mode='Markdown')

# ──────────────────────────────
# CUSTOMER BUY RECORD conversation
# ──────────────────────────────
CSR_CUST, CSR_DATE, CSR_DATE_INPUT, CSR_GROUP, CSR_BRAND, CSR_ITEM, CSR_QTY, CSR_PRICE, CSR_MORE, CSR_NOTE = range(51, 61)

async def start_csr(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    chat_id = update.effective_chat.id
    custs = Database.list_customers()
    if not custs:
        await query.edit_message_text(_('msg_no_customers', chat_id),
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(_('btn_back', chat_id), callback_data="menu_customers")]]))
        return ConversationHandler.END
    keyboard = [[InlineKeyboardButton(f"{c[1]} (${c[5]:.2f})", callback_data=f"csrcust_{c[0]}")] for c in custs]
    keyboard.append([InlineKeyboardButton(_('btn_cancel', chat_id), callback_data="menu_customers")])
    await query.edit_message_text(_('prompt_select_customer', chat_id), reply_markup=InlineKeyboardMarkup(keyboard))
    return CSR_CUST

async def get_csr_cust(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    chat_id = update.effective_chat.id
    context.user_data['csr_cust_id'] = int(query.data[8:])
    context.user_data['csr_items'] = []
    cust = Database.get_customer(context.user_data['csr_cust_id'])
    keyboard = [
        [InlineKeyboardButton(_('btn_today', chat_id), callback_data="csr_date_today")],
        [InlineKeyboardButton(_('btn_fill_date', chat_id), callback_data="csr_date_fill")],
        [InlineKeyboardButton(_('btn_cancel', chat_id), callback_data="menu_customers")],
    ]
    await query.edit_message_text(f"{cust[1]}\n{_('prompt_select_date', chat_id)}", reply_markup=InlineKeyboardMarkup(keyboard))
    return CSR_DATE

async def get_csr_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    chat_id = update.effective_chat.id
    if query.data == "csr_date_today":
        context.user_data['csr_date'] = datetime.now().strftime('%Y-%m-%d')
    else:
        await query.edit_message_text(_('prompt_enter_date', chat_id))
        return CSR_DATE_INPUT
    groups = Database.list_groups()
    keyboard = [[InlineKeyboardButton(f"{g[3]}{g[2]} {g[1]}", callback_data=f"csrgroup_{g[1]}")] for g in groups]
    keyboard.append([InlineKeyboardButton(_('btn_done', chat_id), callback_data="csr_done")])
    await context.bot.send_message(chat_id, _('prompt_select_group', chat_id), reply_markup=InlineKeyboardMarkup(keyboard))
    return CSR_GROUP

async def get_csr_date_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['conv_state'] = CSR_DATE_INPUT
    chat_id = update.effective_chat.id
    text = update.message.text.strip()
    try:
        datetime.strptime(text, '%Y-%m-%d')
        context.user_data['csr_date'] = text
    except:
        await update.message.reply_text(_('msg_invalid_date', chat_id))
        return CSR_DATE_INPUT
    groups = Database.list_groups()
    keyboard = [[InlineKeyboardButton(f"{g[3]}{g[2]} {g[1]}", callback_data=f"csrgroup_{g[1]}")] for g in groups]
    keyboard.append([InlineKeyboardButton(_('btn_done', chat_id), callback_data="csr_done")])
    await update.message.reply_text(_('prompt_select_group', chat_id), reply_markup=InlineKeyboardMarkup(keyboard))
    return CSR_GROUP

async def get_csr_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    chat_id = update.effective_chat.id
    group = query.data[9:]
    context.user_data['csr_group'] = group
    brands = Database.list_brands()
    keyboard = [[InlineKeyboardButton(f"{b[3]}{b[2]} {b[1]}", callback_data=f"csrbrand_{b[1]}")] for b in brands]
    keyboard.append([InlineKeyboardButton(_('btn_cancel', chat_id), callback_data="menu_customers")])
    await query.edit_message_text(_('prompt_select_brand', chat_id), reply_markup=InlineKeyboardMarkup(keyboard))
    return CSR_BRAND

async def get_csr_brand(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    chat_id = update.effective_chat.id
    brand = query.data[9:]
    context.user_data['csr_brand'] = brand
    items = Database.list_items_by_brand(brand)
    if not items:
        await query.edit_message_text(_f('msg_no_items_brand', chat_id, brand=brand),
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(_('btn_back', chat_id), callback_data="menu_customers")]]))
        return ConversationHandler.END
    keyboard = [[InlineKeyboardButton(f"{i[1]} {f'({i[5]}/{i[6]})' if i[5] or i[6] else ''} (${i[3]}) Stock:{i[2]}", callback_data=f"csritem_{i[0]}")] for i in items]
    keyboard.append([InlineKeyboardButton(_('btn_cancel', chat_id), callback_data="menu_customers")])
    await query.edit_message_text(f"{Database.get_brand_display(brand)} {brand}\n{_('prompt_select_item', chat_id)}", reply_markup=InlineKeyboardMarkup(keyboard))
    return CSR_ITEM

async def get_csr_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    chat_id = update.effective_chat.id
    item_id = int(query.data[8:])
    context.user_data['csr_item_id'] = item_id
    item = Database.get_item(item_id)
    await query.edit_message_text(f"{item[1]}\n{_('prompt_enter_qty', chat_id)}")
    return CSR_QTY

async def get_csr_qty(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['conv_state'] = CSR_QTY
    chat_id = update.effective_chat.id
    try:
        qty = int(update.message.text)
        if qty < 1: raise ValueError
        context.user_data['csr_item_qty'] = qty
    except:
        await update.message.reply_text(_('msg_invalid_qty', chat_id))
        return CSR_QTY
    await update.message.reply_text(_('prompt_enter_price_paid', chat_id))
    return CSR_PRICE

async def get_csr_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['conv_state'] = CSR_PRICE
    chat_id = update.effective_chat.id
    try:
        price = float(update.message.text)
        if price <= 0: raise ValueError
        context.user_data['csr_item_price'] = price
    except:
        await update.message.reply_text(_('msg_invalid_price', chat_id))
        return CSR_PRICE
    items = context.user_data['csr_items']
    items.append((context.user_data['csr_item_id'], context.user_data['csr_item_qty'], price))
    context.user_data['csr_items'] = items
    keyboard = [
        [InlineKeyboardButton(_('btn_yes', chat_id), callback_data="csr_more_yes")],
        [InlineKeyboardButton(_('btn_no', chat_id), callback_data="csr_more_no")],
    ]
    await update.message.reply_text(_('prompt_add_more_items', chat_id), reply_markup=InlineKeyboardMarkup(keyboard))
    return CSR_MORE

async def get_csr_more(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    chat_id = update.effective_chat.id
    if query.data == "csr_more_yes":
        groups = Database.list_groups()
        keyboard = [[InlineKeyboardButton(f"{g[3]}{g[2]} {g[1]}", callback_data=f"csrgroup_{g[1]}")] for g in groups]
        keyboard.append([InlineKeyboardButton(_('btn_done', chat_id), callback_data="csr_done")])
        await query.edit_message_text(_('prompt_select_group', chat_id), reply_markup=InlineKeyboardMarkup(keyboard))
        return CSR_GROUP
    else:
        await query.edit_message_text(_('prompt_enter_csr_note', chat_id))
        return CSR_NOTE

async def get_csr_note(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['conv_state'] = CSR_NOTE
    chat_id = update.effective_chat.id
    if hasattr(update, 'callback_query') and update.callback_query:
        query = update.callback_query; await query.answer()
        note = ''
        msg_obj = query
    else:
        note = update.message.text.strip()
        msg_obj = update.message
    cid = context.user_data['csr_cust_id']
    items = context.user_data['csr_items']
    date = context.user_data['csr_date']
    failures = Database.record_customer_sale(cid, items, note, date)
    cust = Database.get_customer(cid)
    total = sum(qty * price for item_id, qty, price in items if item_id not in failures)
    report = f"✅ {_('csr_completed', chat_id)}\n{'─'*20}\n{cust[1]}\n{_('report_date', chat_id)} {date}\n"
    for item_id, qty, price in items:
        if item_id in failures:
            report += f"  ⚠️ Item #{item_id} skipped — insufficient stock\n"
            continue
        item = Database.get_item(item_id)
        report += f"  {item[1]} x{qty} = ${price:.2f}\n"
    report += f"{'─'*20}\n{_('report_total', chat_id)} ${total:.2f}\n{_('report_note', chat_id)} {note or '—'}\n{'─'*20}"
    await msg_obj.reply_text(report,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(_('btn_menu', chat_id), callback_data="menu_main")]]))
    clear_user_data(context)
    return ConversationHandler.END

async def csr_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await update.message.reply_text(_('msg_cancelled', chat_id)); clear_user_data(context); return ConversationHandler.END

async def csr_done_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    chat_id = update.effective_chat.id
    if context.user_data.get('csr_items'):
        await query.edit_message_text(_('prompt_enter_csr_note', chat_id))
        return CSR_NOTE
    else:
        await query.edit_message_text(_('msg_csr_no_items', chat_id),
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(_('btn_menu', chat_id), callback_data="menu_main")]]))
        clear_user_data(context)
        return ConversationHandler.END

conv_handler_csr = ConversationHandler(
    entry_points=[CallbackQueryHandler(start_csr, pattern="^cust_buy_record$")],
    states={
        CSR_CUST: [CallbackQueryHandler(get_csr_cust, pattern="^csrcust_")],
        CSR_DATE: [CallbackQueryHandler(get_csr_date, pattern="^csr_date_")],
        CSR_DATE_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_csr_date_input), CallbackQueryHandler(guard_callback, pattern="^(?!menu_).*$")],
        CSR_GROUP: [CallbackQueryHandler(get_csr_group, pattern="^csrgroup_"), CallbackQueryHandler(csr_done_callback, pattern="^csr_done$")],
        CSR_BRAND: [CallbackQueryHandler(get_csr_brand, pattern="^csrbrand_")],
        CSR_ITEM: [CallbackQueryHandler(get_csr_item, pattern="^csritem_")],
        CSR_QTY: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_csr_qty), CallbackQueryHandler(guard_callback, pattern="^(?!menu_).*$")],
        CSR_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_csr_price), CallbackQueryHandler(guard_callback, pattern="^(?!menu_).*$")],
        CSR_MORE: [CallbackQueryHandler(get_csr_more, pattern="^csr_more_")],
        CSR_NOTE: [CallbackQueryHandler(get_csr_note, pattern="^csr_note_no$"), MessageHandler(filters.TEXT & ~filters.COMMAND, get_csr_note), CallbackQueryHandler(guard_callback, pattern="^(?!menu_).*$")],
    },
    fallbacks=[CommandHandler("cancel", csr_cancel), CallbackQueryHandler(cancel_add_callback, pattern="^menu_customers$")],
)



async def handle_unlock_pin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('awaiting_unlock'):
        return
    chat_id = update.effective_chat.id
    pin = update.message.text.strip()
    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute("SELECT value FROM bot_config WHERE key='bot_unlock_pin'")
    row = cur.fetchone()
    if row is None:
        cur = conn.execute("SELECT value FROM bot_config WHERE key='unlock_pin'")
        row = cur.fetchone()
    conn.close()
    if row and pin == row[0]:
        context.user_data['unlocked'] = True
        context.user_data.pop('awaiting_unlock', None)
        await show_main_menu(update, context, chat_id)
    else:
        await update.message.reply_text("❌ Wrong PIN. Try again:")

async def lang_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    keyboard = [
        [InlineKeyboardButton("🇬🇧 English", callback_data="lang_en")],
        [InlineKeyboardButton("🇰🇭 ភាសាខ្មែរ", callback_data="lang_km")],
    ]
    await update.message.reply_text("🌐 *Select Language / ជ្រើសរើសភាសា*", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def check_bill_alerts(context: ContextTypes.DEFAULT_TYPE):
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cur = conn.execute("SELECT value FROM bot_config WHERE key='alert_bill_payment'")
        pref = cur.fetchone()
        if pref and pref[0] == '0':
            conn.close(); return
        cur = conn.execute("SELECT value FROM bot_config WHERE key='bill_alert_days'")
        row = cur.fetchone()
        bill_days = int(row[0]) if row else 7
        cur = conn.execute("SELECT value FROM bot_config WHERE key='last_bill_alert_time'")
        last_row = cur.fetchone()
        last_alert = float(last_row[0]) if last_row else 0
        now = time.time()
        if now - last_alert < 21600:
            conn.close()
            return
        target_ids = [r[0] for r in conn.execute("SELECT chat_id FROM notification_users WHERE bill_alerts=1 AND active=1").fetchall()]
        today = datetime.now().strftime('%Y-%m-%d')
        due_date = (datetime.now() + timedelta(days=bill_days)).strftime('%Y-%m-%d')
        cur = conn.execute('''SELECT ps.*, c.name as customer_name, c.phone
                              FROM payment_schedules ps
                              JOIN customers c ON ps.customer_id = c.id
                              WHERE ps.status = 'pending' AND ps.due_date <= ? AND ps.due_date >= ?
                              ORDER BY ps.due_date ASC''', (due_date, today))
        bills = cur.fetchall()
        overdue_cur = conn.execute('''SELECT ps.*, c.name as customer_name, c.phone
                                      FROM payment_schedules ps
                                      JOIN customers c ON ps.customer_id = c.id
                                      WHERE ps.status = 'pending' AND ps.due_date < ?
                                      ORDER BY ps.due_date ASC''', (today,))
        overdue = overdue_cur.fetchall()
        conn.close()
        if not bills and not overdue:
            return
        lines = []
        if overdue:
            lines.append(f"🔴 *Overdue Bills* ({len(overdue)})")
            for b in overdue[:5]:
                lines.append(f"• {escape_md(b['customer_name'])} — ${b['amount']:.0f} (due {b['due_date']})")
            if len(overdue) > 5:
                lines.append(f"  ... and {len(overdue)-5} more")
            lines.append("")
        if bills:
            lines.append(f"⚠️ *Upcoming Bills* (within {bill_days}d)")
            for b in bills[:5]:
                lines.append(f"• {escape_md(b['customer_name'])} — ${b['amount']:.0f} (due {b['due_date']})")
            if len(bills) > 5:
                lines.append(f"  ... and {len(bills)-5} more")
        msg = "\n".join(lines)
        for cid in target_ids:
            try:
                await context.application.bot.send_message(cid, msg, parse_mode='Markdown')
            except Exception:
                pass
        conn = sqlite3.connect(DB_PATH)
        conn.execute("UPDATE bot_config SET value = ? WHERE key = 'last_bill_alert_time'", (str(now),))
        conn.commit()
        conn.close()
    except Exception:
        pass

async def check_stock_alerts(context: ContextTypes.DEFAULT_TYPE):
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.execute("SELECT value FROM bot_config WHERE key='alert_stock_runout'")
        pref = cur.fetchone()
        if pref and pref[0] == '0':
            conn.close(); return
        cur = conn.execute("SELECT value FROM bot_config WHERE key='stock_alert_threshold'")
        threshold_row = cur.fetchone()
        cur = conn.execute("SELECT value FROM bot_config WHERE key='alert_interval_hours'")
        interval_row = cur.fetchone()
        cur = conn.execute("SELECT value FROM bot_config WHERE key='last_alert_time'")
        last_row = cur.fetchone()
        threshold = int(threshold_row[0]) if threshold_row else 5
        interval_hours = float(interval_row[0]) if interval_row else 0
        last_alert = float(last_row[0]) if last_row else 0
        now = time.time()
        if interval_hours > 0 and (now - last_alert) < interval_hours * 3600:
            conn.close()
            return
        target_ids = [r[0] for r in conn.execute("SELECT chat_id FROM notification_users WHERE stock_alerts=1 AND active=1").fetchall()]
        cur = conn.execute("SELECT i.name, i.category, i.quantity FROM items i WHERE i.quantity <= ? ORDER BY i.quantity ASC", (threshold,))
        low_items = cur.fetchall()
        runout = [it for it in low_items if it[2] == 0]
        conn.close()
        lines = []
        if runout:
            lines.append(f"🆘 *Run Out of Stock* ({len(runout)})")
            for item in runout[:5]:
                lines.append(f"• {escape_md(item[1])} {escape_md(item[0])} — *0 left*")
            if len(runout) > 5:
                lines.append(f"  ... and {len(runout)-5} more")
            lines.append("")
        if low_items:
            lines.append(f"⚠️ *Low Stock Alert* (≤{threshold})")
            for item in low_items[:10]:
                lines.append(f"• {escape_md(item[1])} {escape_md(item[0])} — *{item[2]} left*")
            if len(low_items) > 10:
                lines.append(f"  ... and {len(low_items)-10} more")
        if not lines:
            return
        msg = "\n".join(lines)
        for cid in target_ids:
            try:
                await context.application.bot.send_message(cid, msg, parse_mode='Markdown')
            except Exception:
                pass
        conn = sqlite3.connect(DB_PATH)
        conn.execute("UPDATE bot_config SET value = ? WHERE key = 'last_alert_time'", (str(now),))
        conn.commit()
        conn.close()
    except Exception:
        pass

async def send_import_alert(context: ContextTypes.DEFAULT_TYPE, item_name, brand, qty, note=''):
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.execute("SELECT value FROM bot_config WHERE key='alert_import'")
        pref = cur.fetchone()
        if pref and pref[0] == '0':
            conn.close(); return
        target_ids = [r[0] for r in conn.execute("SELECT chat_id FROM notification_users WHERE import_alerts=1 AND active=1").fetchall()]
        conn.close()
        msg = f"📦 *New Stock Added*\n{escape_md(brand)} {escape_md(item_name)}\n+{qty} units{escape_md(note)}"
        for cid in target_ids:
            try:
                await context.application.bot.send_message(cid, msg, parse_mode='Markdown')
            except Exception:
                pass
    except Exception:
        pass

def run_bot(token):
    token = token.strip()
    import httpx
    httpx.get(f"https://api.telegram.org/bot{token}/deleteWebhook?drop_pending_updates=true")
    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("additem", add_item))
    app.add_handler(CommandHandler("import", import_stock))
    app.add_handler(CommandHandler("sell", sell))
    app.add_handler(CommandHandler("list", list_items))
    app.add_handler(CommandHandler("report", report))
    app.add_handler(CommandHandler("addbrand", add_brand))
    app.add_handler(CommandHandler("listbrands", list_brands))
    app.add_handler(CommandHandler("deletebrand", delete_brand))
    app.add_handler(CommandHandler("lang", lang_command))
    app.add_handler(conv_handler_item)
    app.add_handler(conv_handler_sell)
    app.add_handler(conv_handler_stock)
    app.add_handler(conv_handler_brand)
    app.add_handler(conv_handler_import_product)
    app.add_handler(conv_handler_import_customer)
    app.add_handler(conv_handler_staff)
    app.add_handler(conv_handler_debt)
    app.add_handler(conv_handler_payment)
    app.add_handler(conv_handler_balance)
    app.add_handler(conv_handler_history)
    app.add_handler(conv_handler_csr)
    app.add_handler(conv_handler_register_code)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_unlock_pin))
    app.add_handler(CallbackQueryHandler(menu_handler))
    job_queue = app.job_queue
    if job_queue:
        job_queue.run_repeating(check_bill_alerts, interval=1800, first=10)
        job_queue.run_repeating(check_stock_alerts, interval=3600, first=30)
    logger.info("Bot started with token %s...", token[:8])
    app.run_polling()

async def run_bot_async(token):
    token = token.strip()
    import httpx
    await httpx.AsyncClient().get(f"https://api.telegram.org/bot{token}/deleteWebhook?drop_pending_updates=true")
    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("additem", add_item))
    app.add_handler(CommandHandler("import", import_stock))
    app.add_handler(CommandHandler("sell", sell))
    app.add_handler(CommandHandler("list", list_items))
    app.add_handler(CommandHandler("report", report))
    app.add_handler(CommandHandler("addbrand", add_brand))
    app.add_handler(CommandHandler("listbrands", list_brands))
    app.add_handler(CommandHandler("deletebrand", delete_brand))
    app.add_handler(CommandHandler("lang", lang_command))
    app.add_handler(conv_handler_item)
    app.add_handler(conv_handler_sell)
    app.add_handler(conv_handler_stock)
    app.add_handler(conv_handler_brand)
    app.add_handler(conv_handler_import_product)
    app.add_handler(conv_handler_import_customer)
    app.add_handler(conv_handler_staff)
    app.add_handler(conv_handler_debt)
    app.add_handler(conv_handler_payment)
    app.add_handler(conv_handler_balance)
    app.add_handler(conv_handler_history)
    app.add_handler(conv_handler_csr)
    app.add_handler(conv_handler_register_code)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_unlock_pin))
    app.add_handler(CallbackQueryHandler(menu_handler))
    job_queue = app.job_queue
    if job_queue:
        job_queue.run_repeating(check_bill_alerts, interval=1800, first=10)
        job_queue.run_repeating(check_stock_alerts, interval=3600, first=30)
    logger.info("Bot started with token %s...", token[:8])
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    return app

async def run_multi():
    init_db()
    tokens = os.getenv("TELEGRAM_BOT_TOKEN", "")
    if not tokens: logger.error("TELEGRAM_BOT_TOKEN not set"); return
    bots = []
    for t in tokens.split(","):
        t = t.strip()
        if t:
            bots.append(await run_bot_async(t))
    logger.info("All %d bots running. Press Ctrl+C to stop.", len(bots))
    try:
        while True:
            await asyncio.sleep(3600)
    except asyncio.CancelledError:
        for b in bots:
            await b.stop()
            await b.shutdown()

def main():
    import ctypes
    ctypes.windll.kernel32.CreateMutexW(None, False, "SokchhornInventoryBot")
    if ctypes.windll.kernel32.GetLastError() == 183:
        logger.warning("Bot already running, exiting this instance.")
        return
    init_db()
    try:
        conn = sqlite3.connect(DB_PATH)
        for key in ('unlock_pin', 'bot_unlock_pin'):
            cur = conn.execute("SELECT value FROM bot_config WHERE key=?", (key,))
            row = cur.fetchone()
            if row and row[0] == '123321':
                logger.warning("Default unlock PIN '123321' is still in use for '%s'. Change it in the web dashboard Settings.", key)
        conn.close()
    except Exception:
        pass
    tokens = os.getenv("TELEGRAM_BOT_TOKEN", "")
    if not tokens: logger.error("TELEGRAM_BOT_TOKEN not set"); return
    all_tokens = [t.strip() for t in tokens.split(",") if t.strip()]
    if not all_tokens: logger.error("No valid tokens found"); return
    if len(all_tokens) == 1:
        run_bot(all_tokens[0])
    else:
        asyncio.run(run_multi())

if __name__ == "__main__":
    main()
