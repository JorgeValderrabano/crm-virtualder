@echo off
REM ==========================================================
REM   CRM Virtualder - Lanzador (Windows)
REM   Doble clic para iniciar. Abre http://localhost:5000
REM ==========================================================
cd /d "%~dp0"

echo.
echo  ============================================
echo    CRM Virtualder - Iniciando...
echo  ============================================
echo.

REM Instalar dependencias si faltan
python -m pip install -q -r requirements.txt 2>nul

REM Iniciar la aplicacion
python app.py

pause
