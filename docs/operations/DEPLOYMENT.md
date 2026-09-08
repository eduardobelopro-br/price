# Operação e implantação

## Windows local

```powershell
cd F:\Github\price
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
python -m uvicorn pricewatch.api.app:app --host 127.0.0.1 --port 8000
```

Worker, após implementado:

```powershell
python -m pricewatch.worker.main
```

## Docker

```powershell
docker compose up --build
```

## Variáveis

Ver `.env.example`.

## Backup

Para SQLite: pausar gravações ou usar a API de backup do SQLite. Nunca copiar arquivo em escrita ativa assumindo consistência.

## Logs

Formato estruturado em produção. Rotação obrigatória para serviço contínuo.

## Telegram

`TELEGRAM_BOT_TOKEN` e `TELEGRAM_CHAT_ID` são opcionais até que o notificador seja habilitado.
