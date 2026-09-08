# Código-base de referência

O diretório `src/pricewatch` fornece contratos e um fluxo mínimo. Ele **não é o MVP completo**.

Incluído:

- `Money`;
- `OfferSnapshot`;
- `CollectResult`;
- protocolo `Collector`;
- `DemoCollector`;
- registry simples;
- FastAPI com `/health` e endpoint de coleta demonstrativo;
- testes unitários básicos.

A IA executora deve completar persistência, SSRF-safe HTTP, JSON-LD, worker, regras, outbox, Telegram e UI conforme specs.

A IA pode substituir este código por uma abordagem melhor. Mudanças de contrato devem atualizar documentação, testes e ADR quando forem arquiteturalmente relevantes.
