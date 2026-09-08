# Arquitetura

## Visão

Arquitetura em camadas com domínio independente de fornecedor.

```text
UI / API
   |
Application Services
   |
Domain
   |
Ports --------------------------------
 |             |            |         |
Storage     Collectors   Notifiers   Clock
 |             |            |
SQLite      Generic +     Telegram
/Postgres    adapters
```

## Componentes

### API
CRUD de produtos, regras, histórico e operações administrativas.

### Domain
Entidades e value objects sem dependência de HTTP, FastAPI ou banco.

### Collectors
Implementam `Collector`. A seleção pode considerar domínio, URL e prioridade.

### Generic collector
Tenta metadados estruturados publicados pela própria página. Não deve fazer parsing agressivo de HTML como regra principal.

### Specific adapters
Implementações por plataforma quando fonte autorizada/API/documentação permitir.

### Monitor service
Orquestra coleta, valida comparabilidade, persiste observações e chama regras.

### Rules engine
Compara observação atual com referência válida e cria eventos idempotentes.

### Outbox
Persistência de notificações antes do envio, evitando perda entre transação e chamada externa.

### Worker
Seleciona itens vencidos, aplica jitter/backoff e processa lotes.

## Extensibilidade

Interface mínima:

```python
class Collector(Protocol):
    name: str
    def supports(self, url: str) -> bool: ...
    async def collect(self, request: CollectRequest) -> CollectResult: ...
```

O `CollectResult` é `OfferSnapshot | CollectError`. Exceções não tratadas são bugs; falhas esperadas são valores estruturados.

## Comparabilidade

Antes de calcular queda, validar:

- mesma moeda;
- mesma identidade/variante quando definida;
- mesmo escopo (`item`, `item+shipping`, `landed`);
- mesma quantidade;
- preço não expirado ou inválido;
- fonte não demo quando produto real.

## Dados

SQLite para MVP single-node. PostgreSQL é opção para concorrência/escala. A camada de persistência deve evitar SQL espalhado pelo domínio.

## Observabilidade

Logs devem conter `product_id`, `collector`, `domain`, `run_id` e categoria de erro, nunca tokens.
