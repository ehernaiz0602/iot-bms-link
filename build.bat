@echo off 
pyinstaller --onefile ^
    --add-data "src/azure_connection/export_pfx.ps1;." ^
    src/main.py

IF EXIST dist\main.exe (
    copy /Y dist\main.exe .
    echo main.exe copied to root directory.
) ELSE (
    echo Build failed: dist\main.exe not found.
)
