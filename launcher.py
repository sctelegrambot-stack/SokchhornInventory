"""Launcher - thin wrapper that loads .env and starts the desktop app."""
import subprocess
import sys
import os
import ctypes
import time
from dotenv import load_dotenv

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(PROJECT_DIR, '.env'))
VENV_DIR = os.path.join(PROJECT_DIR, "venv")
PYTHON = os.path.join(VENV_DIR, "Scripts", "python.exe")


def message_box(title, text):
    ctypes.windll.user32.MessageBoxW(0, text, title, 0)


def main():
    if not os.path.exists(PROJECT_DIR):
        message_box("Error", f"Project directory not found:\n{PROJECT_DIR}")
        sys.exit(1)

    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    if not token:
        message_box("Error", "TELEGRAM_BOT_TOKEN not set in .env file.\nCreate .env with your bot token from @BotFather.")
        sys.exit(1)

    # Kill stale ngrok
    subprocess.run(["taskkill", "/f", "/im", "ngrok.exe"], capture_output=True)

    # Determine entry point
    desktop_exe = os.path.join(PROJECT_DIR, "desktop_app.exe")
    if os.path.exists(desktop_exe):
        subprocess.Popen([desktop_exe], cwd=PROJECT_DIR)
    elif os.path.exists(PYTHON):
        subprocess.Popen([PYTHON, os.path.join(PROJECT_DIR, "desktop_app.py")], cwd=PROJECT_DIR)
    else:
        message_box("Error", "Neither desktop_app.exe nor venv Python found.\nRun setup.bat first.")
        sys.exit(1)

    time.sleep(2)
    message_box("Inventory Bot", "Desktop app launched!\nCheck the system tray or taskbar.")


if __name__ == "__main__":
    main()
