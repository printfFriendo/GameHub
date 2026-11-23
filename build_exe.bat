@echo off
title Compilando GameHub
echo ===================================================
echo   Compilando GameHub para Executavel (.exe)...
echo ===================================================
python -m PyInstaller --noconfirm --clean --onefile --windowed --name "GameHub" --collect-all customtkinter --add-data "scrapers;scrapers" --add-data "sites_config.json;." main.py
if %ERRORLEVEL% EQU 0 (
    copy /Y "dist\GameHub.exe" "GameHub.exe" >nul
    echo.
    echo ===================================================
    echo   Compilado com sucesso!
    echo   Executavel disponivel em:
    echo   - GameHub.exe (nesta pasta)
    echo   - dist\GameHub.exe
    echo ===================================================
) else (
    echo.
    echo ERRO durante a compilacao! Verifique as mensagens acima.
)
pause
