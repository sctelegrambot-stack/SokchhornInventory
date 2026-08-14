import logging
import sqlite3
import os
import sys
import time
import asyncio
import hmac
import httpx
from datetime import datetime, timedelta
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, ContextTypes, CommandHandler, MessageHandler, filters, CallbackQueryHandler
from config import ADMIN_IDS, DASHBOARD_URL, DB_PATH
from utils import load_langs, get_lang, set_lang, _, _f, escape_md
from db import fetchone, fetchall, get_db

# Load .env from the same directory as the .exe/script
BASE_DIR = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, 'frozen', False) else __file__))
load_dotenv(os.path.join(BASE_DIR, '.env'))

import system_db
system_db.init_system_db()
system_db.ensure_default_org()
try:
    DB_PATH = system_db.get_org_db_path(1)
    config.SYSTEM_DB_PATH = DB_PATH
except Exception:
    pass

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)


def is_owner(context):
    return context.user_data.get('_uid') in ADMIN_IDS


def init_db_reporter():
    """Minimal DB init for the reporter bot - just ensures tables exist."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("INSERT OR IGNORE INTO bot_config (key, value) VALUES ('unlock_pin', '123321')")
    conn.execute("INSERT OR IGNORE INTO bot_config (key, value) VALUES ('stock_alert_threshold', '5')")
    conn.execute("INSERT OR IGNORE INTO bot_config (key, value) VALUES ('alert_interval_hours', '0')")
    conn.execute("INSERT OR IGNORE INTO bot_config (key, value) VALUES ('last_alert_time', '0')")
    conn.execute("INSERT OR IGNORE INTO bot_config (key, value) VALUES ('bill_alert_days', '7')")
    conn.execute("INSERT OR IGNORE INTO bot_config (key, value) VALUES ('last_bill_alert_time', '0')")
    conn.execute("INSERT OR IGNORE INTO bot_config (key, value) VALUES ('alert_bill_payment', '1')")
    conn.execute("INSERT OR IGNORE INTO bot_config (key, value) VALUES ('alert_stock_runout', '1')")
    conn.execute("INSERT OR IGNORE INTO bot_config (key, value) VALUES ('alert_import', '1')")
    conn.commit()
    conn.close()
    load_langs()


async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, chat_id=None):
    if chat_id is None:
        chat_id = update.effective_chat.id
    uid = update.effective_user.id
    context.user_data['_uid'] = uid

    if uid in ADMIN_IDS:
        context.user_data['unlocked'] = True
    if not context.user_data.get('unlocked'):
        context.user_data['awaiting_unlock'] = True
        kb = [
            [InlineKeyboardButton(_('btn_dashboard', chat_id), url=DASHBOARD_URL)],
            [InlineKeyboardButton(_('btn_language', chat_id), callback_data="menu_language")],
        ]
        await update.message.reply_text("🔒 Enter unlock PIN to access reports:", reply_markup=InlineKeyboardMarkup(kb))
        return

    keyboard = [
        [InlineKeyboardButton(_('btn_inv_list', chat_id), callback_data="inv_list")],
        [InlineKeyboardButton(_('btn_sell_report', chat_id), callback_data="sell_report")],
        [InlineKeyboardButton(_('btn_cust_report', chat_id), callback_data="cust_report")],
        [InlineKeyboardButton(_('btn_language', chat_id), callback_data="menu_language")],
    ]
    if DASHBOARD_URL.startswith("https://"):
        keyboard.insert(0, [InlineKeyboardButton("🌐 Open Dashboard", url=DASHBOARD_URL)])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "📊 *Reporter Bot*\nView reports below or open the Dashboard for full management:",
        reply_markup=reply_markup, parse_mode='Markdown'
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    context.user_data.pop('awaiting_unlock', None)
    context.user_data.pop('unlock_fails', None)
    await show_main_menu(update, context, chat_id)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start(update, context)


async def id_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user
    name = (user.first_name or '') + (' ' + user.last_name if user.last_name else '')
    await update.message.reply_text(
        f"🆔 *Your Telegram ID:*\n`{chat_id}`\n\nUse this number in the Dashboard Settings → Notification Recipients to receive alerts.",
        parse_mode='Markdown'
    )
    context.application.bot_data['last_user_name'] = name


async def menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    chat_id = update.effective_chat.id
    context.user_data['_uid'] = update.effective_user.id

    owner = is_owner(context)

    if data == "menu_main":
        uid = update.effective_user.id
        if uid in ADMIN_IDS:
            context.user_data['unlocked'] = True
        if not context.user_data.get('unlocked'):
            context.user_data['awaiting_unlock'] = True
            kb = [[InlineKeyboardButton(_('btn_dashboard', chat_id), url=DASHBOARD_URL),
                   InlineKeyboardButton(_('btn_language', chat_id), callback_data="menu_language")]]
            await query.edit_message_text("🔒 Enter unlock PIN to access reports:", reply_markup=InlineKeyboardMarkup(kb))
            return
        context.user_data.pop('awaiting_unlock', None)
        keyboard = [
            [InlineKeyboardButton(_('btn_inv_list', chat_id), callback_data="inv_list")],
            [InlineKeyboardButton(_('btn_sell_report', chat_id), callback_data="sell_report")],
            [InlineKeyboardButton(_('btn_cust_report', chat_id), callback_data="cust_report")],
        ]
        if DASHBOARD_URL.startswith("https://"):
            keyboard.insert(0, [InlineKeyboardButton("🌐 Dashboard", url=DASHBOARD_URL)])
        keyboard.append([InlineKeyboardButton(_('btn_language', chat_id), callback_data="menu_language")])
        await query.edit_message_text("📊 *Reporter Bot*", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        return

    elif data == "menu_language":
        keyboard = [
            [InlineKeyboardButton("🇬🇧 English", callback_data="lang_en")],
            [InlineKeyboardButton("🇰🇭 ភាសាខ្មែរ", callback_data="lang_km")],
            [InlineKeyboardButton(_('btn_back', chat_id), callback_data="menu_main")],
        ]
        await query.edit_message_text("🌐 *Language / ភាសា*", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    elif data.startswith("lang_"):
        lang = data[5:]
        set_lang(chat_id, lang)
        await query.edit_message_text(_('msg_lang_changed', chat_id),
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(_('btn_menu', chat_id), callback_data="menu_main")]]))

    # ── Read-only Reports ──
    elif data == "inv_list":
        from db import fetchall
        items = fetchall("SELECT id,name,category,quantity,price,group_name,ram,rom,cost_price,product_code FROM items")
        if not items:
            await query.edit_message_text(_('msg_no_items', chat_id),
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🌐 Dashboard", url=DASHBOARD_URL), InlineKeyboardButton(_('btn_back', chat_id), callback_data="menu_main")]]))
            return
        resp = "📋 *Inventory*\n"
        for i in items:
            safe_name = escape_md(i[1])
            spec = f" ({i[6]}/{i[7]})" if i[6] or i[7] else ''
            resp += f"ID:{i[0]} {safe_name}{spec} Qty:{i[3]} R:${i[4] or 'N/A'}\n"
        await query.edit_message_text(resp,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🌐 Dashboard", url=DASHBOARD_URL), InlineKeyboardButton(_('btn_back', chat_id), callback_data="menu_main")]]),
            parse_mode='Markdown')

    elif data == "sell_report":
        from db import fetchall
        sales = fetchall("SELECT s.timestamp,i.name,s.quantity,i.price,s.sellout_price,s.delivery_fee,i.cost_price FROM sales s JOIN items i ON s.item_id=i.id WHERE COALESCE(s.special,0)=0 ORDER BY s.timestamp DESC LIMIT 10")
        if not sales:
            await query.edit_message_text(_('msg_no_sales', chat_id),
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🌐 Dashboard", url=DASHBOARD_URL), InlineKeyboardButton(_('btn_back', chat_id), callback_data="menu_main")]]))
            return
        resp = "📊 *Recent Sales*\n"
        ts = 0
        tr = 0
        for s in sales:
            price = float(s[4]) if s[4] else (s[3] or 0)
            resp += f"{s[0][:10]} {s[1]} x{s[2]} ${price:.0f}\n"
            ts += s[2]
            tr += price * s[2]
        resp += f"\n{_('report_total_qty', chat_id)} {ts}\n{_('report_total_revenue', chat_id)} ${tr:.0f}"
        await query.edit_message_text(resp,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🌐 Dashboard", url=DASHBOARD_URL), InlineKeyboardButton(_('btn_back', chat_id), callback_data="menu_main")]]),
            parse_mode='Markdown')

    elif data == "cust_report":
        rows = fetchall("""SELECT ps.id,c.id,c.name,ps.amount,ps.due_date,ps.status
            FROM payment_schedules ps JOIN customers c ON ps.customer_id=c.id
            WHERE ps.status='pending' ORDER BY ps.due_date ASC""")
        if not rows:
            await query.edit_message_text(_('msg_no_schedules', chat_id),
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🌐 Dashboard", url=DASHBOARD_URL), InlineKeyboardButton(_('btn_back', chat_id), callback_data="menu_main")]]))
            return
        today = datetime.now().strftime('%Y-%m-%d')
        overdue = [r for r in rows if r[4] < today]
        upcoming = [r for r in rows if r[4] >= today]
        resp = "📋 *Outstanding Bills*\n"
        if overdue:
            resp += f"\n🔴 *Overdue ({len(overdue)})*\n"
            for r in overdue[:5]:
                safe_name = escape_md(r[2])
                resp += f"  {safe_name} ${r[3]:.0f} (due {r[4]})\n"
        if upcoming:
            resp += f"\n🟡 *Upcoming ({len(upcoming)})*\n"
            for r in upcoming[:5]:
                safe_name = escape_md(r[2])
                resp += f"  {safe_name} ${r[3]:.0f} (due {r[4]})\n"
        await query.edit_message_text(resp,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🌐 Dashboard", url=DASHBOARD_URL), InlineKeyboardButton(_('btn_back', chat_id), callback_data="menu_main")]]),
            parse_mode='Markdown')


async def handle_unlock_pin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('awaiting_unlock'):
        return
    chat_id = update.effective_chat.id
    pin = update.message.text.strip()
    # Brute-force lockout: after 5 wrong PINs the chat is blocked until /start.
    fails = context.user_data.get('unlock_fails', 0)
    if fails >= 5:
        await update.message.reply_text("🔒 Too many wrong PIN attempts. Use /start to try again in a few minutes.")
        return
    row = fetchone("SELECT value FROM bot_config WHERE key='unlock_pin'")
    if row and hmac.compare_digest(pin, str(row[0])):
        context.user_data['unlocked'] = True
        context.user_data.pop('awaiting_unlock', None)
        context.user_data.pop('unlock_fails', None)
        await show_main_menu(update, context, chat_id)
    else:
        context.user_data['unlock_fails'] = fails + 1
        remaining = max(0, 5 - fails - 1)
        await update.message.reply_text(f"❌ Wrong PIN. {remaining} attempt(s) remaining.")


async def lang_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    keyboard = [
        [InlineKeyboardButton("🇬🇧 English", callback_data="lang_en")],
        [InlineKeyboardButton("🇰🇭 ភាសាខ្មែរ", callback_data="lang_km")],
    ]
    await update.message.reply_text("🌐 *Language / ភាសា*", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')


async def check_bill_alerts(context: ContextTypes.DEFAULT_TYPE):
    try:
        pref = fetchone("SELECT value FROM bot_config WHERE key='alert_bill_payment'")
        if pref and pref[0] == '0':
            return
        row = fetchone("SELECT value FROM bot_config WHERE key='bill_alert_days'")
        bill_days = int(row[0]) if row else 7
        last_row = fetchone("SELECT value FROM bot_config WHERE key='last_bill_alert_time'")
        last_alert = float(last_row[0]) if last_row else 0
        now = time.time()
        if now - last_alert < 21600:
            return
        target_ids = [r[0] for r in fetchall("SELECT chat_id FROM notification_users WHERE bill_alerts=1 AND active=1")]
        today = datetime.now().strftime('%Y-%m-%d')
        due_date = (datetime.now() + timedelta(days=bill_days)).strftime('%Y-%m-%d')
        bills = fetchall('''SELECT c.name as customer_name, ps.amount, ps.due_date
            FROM payment_schedules ps JOIN customers c ON ps.customer_id = c.id
            WHERE ps.status = 'pending' AND ps.due_date <= ? AND ps.due_date >= ?
            ORDER BY ps.due_date ASC''', (due_date, today))
        overdue = fetchall('''SELECT c.name as customer_name, ps.amount, ps.due_date
            FROM payment_schedules ps JOIN customers c ON ps.customer_id = c.id
            WHERE ps.status = 'pending' AND ps.due_date < ?
            ORDER BY ps.due_date ASC''', (today,))
        if not bills and not overdue:
            return
        lines = []
        if overdue:
            lines.append(f"🔴 *Overdue Bills ({len(overdue)})*")
            for b in overdue[:5]:
                lines.append(f"• {b['customer_name']} — ${b['amount']:.0f} (due {b['due_date']})")
            lines.append("")
        if bills:
            lines.append(f"⚠️ *Upcoming Bills (within {bill_days}d)*")
            for b in bills[:5]:
                lines.append(f"• {b['customer_name']} — ${b['amount']:.0f} (due {b['due_date']})")
        msg = "\n".join(lines)
        for cid in target_ids:
            try:
                await context.application.bot.send_message(cid, msg + f"\n\n🌐 {DASHBOARD_URL}", parse_mode='Markdown')
            except Exception:
                pass
        with get_db() as conn:
            conn.execute("UPDATE bot_config SET value = ? WHERE key = 'last_bill_alert_time'", (str(now),))
    except Exception:
        logger.exception("Bill alert error")


async def check_stock_alerts(context: ContextTypes.DEFAULT_TYPE):
    try:
        pref = fetchone("SELECT value FROM bot_config WHERE key='alert_stock_runout'")
        if pref and pref[0] == '0':
            return
        threshold_row = fetchone("SELECT value FROM bot_config WHERE key='stock_alert_threshold'")
        interval_row = fetchone("SELECT value FROM bot_config WHERE key='alert_interval_hours'")
        last_row = fetchone("SELECT value FROM bot_config WHERE key='last_alert_time'")
        threshold = int(threshold_row[0]) if threshold_row else 5
        interval_hours = float(interval_row[0]) if interval_row else 0
        last_alert = float(last_row[0]) if last_row else 0
        now = time.time()
        if interval_hours > 0 and (now - last_alert) < interval_hours * 3600:
            return
        target_ids = [r[0] for r in fetchall("SELECT chat_id FROM notification_users WHERE stock_alerts=1 AND active=1")]
        low_items = fetchall("SELECT i.name, i.category, i.quantity FROM items i WHERE i.quantity <= ? ORDER BY i.quantity ASC", (threshold,))
        runout = [it for it in low_items if it[2] == 0]
        lines = []
        if runout:
            lines.append(f"🆘 *Run Out of Stock ({len(runout)})*")
            for item in runout[:5]:
                lines.append(f"• {item[1]} {item[0]} — *0 left*")
            lines.append("")
        if low_items:
            lines.append(f"⚠️ *Low Stock (≤{threshold})*")
            for item in low_items[:10]:
                lines.append(f"• {item[1]} {item[0]} — *{item[2]} left*")
        if not lines:
            return
        msg = "\n".join(lines)
        for cid in target_ids:
            try:
                await context.application.bot.send_message(cid, msg + f"\n\n🌐 {DASHBOARD_URL}", parse_mode='Markdown')
            except Exception:
                pass
        with get_db() as conn:
            conn.execute("UPDATE bot_config SET value = ? WHERE key = 'last_alert_time'", (str(now),))
    except Exception:
        logger.exception("Stock alert error")


def run_bot(token):
    token = token.strip()
    httpx.get(f"https://api.telegram.org/bot{token}/deleteWebhook?drop_pending_updates=true")
    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("id", id_command))
    app.add_handler(CommandHandler("lang", lang_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_unlock_pin))
    app.add_handler(CallbackQueryHandler(menu_handler))
    job_queue = app.job_queue
    if job_queue:
        job_queue.run_repeating(check_bill_alerts, interval=1800, first=10)
        job_queue.run_repeating(check_stock_alerts, interval=3600, first=30)
    logger.info("Reporter bot started with token %s...", token[:8])
    app.run_polling()


async def run_bot_async(token):
    token = token.strip()
    await httpx.AsyncClient().get(f"https://api.telegram.org/bot{token}/deleteWebhook?drop_pending_updates=true")
    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("id", id_command))
    app.add_handler(CommandHandler("lang", lang_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_unlock_pin))
    app.add_handler(CallbackQueryHandler(menu_handler))
    job_queue = app.job_queue
    if job_queue:
        job_queue.run_repeating(check_bill_alerts, interval=1800, first=10)
        job_queue.run_repeating(check_stock_alerts, interval=3600, first=30)
    logger.info("Reporter bot started with token %s...", token[:8])
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    return app


async def run_multi():
    init_db_reporter()
    tokens = os.getenv("TELEGRAM_BOT_TOKEN", "")
    if not tokens:
        logger.error("TELEGRAM_BOT_TOKEN not set")
        return
    bots = []
    for t in tokens.split(","):
        t = t.strip()
        if t:
            bots.append(await run_bot_async(t))
    logger.info("All %d reporter bots running.", len(bots))
    try:
        while True:
            await asyncio.sleep(3600)
    except asyncio.CancelledError:
        for b in bots:
            await b.stop()
            await b.shutdown()


def main():
    if os.name == 'nt':
        import ctypes
        try:
            ctypes.windll.kernel32.CreateMutexW(None, False, "SokchhornInventoryBot")
            if ctypes.windll.kernel32.GetLastError() == 183:
                logger.warning("Bot already running, exiting.")
                return
        except AttributeError:
            pass
    init_db_reporter()
    tokens = os.getenv("TELEGRAM_BOT_TOKEN", "")
    if not tokens:
        logger.error("TELEGRAM_BOT_TOKEN not set")
        return
    all_tokens = [t.strip() for t in tokens.split(",") if t.strip()]
    if not all_tokens:
        logger.error("No valid tokens found")
        return
    if len(all_tokens) == 1:
        run_bot(all_tokens[0])
    else:
        asyncio.run(run_multi())


if __name__ == "__main__":
    main()
