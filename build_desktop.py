import os, shutil, site
import subprocess, sys

BASE = os.path.dirname(os.path.abspath(__file__))
DIST = os.path.join(BASE, 'dist')
os.makedirs(DIST, exist_ok=True)

cmd = [
    sys.executable, '-m', 'PyInstaller',
    '--noconfirm',
    '--onefile',
    '--windowed',
    '--name', 'InventoryBot',
    '--distpath', DIST,
    '--workpath', os.path.join(BASE, 'build'),
    '--specpath', BASE,
    '--add-data', f'templates{os.pathsep}templates',
    '--hidden-import', 'webview.platforms.edgechromium',
    '--hidden-import', 'webview.platforms.cef',
    '--hidden-import', 'pystray',
    '--hidden-import', 'PIL',
    '--hidden-import', 'psutil',
    '--hidden-import', 'httpx',
    os.path.join(BASE, 'desktop_app.py'),
]
subprocess.check_call(' '.join(cmd), shell=True, cwd=BASE)
for spec in ('webapp.spec', 'bot.spec'):
    subprocess.check_call(' '.join([
        sys.executable, '-m', 'PyInstaller', '--noconfirm',
        '--distpath', DIST, '--workpath', os.path.join(BASE, 'build'),
        os.path.join(BASE, spec),
    ]), shell=True, cwd=BASE)
for asset in ('.env', 'inventory.db'):
    src = os.path.join(BASE, asset)
    if os.path.exists(src):
        shutil.copy2(src, os.path.join(DIST, asset))
print(f'\nBuild complete: {os.path.join(DIST, "InventoryBot.exe")} (+ webapp.exe, bot.exe)')
