# Spec — Monitoramento de produto

## Product

```text
id
url
canonical_url?
domain
title?
status
currency_preference?
variant_key?
price_scope
check_interval_seconds
last_checked_at?
next_check_at
created_at
updated_at
```

## OfferSnapshot

```json
{
  "observed_at": "2026-09-08T12:00:00Z",
  "source": "jsonld",
  "source_kind": "real",
  "title": "Produto X",
  "amount": "199.90",
  "currency": "BRL",
  "shipping_amount": null,
  "tax_amount": null,
  "total_amount": null,
  "price_scope": "item",
  "variant_key": null,
  "seller": null,
  "availability": "in_stock",
  "confidence": "high",
  "raw_reference": null
}
```

## CollectError

Campos:
- `code`;
- `message`;
- `retryable`;
- `http_status?`;
- `collector`;
- `observed_at`.

Códigos sugeridos:
`unsupported`, `blocked`, `timeout`, `dns_error`, `invalid_price`, `currency_missing`, `variant_ambiguous`, `authentication_required`, `rate_limited`, `network_error`.

## Regras

### target_price
Dispara quando `current <= threshold` e a condição muda de falsa para verdadeira.

### absolute_drop
Dispara quando `reference - current >= amount`.

### percentage_drop
`((reference-current)/reference)*100 >= threshold`.

A referência padrão é a observação válida anterior comparável. Futuramente pode ser preço inicial ou média.

## Idempotency key

Sugestão:

```text
sha256(product_id | rule_id | current_snapshot_id | transition)
```

## Frequência

Mínimo configurável sugerido: 15 minutos no MVP, com jitter. Adaptadores podem impor intervalos maiores.

## Falhas consecutivas

Backoff exponencial limitado. Após limiar configurável, manter o produto visível e sinalizar erro; não apagar histórico.
