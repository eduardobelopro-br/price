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

Worker (processo separado, independente da API):

```powershell
python -m pricewatch.worker.main
```

## Docker

```powershell
docker compose up --build
```

`docker-compose.yml` sobe dois serviços a partir da mesma imagem: `api` (porta 8000, bind
`127.0.0.1`) e `worker` (sem porta exposta), ambos compartilhando `./data` via volume para o
SQLite. Validado manualmente: `docker compose up -d`, cadastro de produto via API, e o worker
coletando o preço de forma independente no ciclo seguinte.

## CI

`.github/workflows/ci.yml` roda `ruff check`, `mypy --strict` e `pytest` em Python 3.11 e 3.12
a cada push/PR. Nenhum teste depende de rede real (SSRF/HTTP são testados com transporte e
resolver injetados).

## Variáveis

Ver `.env.example`.

## Backup

Para SQLite: pausar gravações ou usar a API de backup do SQLite. Nunca copiar arquivo em escrita ativa assumindo consistência.

## Logs

Formato estruturado (JSON, um objeto por linha) via `pricewatch.logging_config.configure_logging()`,
usado pela API e pelo worker. Campos como `product_id` e `domain` são anexados via `extra=` nos
pontos relevantes; chaves sensíveis (`token`, `api_key`, `password`, `secret`) nunca aparecem na
saída, mesmo se alguém passar `extra={"bot_token": ...}` por engano. Rotação de arquivo é
responsabilidade do orquestrador (Docker/systemd), não da aplicação.

## Telegram

`TELEGRAM_BOT_TOKEN` e `TELEGRAM_CHAT_ID` são opcionais até que o notificador seja habilitado.
