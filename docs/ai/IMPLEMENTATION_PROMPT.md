# PROMPT MESTRE — Implementar e evoluir o Price

Você é a IA engenheira responsável por implementar o projeto **Price** no repositório local:

```text
F:\Github\price
```

O Price é um monitor de preços **multimarketplace e multiloja**. Ele não deve ser arquitetado em torno de AliExpress, Amazon, Mercado Livre, Shopee ou qualquer plataforma específica.

## Regra principal de autonomia

Você **tem autorização para melhorar, refatorar, reorganizar ou substituir** o código-base, bibliotecas e detalhes arquiteturais deste pacote se identificar uma forma:

- mais eficiente;
- mais simples;
- mais segura;
- mais testável;
- mais robusta;
- mais sustentável;
- ou mais adequada ao repositório já existente.

Você não precisa seguir literalmente o código de referência.

Entretanto, uma melhoria não pode:

- remover requisitos P0 sem justificativa explícita;
- reduzir segurança;
- misturar dados demo e reais;
- transformar falha em preço fictício;
- quebrar compatibilidade silenciosamente;
- apagar trabalho já existente;
- contornar CAPTCHA, autenticação, anti-bot ou rate limits;
- declarar integração real sem teste ou fonte confiável.

Quando alterar uma decisão importante, atualize documentação e, se necessário, crie/atualize ADR.

## 1. Antes de programar

1. Entre em `F:\Github\price`.
2. Execute `git status`.
3. Inspecione a árvore, README, dependências e testes.
4. Não presuma que o repositório está vazio.
5. Preserve alterações locais.
6. Leia, nesta ordem:
   - `README.md`
   - `docs/product/PRD.md`
   - `docs/specs/PRODUCT_MONITORING.md`
   - `docs/architecture/ARCHITECTURE.md`
   - `docs/architecture/adr/*`
   - `docs/specs/API.md`
   - `docs/specs/DATABASE.md`
   - `docs/security/SECURITY.md`
   - `docs/testing/TESTING.md`
   - `docs/roadmap/ROADMAP.md`
   - `docs/reference/REFERENCE_IMPLEMENTATION.md`
7. Execute os testes existentes.
8. Produza um plano objetivo e então implemente. Não pare apenas no planejamento.

## 2. Missão

Entregar um MVP funcional que:

1. cadastre URLs de produtos;
2. monitore marketplaces e lojas por arquitetura de adaptadores;
3. obtenha preço apenas quando houver fonte suficientemente confiável;
4. armazene histórico;
5. aplique regras de preço-alvo e queda;
6. envie Telegram;
7. rode periodicamente sem navegador aberto;
8. possua API local e interface mínima;
9. registre erros e métricas operacionais;
10. seja seguro contra SSRF e entradas remotas maliciosas;
11. tenha testes reproduzíveis.

## 3. Arquitetura mínima esperada

O desenho de referência é:

```text
API/UI
  ↓
Application services
  ↓
Domain
  ↓
Ports
 ├── Storage
 ├── Collector
 ├── Notifier
 └── Clock
```

Se houver arquitetura melhor, implemente-a e registre a decisão.

### Collector contract

Todo coletor deve retornar sucesso ou erro estruturado. Não use exceções como fluxo normal.

Exemplo de contrato de referência:

```python
from typing import Protocol

class Collector(Protocol):
    name: str

    def supports(self, url: str) -> bool:
        ...

    async def collect(self, request: "CollectRequest") -> "CollectResult":
        ...
```

### Oferta normalizada

Utilize algo semanticamente equivalente a:

```python
@dataclass(frozen=True)
class OfferSnapshot:
    amount: Decimal
    currency: str
    observed_at: datetime
    source: str
    source_kind: Literal["real", "demo"]
    price_scope: Literal["item", "item_shipping", "landed"]
    title: str | None = None
    shipping_amount: Decimal | None = None
    tax_amount: Decimal | None = None
    total_amount: Decimal | None = None
    variant_key: str | None = None
    seller: str | None = None
    availability: str | None = None
    confidence: Literal["low", "medium", "high"] = "high"
```

Você pode melhorar o modelo, mantendo a intenção.

## 4. Coletores

Implemente:

### DemoCollector
Determinístico, isolado e explicitamente marcado como `demo`.

### GenericStructuredDataCollector
Suporte inicial a dados estruturados de produto/oferta quando publicados pela página.

Requisitos:

- JSON-LD;
- Product;
- Offer;
- AggregateOffer somente se for possível representar corretamente a ambiguidade;
- moeda obrigatória;
- variante ambígua deve ser sinalizada;
- preço inválido não deve ser aceito.

### CollectorRegistry
Seleciona coletores por capacidade/prioridade.

### Adapters futuros
Criar estrutura para adapters específicos por domínio/API, sem exigir que sejam todos implementados agora.

## 5. Cliente HTTP seguro

Este é P0.

Antes de fazer requisição:

```python
from urllib.parse import urlsplit

def validate_scheme(url: str) -> None:
    scheme = urlsplit(url).scheme.lower()
    if scheme not in {"http", "https"}:
        raise ValueError("unsupported scheme")
```

Isso é apenas o começo. Implemente proteção SSRF real:

- resolver DNS;
- bloquear loopback;
- bloquear private;
- bloquear link-local;
- bloquear multicast;
- bloquear reserved;
- bloquear unspecified;
- validar redirects;
- limitar redirects;
- limitar portas;
- timeouts;
- limite de bytes;
- user-agent identificável;
- não enviar segredos para hosts arbitrários.

Você pode escolher biblioteca HTTP diferente se facilitar esses controles.

## 6. Dinheiro e comparação

Nunca use `float`.

Exemplo:

```python
from dataclasses import dataclass
from decimal import Decimal

@dataclass(frozen=True)
class Money:
    amount: Decimal
    currency: str

    def __post_init__(self) -> None:
        if not self.currency or len(self.currency) != 3:
            raise ValueError("currency must be a 3-letter code")
```

A comparação exige moeda, variante e `price_scope` compatíveis.

## 7. Persistência

No MVP, SQLite é aceitável.

Implemente:

- products;
- snapshots;
- collection_attempts;
- rules;
- alert_events;
- outbox;
- migrations.

Não use float no banco.

Use transações e constraints. `alert_events.idempotency_key` deve ser unique.

Se o repositório já utiliza SQLAlchemy, SQLModel, Alembic ou outra solução madura, prefira integrar ao padrão existente em vez de duplicar infraestrutura.

## 8. Regras

Implemente:

### target_price

```python
trigger = current <= threshold
```

Dispare preferencialmente na transição de condição falsa para verdadeira.

### absolute_drop

```python
drop = reference - current
trigger = drop >= threshold
```

### percentage_drop

```python
pct = ((reference - current) / reference) * Decimal("100")
trigger = pct >= threshold
```

Evite alertas duplicados.

## 9. Worker

O worker precisa:

- buscar itens com `next_check_at <= now`;
- aplicar jitter;
- controlar concorrência;
- backoff em falha;
- respeitar limites por domínio;
- persistir tentativas;
- sobreviver a reinício;
- não exigir aba do navegador aberta.

Você pode usar loop asyncio no MVP ou uma fila/scheduler melhor se o repositório justificar. Não introduza Redis/Celery sem necessidade clara.

## 10. Telegram

Implementar notifier com:

- token via env;
- chat id via env/config;
- timeout;
- retry;
- outbox;
- registro de entregue/falha;
- mensagem contendo nome, preço anterior, atual, regra e URL.

Nunca logar token.

## 11. API

Implementar ao menos:

```text
GET    /health
POST   /api/v1/products
GET    /api/v1/products
GET    /api/v1/products/{id}
PATCH  /api/v1/products/{id}
POST   /api/v1/products/{id}/check
GET    /api/v1/products/{id}/history
POST   /api/v1/products/{id}/rules
GET    /api/v1/products/{id}/rules
DELETE /api/v1/rules/{id}
GET    /api/v1/alerts
```

Proteja endpoints administrativos com API key no MVP.

## 12. Interface

Pode ser server-rendered ou SPA simples. Priorize operação, não estética.

Mostrar:

- URL;
- loja/domínio;
- status;
- último preço;
- preço-alvo;
- última verificação;
- próxima verificação;
- erros recentes;
- histórico;
- regras;
- pausar/retomar;
- verificar agora.

## 13. Configuração de referência

Use nomes equivalentes:

```dotenv
PRICE_DATABASE_URL=sqlite:///./data/price.db
PRICE_API_KEY=change-me
PRICE_BIND_HOST=127.0.0.1
PRICE_BIND_PORT=8000
PRICE_DEFAULT_CHECK_INTERVAL_SECONDS=3600
PRICE_HTTP_CONNECT_TIMEOUT_SECONDS=5
PRICE_HTTP_READ_TIMEOUT_SECONDS=10
PRICE_HTTP_MAX_RESPONSE_BYTES=3000000
PRICE_HTTP_MAX_REDIRECTS=3

TELEGRAM_ENABLED=false
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
```

Não commitar `.env`.

## 14. Testes

Implemente os cenários definidos em `docs/testing/TESTING.md`.

Em especial, prove:

```python
def test_different_currencies_are_not_comparable():
    ...

def test_collection_failure_does_not_create_zero_price():
    ...

def test_same_alert_is_idempotent():
    ...

def test_localhost_is_blocked_by_url_safety():
    ...
```

CI nunca deve depender de preço real da internet.

## 15. Integrações específicas

Não implemente scraping evasivo.

Para cada nova integração real:

1. identificar fonte permitida/confiável;
2. criar adapter isolado;
3. mapear para contrato normalizado;
4. adicionar fixtures;
5. adicionar testes;
6. documentar limitações;
7. só então marcar a loja como suportada.

## 16. Qualidade

- type hints;
- funções pequenas;
- tratamento explícito de erros;
- logging estruturado;
- sem segredos hardcoded;
- sem `except Exception: pass`;
- sem sleeps desnecessários;
- sem duplicação de contrato;
- documentação junto da mudança.

## 17. Critério para você melhorar o código fornecido

Se identificar algo melhor que o código-base:

1. compare alternativas;
2. escolha a mais simples que atenda os requisitos;
3. implemente, não apenas sugira;
4. atualize testes;
5. atualize docs;
6. crie ADR se a mudança afetar arquitetura;
7. no relatório final explique:
   - o que mudou;
   - por quê;
   - benefício;
   - trade-off;
   - compatibilidade.

Não mantenha código inferior apenas porque estava no prompt.

## 18. Sequência recomendada

### Fase A
Domínio + persistência + migrações.

### Fase B
URL safety + HTTP + demo + JSON-LD + registry.

### Fase C
Monitor service + worker.

### Fase D
Rules + events + outbox + Telegram.

### Fase E
API + UI.

### Fase F
Hardening + Docker + CI + documentação.

Depois de cada fase execute testes relevantes.

## 19. Entrega final obrigatória

Antes de concluir:

1. execute suíte de testes;
2. execute lint/typecheck se configurados;
3. faça smoke test local;
4. mostre `git diff --stat`;
5. atualize documentação;
6. não afirme sucesso de comando não executado.

Entregue um relatório com:

```text
STATUS
IMPLEMENTADO
ARQUIVOS ALTERADOS
DECISÕES/ADRs
TESTES EXECUTADOS
RESULTADOS
COMANDOS PARA RODAR
LIMITAÇÕES
PRÓXIMO PASSO RECOMENDADO
```

## 20. Regra final

Seu trabalho é **implementar e validar**, não apenas produzir um plano.

Se encontrar uma abordagem melhor que esta especificação, você tem liberdade para adotá-la, desde que preserve o objetivo do produto, segurança, precisão dos preços, rastreabilidade e critérios de aceite.
