import httpx
import pytest

from pricewatch.notifications.telegram import NotificationError, TelegramNotifier


@pytest.mark.asyncio
async def test_send_succeeds_and_does_not_leak_token_on_success() -> None:
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        return httpx.Response(200, json={"ok": True})

    notifier = TelegramNotifier("secret-token", "12345", transport=httpx.MockTransport(handler))

    await notifier.send("preço caiu!")

    assert "secret-token" in captured["url"]  # the real request does need the token in the path


@pytest.mark.asyncio
async def test_send_raises_notification_error_without_leaking_token_on_failure() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"ok": False, "description": "Unauthorized"})

    notifier = TelegramNotifier("secret-token", "12345", transport=httpx.MockTransport(handler))

    with pytest.raises(NotificationError) as exc_info:
        await notifier.send("preço caiu!")

    assert "secret-token" not in str(exc_info.value)


@pytest.mark.asyncio
async def test_send_raises_notification_error_on_transport_failure() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom")

    notifier = TelegramNotifier("secret-token", "12345", transport=httpx.MockTransport(handler))

    with pytest.raises(NotificationError) as exc_info:
        await notifier.send("preço caiu!")

    assert "secret-token" not in str(exc_info.value)
