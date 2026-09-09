# Price

Monitor de preços multiloja e multimarketplace.

**Destino pretendido:** `F:\Github\price`  
**Modelo de documentação:** docs-as-code  
**Estado:** especificação + código-base de referência para implementação/evolução por outra IA.

## Objetivo

O Price recebe URLs de produtos de marketplaces, e-commerces e lojas próprias, coleta ofertas comparáveis, mantém histórico e gera alertas quando o preço atende a uma regra configurada.

A aplicação **não promete compatibilidade universal**. Quando uma página não puder ser monitorada com confiabilidade, o sistema deve informar isso claramente em vez de inventar ou inferir preços.

## Mapa da documentação

- [PRD](docs/product/PRD.md)
- [Arquitetura](docs/architecture/ARCHITECTURE.md)
- [ADRs](docs/architecture/adr/)
- [Spec de monitoramento](docs/specs/PRODUCT_MONITORING.md)
- [API](docs/specs/API.md)
- [Banco](docs/specs/DATABASE.md)
- [Segurança](docs/security/SECURITY.md)
- [Testes](docs/testing/TESTING.md)
- [Deploy](docs/operations/DEPLOYMENT.md)
- [Roadmap](docs/roadmap/ROADMAP.md)
- [Prompt mestre para outra IA](docs/ai/IMPLEMENTATION_PROMPT.md)
- [Código-base](docs/reference/REFERENCE_IMPLEMENTATION.md)

## Estrutura

```text
price/
├─ docs/
│  ├─ product/
│  ├─ architecture/
│  │  └─ adr/
│  ├─ specs/
│  ├─ security/
│  ├─ testing/
│  ├─ operations/
│  ├─ roadmap/
│  ├─ reference/
│  └─ ai/
├─ src/pricewatch/
├─ tests/
├─ examples/
├─ pyproject.toml
├─ Dockerfile
├─ docker-compose.yml
├─ .env.example
└─ README.md
```

## Princípios

1. Marketplace é um detalhe de integração, não do domínio.
2. Preço desconhecido nunca vira zero.
3. Dinheiro usa decimal e moeda explícita.
4. A mesma oferta só é comparada quando produto, variante, moeda e escopo são compatíveis.
5. Dados simulados e reais nunca são misturados.
6. Erros de coleta são persistidos e observáveis.
7. O monitoramento funciona sem navegador aberto.
8. Integrações específicas podem ser adicionadas como plugins/adaptadores.
9. A implementação deve respeitar limites, autenticação e políticas dos sites.
10. A documentação deve mudar no mesmo commit que altera contratos ou arquitetura.

## Início rápido do código-base

Duplo clique em `start.bat` na raiz do repositório: cria o `.venv` e o `.env` se ainda não
existirem, instala as dependências, inicia o worker numa janela separada e a API em
`http://127.0.0.1:8000` (abre o navegador automaticamente).

Ou manualmente:

```powershell
cd F:\Github\price
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
python -m uvicorn pricewatch.api.app:app --reload --host 127.0.0.1 --port 8000
```

Execute os testes:

```powershell
python -m pytest
```

O código-base é deliberadamente pequeno. Ele demonstra contratos e extensibilidade; a IA executora deve completar o MVP descrito no PRD.
