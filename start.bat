@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Criando ambiente virtual em .venv ...
    python -m venv .venv
    if errorlevel 1 (
        echo Falha ao criar o ambiente virtual. Verifique se o Python 3.11+ esta instalado e no PATH.
        pause
        exit /b 1
    )
    echo Instalando dependencias...
    ".venv\Scripts\python.exe" -m pip install -e ".[dev]"
    if errorlevel 1 (
        echo Falha ao instalar dependencias.
        pause
        exit /b 1
    )
)

if not exist ".env" (
    echo Criando .env a partir de .env.example ...
    copy ".env.example" ".env" >nul
)

if not exist "data" mkdir data

echo Iniciando o worker em uma janela separada...
start "Price Worker" cmd /k ""%cd%\.venv\Scripts\python.exe" -m pricewatch.worker.main"

echo Iniciando a API em http://127.0.0.1:8000 ...
start "" http://127.0.0.1:8000

".venv\Scripts\python.exe" -m uvicorn pricewatch.api.app:app --host 127.0.0.1 --port 8000

endlocal
