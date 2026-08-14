import os
import sys
import secrets
from dotenv import load_dotenv

# When frozen (PyInstaller .exe), use the .exe's directory; otherwise use __file__'s directory
BASE_DIR = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, 'frozen', False) else __file__))

# Load .env from the same directory as the .exe/script
load_dotenv(os.path.join(BASE_DIR, '.env'))

# When frozen (PyInstaller .exe), use the .exe's directory; otherwise use __file__'s directory
BASE_DIR = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, 'frozen', False) else __file__))
DB_PATH = os.getenv("DB_PATH", os.path.join(BASE_DIR, "inventory.db"))
ADMIN_IDS = {7185846273}
LANG_FILE = os.getenv("LANG_FILE", os.path.join(BASE_DIR, "lang_prefs.json"))

DASHBOARD_URL = os.getenv("DASHBOARD_URL", "https://sokchhorn-bot.fly.dev/").rstrip("/") + "/"
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")

# Multi-tenant: shared tenant directory database
SYSTEM_DB_PATH = os.getenv("SYSTEM_DB_PATH", os.path.join(BASE_DIR, "system.db"))

# SECRET_KEY: prefer an explicit env var, otherwise persist a generated key next to
# the system DB so user sessions survive restarts/redepoys (unless the dir is RO).
def _load_secret_key():
    from_env = os.environ.get("SECRET_KEY")
    if from_env:
        return from_env
    key_path = os.path.join(os.path.dirname(SYSTEM_DB_PATH), ".secret_key")
    try:
        if os.path.exists(key_path):
            with open(key_path, 'r') as f:
                key = f.read().strip()
                if key:
                    return key
        key = secrets.token_hex(32)
        with open(key_path, 'w') as f:
            f.write(key)
        return key
    except OSError:
        # Fall back to an ephemeral key (e.g. read-only filesystem).
        return secrets.token_hex(24)

SECRET_KEY = _load_secret_key()

# Whether the public /register page can create new (super-)admin accounts.
# Set ALLOW_REGISTRATION=0 in production once your first admin exists.
ALLOW_REGISTRATION = os.getenv("ALLOW_REGISTRATION", "1") == "1"

# Desktop-app auto-login secret. /desktop-login only works when the client is
# on loopback AND supplies this token. Leave empty to disable desktop auto-login
# entirely (fail closed). Never expose this to the public web app.
DESKTOP_LOGIN_TOKEN = os.getenv("DESKTOP_LOGIN_TOKEN", "")
# Username (in any org) that gets the org-provisioning super-admin panel
SUPER_ADMIN_USERNAME = os.getenv("SUPER_ADMIN_USERNAME", "")

# Free-plan limits (per shop). Defaults: 15 products, 3 users.
FREE_ITEM_LIMIT = int(os.getenv("FREE_ITEM_LIMIT", "15"))
FREE_USER_LIMIT = int(os.getenv("FREE_USER_LIMIT", "3"))
# Org ids that are permanently unlimited (grandfathered). Default "1" = admin@sokchhorn's shop.
UNLIMITED_ORG_IDS = set(x.strip() for x in os.getenv("UNLIMITED_ORG_IDS", "1").split(",") if x.strip())

# Desktop app feature permissions, controlled by the web app (owner/admin).
# Each feature is a toggle the web Settings page can enable/deny for the desktop app.
DESKTOP_FEATURES = {
    'delete': {'label': 'Delete', 'icon': 'bi-trash', 'desc': 'Delete items, sales, customers, brands & categories', 'default': '0'},
    'print': {'label': 'Print', 'icon': 'bi-printer', 'desc': 'Print barcodes & receipts', 'default': '1'},
    'import': {'label': 'Import', 'icon': 'bi-box-arrow-in-down', 'desc': 'Add stock, import Excel, add items', 'default': '1'},
    'edit': {'label': 'Edit', 'icon': 'bi-pencil', 'desc': 'Edit item prices & details', 'default': '1'},
    'export': {'label': 'Export', 'icon': 'bi-file-earmark-excel', 'desc': 'Download Excel reports', 'default': '1'},
    'sellout': {'label': 'Sellout', 'icon': 'bi-cart-plus', 'desc': 'Make sales & sellout', 'default': '1'},
    'customers': {'label': 'Customers', 'icon': 'bi-people', 'desc': 'Manage customers & credit', 'default': '1'},
}
