# ADR-0001 — Núcleo independente de marketplace

**Status:** aceito

## Decisão
O domínio não conhece Amazon, AliExpress, Mercado Livre, Shopee ou qualquer loja. Integrações implementam portas.

## Motivo
Evita acoplamento, facilita testes e permite adicionar/retirar fontes.

## Consequência
Toda integração deve mapear seus dados para o contrato `OfferSnapshot`.
