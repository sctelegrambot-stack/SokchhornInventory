import os
import sys
import subprocess

BASE = os.path.dirname(os.path.abspath(__file__))
DIST = os.path.join(BASE, 'dist')
os.makedirs(DIST, exist_ok=True)

icon_path = os.path.join(BASE, 'app_new.ico')
if not os.path.exists(icon_path):
    icon_path = os.path.join(BASE, 'app.ico')

cmd = [
    sys.executable, '-m', 'PyInstaller',
    '--noconfirm',
    '--onefile',
    '--windowed',
    '--name', 'InventoryBot',
    '--icon', icon_path,
    '--distpath', DIST,
    '--workpath', os.path.join(BASE, 'build'),
    '--specpath', BASE,
    '--add-data', f'templates{os.pathsep}templates',
    '--add-data', f'{icon_path}{os.pathsep}.',
    '--hidden-import', 'webview.platforms.edgechromium',
    '--hidden-import', 'webview.platforms.cef',
    '--hidden-import', 'pystray',
    '--hidden-import', 'PIL',
    '--hidden-import', 'psutil',
    '--hidden-import', 'httpx',
    os.path.join(BASE, 'desktop_app.py'),
]

subprocess.check_call(cmd, cwd=BASE)
print(f'\nBuild complete: {os.path.join(DIST, "InventoryBot.exe")}')
