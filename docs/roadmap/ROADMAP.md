# Roadmap de implementação

## Etapa 0 — Reconhecimento
- inspecionar repositório existente;
- preservar trabalho local;
- alinhar dependências e convenções.

## Etapa 1 — Domínio e persistência
- entidades;
- money;
- snapshots/errors;
- SQLite/migrações;
- testes unitários.

## Etapa 2 — Coleta
- URL safety;
- HTTP client;
- demo;
- JSON-LD;
- registry de adaptadores.

## Etapa 3 — Monitor
- scheduler/worker;
- retries/backoff;
- estados;
- collection attempts.

## Etapa 4 — Alertas
- regras;
- eventos idempotentes;
- outbox;
- Telegram.

## Etapa 5 — API e UI
- CRUD;
- histórico;
- status;
- configuração.

## Etapa 6 — Hardening
- SSRF tests;
- limites;
- logs;
- backups;
- Docker;
- CI.

## Etapa 7 — Integrações reais
Adicionar uma por vez, somente com fonte confiável e testes.

## Definition of Done
Código + testes + documentação + comandos reproduzíveis + limitações registradas.
