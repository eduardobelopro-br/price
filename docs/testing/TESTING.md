# Estratégia de testes

## Unitários

T-01 Decimal sem erro de arredondamento.  
T-02 Regra target: transição falsa→verdadeira.  
T-03 Target não duplica no mesmo snapshot.  
T-04 Queda absoluta.  
T-05 Queda percentual.  
T-06 Moedas diferentes não comparam.  
T-07 Variantes diferentes não comparam.  
T-08 Escopos diferentes não comparam.  
T-09 Preço zero inválido quando não é preço real permitido.  
T-10 Erro de coleta não cria snapshot.

## Coletores

T-11 Demo determinístico.  
T-12 Generic JSON-LD Product/Offer.  
T-13 Moeda ausente retorna erro.  
T-14 Oferta ambígua retorna erro ou exige seleção.  
T-15 Página sem dados suportados retorna unsupported.

## Segurança

T-16 Bloqueia `localhost`.  
T-17 Bloqueia `127.0.0.1`.  
T-18 Bloqueia RFC1918.  
T-19 Bloqueia redirect para IP privado.  
T-20 Bloqueia `file://`.  
T-21 Limita tamanho de resposta.

## Integração

T-22 Cadastro → coleta demo → snapshot.  
T-23 Queda → alert event → outbox.  
T-24 Reinício preserva dados.

## Regra de CI

Nenhum teste de CI deve depender de preço real de marketplace. Integrações reais têm testes contratados/opt-in.
