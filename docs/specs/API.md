# Spec — API HTTP

Prefixo: `/api/v1`

Autenticação MVP: `X-API-Key`.

## Endpoints P0

### `GET /health`
Saúde do processo.

### `POST /products`
Cria monitor.

Exemplo:

```json
{
  "url": "https://example.com/product/123",
  "check_interval_seconds": 3600,
  "price_scope": "item"
}
```

### `GET /products`
Lista.

### `GET /products/{id}`
Detalhes.

### `PATCH /products/{id}`
Pausa, retoma ou ajusta intervalo/metadados.

### `DELETE /products/{id}`
No MVP, preferir soft delete/archival.

### `POST /products/{id}/check`
Solicita verificação manual respeitando controles.

### `GET /products/{id}/history`
Histórico paginado.

### `POST /products/{id}/rules`
Cria regra.

### `GET /products/{id}/rules`
Lista regras.

### `DELETE /rules/{id}`
Desativa/remove regra conforme política.

### `GET /alerts`
Lista eventos e entrega.

## Erros

Formato:

```json
{
  "error": {
    "code": "unsupported",
    "message": "No reliable collector supports this page.",
    "details": {}
  }
}
```

Não retornar stack trace ao cliente.
