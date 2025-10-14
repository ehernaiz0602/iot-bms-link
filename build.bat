@echo off 
pyinstaller --onefile ^
    --add-data "src/azure_connection/export_pfx.ps1;." ^
    --add-data "config/Settings-Azure.json;config" ^
    --add-data "config/Settings-IP.json;config" ^
    --add-data "config/Settings-General.json;config" ^
    src/main.py
