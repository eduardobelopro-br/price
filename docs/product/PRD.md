# PRD — Price

## 1. Visão

O Price é uma aplicação para acompanhar preços de produtos em marketplaces, lojas virtuais e sites próprios por URL, mantendo histórico e notificando o usuário quando uma condição de preço for satisfeita.

## 2. Problema

Usuários acompanham o mesmo produto em diferentes lojas e precisam verificar manualmente promoções. Comparadores externos nem sempre cobrem lojas menores, variantes específicas, preço total, frete ou regras personalizadas.

## 3. Objetivos

### P0 — MVP

- cadastrar URL de produto;
- identificar domínio/loja;
- tentar obter uma oferta confiável;
- armazenar preço, moeda, variante e timestamp;
- registrar falhas sem substituir o último preço válido;
- permitir preço-alvo;
- permitir alerta por redução absoluta e percentual;
- histórico;
- worker periódico independente da interface;
- notificação Telegram;
- API local autenticada;
- interface simples;
- coletor demo para testes;
- coletor genérico baseado em dados estruturados quando disponíveis;
- arquitetura de adaptadores para integrações específicas.

### P1

- e-mail;
- múltiplos canais de alerta;
- menor preço de 7/30/90 dias;
- comparação entre lojas;
- tags e listas;
- pausa automática de URLs com falhas recorrentes;
- suporte PostgreSQL;
- browser automation somente quando permitido e realmente necessário.

### Fora do escopo inicial

- burlar CAPTCHA;
- contornar login, anti-bot ou rate limit;
- prometer suporte a qualquer URL;
- comprar automaticamente;
- usar contas ou credenciais sem autorização;
- inferir preço a partir de texto ambíguo quando não houver confiança suficiente.

## 4. Personas

### Usuário individual

Quer acompanhar alguns produtos e receber aviso quando atingirem valor interessante.

### Usuário avançado

Acompanha dezenas ou centenas de URLs e quer histórico, filtros e regras.

### Operador/administrador

Mantém integrações, diagnostica falhas e acompanha saúde dos coletores.

## 5. Jornada principal

1. Usuário cola uma URL.
2. Sistema valida e identifica a fonte.
3. Coletor obtém uma oferta ou retorna erro estruturado.
4. Usuário escolhe regra de alerta.
5. Worker atualiza periodicamente.
6. Histórico é persistido.
7. Motor de regras avalia nova amostra.
8. Um evento idempotente é criado.
9. O canal envia a notificação.
10. Usuário acessa histórico e status.

## 6. Requisitos funcionais

### RF-001 Cadastro
Aceitar apenas `http` e `https`. Normalizar URL sem destruir identificadores necessários.

### RF-002 Oferta
Uma oferta deve conter, quando conhecida: título, preço, moeda, disponibilidade, variante, vendedor, frete, impostos, preço total, URL canônica e origem.

### RF-003 Confiabilidade
Cada observação deve indicar método e nível de confiança. Sem confiança suficiente, gerar erro de coleta.

### RF-004 Histórico
Novas observações são append-only. Correções administrativas devem ser auditáveis.

### RF-005 Regras
Suportar:
- `target_price`;
- `absolute_drop`;
- `percentage_drop`;
- opcionalmente `new_low`.

### RF-006 Idempotência
A mesma condição não pode gerar notificações duplicadas continuamente enquanto o preço permanecer inalterado.

### RF-007 Worker
Rodar fora da interface. Reinício não pode perder produtos cadastrados.

### RF-008 Notificação
Telegram no MVP, com tentativas e registro de status.

### RF-009 Estado
Produto: `active`, `paused`, `unsupported`, `error`.

### RF-010 Integrações
Novas lojas devem entrar por adaptador sem alterar o motor de regras.

## 7. Requisitos não funcionais

- Python 3.11+ na referência.
- Dinheiro com `Decimal`.
- UTC internamente.
- Banco transacional.
- Logs estruturados.
- Segredos via ambiente.
- Proteção SSRF.
- Timeout e tamanho máximo de resposta.
- Testes sem depender de preço real na internet.
- API com documentação OpenAPI.
- Execução local em Windows e Docker.

## 8. Métricas

- taxa de coletas válidas;
- taxa de erro por domínio;
- latência de coleta;
- tempo até alerta;
- notificações entregues;
- falsos alertas conhecidos;
- produtos pausados por falha.

## 9. Critérios de aceite do MVP

O MVP está pronto quando:

1. uma URL demo é cadastrada;
2. o worker registra ao menos duas observações;
3. uma queda dispara exatamente um alerta;
4. reiniciar serviço não perde dados;
5. uma URL inválida/privada é rejeitada;
6. falha de coleta não grava preço zero;
7. testes P0 passam;
8. documentação e configuração reproduzem a execução.
