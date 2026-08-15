import os, shutil, site

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

import subprocess, sys
subprocess.check_call(' '.join(cmd), shell=True, cwd=BASE)
print(f'\nBuild complete: {os.path.join(DIST, "InventoryBot.exe")}')
