@echo off
cd /d "C:\sokchhorn_spare_pc"
echo Building Desktop App...
"venv\Scripts\pyinstaller.exe" --noconfirm --onefile --windowed --name "InventoryBot" --icon NUL --add-data "templates;templates" --add-data "venv\Lib\site-packages\webview;webview" "desktop_app.py"
echo Done.
pause
