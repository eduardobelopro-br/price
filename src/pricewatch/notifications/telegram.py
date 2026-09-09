from __future__ import annotations

import httpx

from pricewatch.domain.models import AlertEvent, Product, Rule

_RULE_LABELS = {
    "target_price": "preço-alvo atingido",
    "absolute_drop": "queda de preço",
    "percentage_drop": "queda percentual de preço",
    "new_low": "novo menor preço",
}


class NotificationError(RuntimeError):
    pass


def format_alert_message(product: Product, rule: Rule, event: AlertEvent) -> str:
    title = product.title or product.url
    rule_label = _RULE_LABELS.get(rule.kind, rule.kind)
    return (
        f"{title}\n"
        f"Regra: {rule_label}\n"
        f"Preço anterior: {event.reference_price} {event.currency}\n"
        f"Preço atual: {event.current_price} {event.currency}\n"
        f"{product.url}"
    )


class TelegramNotifier:
    """Sends alert messages via the Telegram Bot API. Never logs the bot
    token: request failures are translated into NotificationError with a
    sanitized message before they can bubble up to a logger.
    """

    name = "telegram"

    def __init__(
        self,
        bot_token: str,
        chat_id: str,
        *,
        timeout_seconds: float = 10.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._bot_token = bot_token
        self._chat_id = chat_id
        self._timeout = httpx.Timeout(timeout_seconds)
        self._transport = transport

    async def send(self, message: str) -> None:
        url = f"https://api.telegram.org/bot{self._bot_token}/sendMessage"
        try:
            async with httpx.AsyncClient(timeout=self._timeout, transport=self._transport) as client:
                response = await client.post(url, json={"chat_id": self._chat_id, "text": message})
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            raise NotificationError(f"telegram API returned status {status_code}") from None
        except httpx.HTTPError as exc:
            raise NotificationError(f"telegram request failed: {type(exc).__name__}") from None
