@echo off
cd /d "%~dp0"
if exist "dist\InventoryBot.exe" (
    start "" "dist\InventoryBot.exe"
) else (
    start "" "venv\Scripts\pythonw.exe" "desktop_app.py"
)
exit
