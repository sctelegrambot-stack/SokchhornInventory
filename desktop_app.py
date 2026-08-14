import sys
import os
import subprocess
import time
import webbrowser
import socket
import logging
import json
import urllib.request
import urllib.error
from dotenv import load_dotenv

import webview

BASE = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, 'frozen', False) else __file__))

# Load .env from the same directory as the .exe/script
load_dotenv(os.path.join(BASE, '.env'))
LOG_FILE = os.path.join(BASE, 'desktop.log')

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format='[%(asctime)s] %(message)s',
    datefmt='%H:%M:%S',
)
logger = logging.getLogger(__name__)


def port_open(port, timeout=1):
    try:
        with socket.create_connection(('127.0.0.1', port), timeout=timeout):
            return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False


def exe_path(name):
    p = os.path.join(BASE, name)
    return p if os.path.exists(p) else os.path.join(BASE, 'bin', name)


def find_ngrok():
    candidates = [
        os.path.join(os.environ.get("TEMP", "C:\\Temp"), "opencode", "ngrok.exe"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "WindowsApps", "ngrok.exe"),
        os.path.join(BASE, "bin", "ngrok.exe"),
        "ngrok",
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return "ngrok"


def get_ngrok_url():
    try:
        resp = urllib.request.urlopen("http://127.0.0.1:4040/api/tunnels", timeout=5)
        data = json.loads(resp.read().decode())
        for t in data.get("tunnels", []):
            pub = t.get("public_url", "")
            if pub.startswith("https://"):
                return pub.rstrip("/") + "/"
    except Exception:
        pass
    return None


ENV_FILE = os.path.join(BASE, '.env')
VENV_PYTHON = os.path.join(BASE, 'venv', 'Scripts', 'python.exe')


def write_env_dashboard_url(url):
    """Write the ngrok URL into .env as DASHBOARD_URL so bot/webapp can use it."""
    try:
        lines = []
        found = False
        if os.path.exists(ENV_FILE):
            with open(ENV_FILE, 'r') as f:
                for line in f:
                    if line.startswith('DASHBOARD_URL='):
                        lines.append(f'DASHBOARD_URL={url}\n')
                        found = True
                    else:
                        lines.append(line)
        if not found:
            lines.append(f'DASHBOARD_URL={url}\n')
        with open(ENV_FILE, 'w') as f:
            f.writelines(lines)
        # Also set in current process environment so it takes effect immediately
        os.environ['DASHBOARD_URL'] = url
        logger.info('DASHBOARD_URL set to %s', url)
    except Exception as e:
        logger.warning('Failed to write DASHBOARD_URL to .env: %s', e)


def start_ngrok():
    ngrok_exe = find_ngrok()
    logger.info('Starting ngrok: %s', ngrok_exe)
    subprocess.Popen(
        [ngrok_exe, "http", "5000", "--log=stdout"],
        cwd=BASE,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    ngrok_url = None
    for _ in range(30):
        time.sleep(2)
        ngrok_url = get_ngrok_url()
        if ngrok_url:
            break
    if ngrok_url:
        logger.info('ngrok URL: %s', ngrok_url)
        write_env_dashboard_url(ngrok_url)
    return ngrok_url


def start_script(script_name):
    """Start a Python script via any available python interpreter."""
    script = os.path.join(BASE, script_name)
    if not os.path.exists(script):
        return False
    # Prefer venv Python, fall back to the same interpreter that launched us
    for py in (VENV_PYTHON, sys.executable):
        if os.path.exists(py):
            subprocess.Popen([py, script], cwd=BASE, creationflags=subprocess.CREATE_NO_WINDOW)
            return True
    return False


def start_app():
    if port_open(5000):
        logger.info('Webapp already running')
        return True
    logger.info('Starting webapp...')
    # Prefer Python script over stale compiled .exe so code changes take effect
    if start_script('webapp.py'):
        logger.info('Started webapp.py')
    elif os.path.exists(exe_path('webapp.exe')):
        subprocess.Popen([exe_path('webapp.exe')], cwd=BASE, creationflags=subprocess.CREATE_NO_WINDOW)
    else:
        logger.error('Failed to start webapp')
        return False
    for i in range(30):
        if port_open(5000, timeout=1):
            logger.info('Webapp ready on port 5000')
            return True
        time.sleep(1)
    logger.error('Webapp failed to start')
    return False


def start_bot():
    """Start the bot subprocess ONLY if RUN_LOCAL_BOT=1.

    With the app hosted on Fly.io, the Telegram bot runs in the cloud and the
    local machine must not poll the same token (single getUpdates allowed).
    """
    if os.getenv('RUN_LOCAL_BOT', '0') != '1':
        logger.info('Bot skipped: RUN_LOCAL_BOT != 1 (Telegram bot runs on Fly.io)')
        return
    # Prefer Python script over stale compiled .exe so code changes take effect
    if start_script('main.py'):
        logger.info('Bot started (main.py)')
    elif os.path.exists(exe_path('bot.exe')):
        subprocess.Popen([exe_path('bot.exe')], cwd=BASE, creationflags=subprocess.CREATE_NO_WINDOW)
        logger.info('Bot started (bot.exe)')
    else:
        logger.warning('No bot executable or script found (non-fatal)')


class Api:
    ngrok_url = ""

    def openBrowser(self):
        webbrowser.open('http://127.0.0.1:5000/')

    def openDashboard(self):
        webbrowser.open(self.ngrok_url if self.ngrok_url else 'http://127.0.0.1:5000/')

    def copyNgrokUrl(self):
        if self.ngrok_url:
            import pyperclip
            try:
                pyperclip.copy(self.ngrok_url.rstrip('/'))
            except Exception:
                pass

    def getNgrokUrl(self):
        return self.ngrok_url or ''


def main():
    api = Api()

    if start_app():
        if os.getenv('RUN_LOCAL_NGROK', '0') == '1':
            # Start ngrok BEFORE bot so DASHBOARD_URL is set in os.environ for the bot subprocess
            ngrok_url = start_ngrok()
            api.ngrok_url = ngrok_url or ''
        else:
            api.ngrok_url = os.getenv('DASHBOARD_URL', '').rstrip('/') or 'https://sokchhorn-bot.fly.dev'
        start_bot()
        token = os.getenv('DESKTOP_LOGIN_TOKEN', '').strip()
        if token:
            from urllib.parse import quote
            url = f'http://127.0.0.1:5000/desktop-login?t={quote(token)}'
        else:
            # No shared desktop token configured: show the normal login page
            # instead of trying the (now fail-closed) auto-login endpoint.
            url = 'http://127.0.0.1:5000/'
        logger.info('Loading webapp at %s', url)
    else:
        url = 'data:text/html,' + ''.join(('%3Chtml%3E%3Cbody%20style%3D%22display%3Aflex%3Bjustify-content%3Acenter%3Balign-items%3Acenter%3Bheight%3A100vh%3Bmargin%3A0%3Bbackground%3A%23f0f2f5%3Bfont-family%3Asans-serif%3Btext-align%3Acenter%3Bflex-direction%3Acolumn%22%3E%3Ch2%3EServer%20Not%20Running%3C%2Fh2%3E%3Cp%3EStart%20webapp.exe%20first%3C%2Fp%3E%3C%2Fbody%3E%3C%2Fhtml%3E'))
        logger.warning('Server not ready')
    window = webview.create_window(
        'Inventory Bot', url,
        width=1280, height=800,
        resizable=True, min_size=(900, 600),
        js_api=api,
    )
    webview.start(debug=False)


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        import traceback
        logger.exception('Fatal error: %s', e)
