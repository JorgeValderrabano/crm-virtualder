@echo off
echo Arrancando Virtualder CRM...

:: 1. Lanza un temporizador oculto que abrirá el navegador en 2 segundos
start cmd /c "timeout /t 2 > NUL && start http://localhost:5000/"

:: 2. Inicia tu servidor Flask
python app.py