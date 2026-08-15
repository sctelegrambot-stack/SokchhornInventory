import sys, os, subprocess, threading, time, webbrowser, socket
import webview

BASE = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, 'frozen', False) else __file__))

def log(msg):
    try:
        with open(os.path.join(BASE, 'desktop.log'), 'a') as f:
            f.write(f'[{time.strftime("%H:%M:%S")}] {msg}\n')
    except: pass

def port_open(port, timeout=1):
    try:
        s = socket.create_connection(('127.0.0.1', port), timeout=timeout)
        s.close(); return True
    except: return False

def exe_path(name):
    p = os.path.join(BASE, name)
    return p if os.path.exists(p) else os.path.join(BASE, 'bin', name)

def ensure_servers():
    if port_open(5000):
        log('Servers already running')
        return True
    log('Starting webapp...')
    webapp = exe_path('webapp.exe')
    bot = exe_path('bot.exe')
    if not os.path.exists(webapp):
        log(f'webapp.exe not found at {webapp}')
        return False
    subprocess.Popen([webapp], cwd=BASE, creationflags=subprocess.CREATE_NO_WINDOW)
    for i in range(30):
        if port_open(5000, timeout=1):
            log('Webapp ready')
            if os.path.exists(bot):
                subprocess.Popen([bot], cwd=BASE, creationflags=subprocess.CREATE_NO_WINDOW)
                log('Bot started')
            return True
        time.sleep(1)
    log('Webapp failed to start')
    return False

class Api:
    def openBrowser(self): webbrowser.open('http://127.0.0.1:5000/')
    def openTelegram(self): webbrowser.open('https://t.me/scinvenbot')

def main():
    api = Api()
    ready = ensure_servers()
    if ready:
        url = 'http://127.0.0.1:5000/'
        log('Loading webapp at ' + url)
    else:
        url = 'data:text/html,' + ''.join(('%3Chtml%3E%3Cbody%20style%3D%22display%3Aflex%3Bjustify-content%3Acenter%3Balign-items%3Acenter%3Bheight%3A100vh%3Bmargin%3A0%3Bbackground%3A%23f0f2f5%3Bfont-family%3Asans-serif%3Btext-align%3Acenter%3Bflex-direction%3Acolumn%22%3E%3Ch2%3EServer%20Not%20Running%3C%2Fh2%3E%3Cp%3EStart%20webapp.exe%20first%3C%2Fp%3E%3C%2Fbody%3E%3C%2Fhtml%3E'))
        log('Server not ready')
    window = webview.create_window('Inventory Bot', url, width=1280, height=800,
        resizable=True, min_size=(900, 600), js_api=api)
    webview.start(debug=False)

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        import traceback
        log(f'Fatal: {e}\n{traceback.format_exc()}')