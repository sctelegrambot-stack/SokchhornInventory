import subprocess
import sys
import os
import ctypes
import time
import re
import urllib.request
import urllib.error
import json

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
PYTHON = os.path.join(PROJECT_DIR, "venv", "Scripts", "python.exe")
NGROK = os.path.join(PROJECT_DIR, "ngrok.exe")
ENV_FILE = os.path.join(PROJECT_DIR, ".env")

def read_env_token():
    try:
        with open(ENV_FILE) as f:
            for line in f:
                if line.startswith("TELEGRAM_BOT_TOKEN="):
                    token = line.strip().split("=", 1)[1]
                    if token:
                        return token
    except Exception:
        pass
    return ''

def message_box(title, text):
    ctypes.windll.user32.MessageBoxW(0, text, title, 0)

def find_ngrok():
    for candidate in [
        NGROK,
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "WindowsApps", "ngrok.exe"),
    ]:
        if os.path.exists(candidate):
            return candidate
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

def write_env(token, url):
    header = []
    lines = {}
    if os.path.exists(ENV_FILE):
        with open(ENV_FILE) as f:
            for line in f:
                stripped = line.strip()
                if stripped and '=' in stripped and not stripped.startswith('#'):
                    k, v = stripped.split('=', 1)
                    lines[k.strip()] = v
                elif stripped:
                    header.append(stripped)
    lines['TELEGRAM_BOT_TOKEN'] = token
    lines['DASHBOARD_URL'] = url
    with open(ENV_FILE, "w") as f:
        for h in header:
            f.write(h + "\n")
        for k, v in lines.items():
            f.write(f"{k}={v}\n")

def start_process(script_name):
    script = os.path.join(PROJECT_DIR, script_name)
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    proc = subprocess.Popen(
        [PYTHON, script],
        cwd=PROJECT_DIR,
        startupinfo=startupinfo,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    return proc

def main():
    if not os.path.exists(PROJECT_DIR):
        message_box("Error", f"Project directory not found:\n{PROJECT_DIR}")
        sys.exit(1)
    if not os.path.exists(PYTHON):
        message_box("Error", f"Python not found:\n{PYTHON}")
        sys.exit(1)

    # Wait for network before anything
    for _ in range(30):
        try:
            urllib.request.urlopen("https://google.com", timeout=3)
            break
        except Exception:
            time.sleep(2)

    # Kill old ngrok and any previous bot/dashboard processes
    subprocess.run(["taskkill", "/f", "/im", "ngrok.exe"], capture_output=True)
    for script in ["webapp.py", "main.py"]:
        subprocess.run(["taskkill", "/f", "/fi", "IMAGENAME eq python.exe",
                        "/fi", f"CMDline contains {script}"], capture_output=True)
    time.sleep(2)

    # Start ngrok tunnel
    ngrok_exe = find_ngrok()
    try:
        subprocess.Popen(
            [ngrok_exe, "http", "5000"],
            cwd=PROJECT_DIR,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    except FileNotFoundError:
        message_box("Inventory Bot",
                    "ngrok.exe not found.\n\n"
                    "Run setup_spare_pc.bat to install ngrok, or place ngrok.exe in the project folder.")
        ngrok_exe = None

    # Wait for ngrok URL (up to 60s, retry every 2s)
    url = None
    if ngrok_exe is not None:
        for _ in range(30):
            time.sleep(2)
            url = get_ngrok_url()
            if url:
                break

    if url:
        token = read_env_token()
        if not token:
            message_box("Error", "TELEGRAM_BOT_TOKEN not set in .env\n\n"
                                 "Add your bot token to .env and try again.")
            return
        write_env(token, url)
    else:
        ctypes.windll.user32.MessageBoxW(0,
            "ngrok URL not detected. Check your internet connection.",
            "Inventory Bot", 0)

    # Start dashboard + bot
    for script in ["webapp.py", "main.py"]:
        start_process(script)
        time.sleep(3)

    message_box("Inventory Bot",
        "✅ Bot & Dashboard started!\n\n"
        f"URL: {url or 'Check ngrok dashboard'}")

if __name__ == "__main__":
    main()
