# Spec — Banco de dados

## Tabelas

### products
Identidade e agenda do monitor.

### snapshots
Observações válidas, append-only.

### collection_attempts
Uma linha por tentativa, inclusive erros.

### rules
Regras ativas/inativas.

### alert_events
Evento lógico idempotente.

### outbox
Entrega pendente/tentativas.

### schema_migrations
Controle de versão.

## Restrições

- `snapshots.amount` armazenado como decimal textual ou integer minor units, nunca float.
- `currency` obrigatório para preço válido.
- unique para `alert_events.idempotency_key`.
- índices em `products.next_check_at`, `snapshots.product_id, observed_at`, `outbox.status, next_attempt_at`.

## Retenção

Histórico é valioso. Não remover automaticamente no MVP. Se crescer, adotar compactação/retention documentada sem apagar mínimos históricos usados nas regras.
