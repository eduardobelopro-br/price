from __future__ import annotations

import asyncio
import logging

from pricewatch.clock import SystemClock
from pricewatch.collectors.demo import DemoCollector
from pricewatch.collectors.generic import GenericStructuredDataCollector
from pricewatch.collectors.registry import CollectorRegistry
from pricewatch.logging_config import configure_logging
from pricewatch.net.http_client import SecureHttpClient
from pricewatch.notifications.dispatcher import OutboxDispatcher
from pricewatch.notifications.telegram import TelegramNotifier
from pricewatch.services.monitor import MonitorService
from pricewatch.settings import Settings
from pricewatch.storage.sqlite import SqliteStorage
from pricewatch.worker.scheduler import Worker

logger = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = 15


async def run(settings: Settings) -> None:
    storage = SqliteStorage(settings.database_path)
    try:
        http_client = SecureHttpClient(
            connect_timeout_seconds=settings.http_connect_timeout_seconds,
            read_timeout_seconds=settings.http_read_timeout_seconds,
            max_redirects=settings.http_max_redirects,
            max_response_bytes=settings.http_max_response_bytes,
        )
        registry = CollectorRegistry([DemoCollector(), GenericStructuredDataCollector(http_client)])
        clock = SystemClock()
        monitor = MonitorService(storage, registry, clock)
        worker = Worker(storage, monitor, clock)

        dispatcher: OutboxDispatcher | None = None
        if settings.telegram_enabled:
            if not settings.telegram_bot_token or not settings.telegram_chat_id:
                logger.warning("TELEGRAM_ENABLED is true but bot token/chat id are missing; notifications disabled")
            else:
                notifier = TelegramNotifier(settings.telegram_bot_token, settings.telegram_chat_id)
                dispatcher = OutboxDispatcher(storage, notifier, clock)

        logger.info("worker started (poll_interval_seconds=%s)", POLL_INTERVAL_SECONDS)
        while True:
            checked = await worker.run_once()
            if checked:
                logger.info("checked %s due product(s)", checked)
            if dispatcher is not None:
                sent = await dispatcher.dispatch_due()
                if sent:
                    logger.info("dispatched %s pending notification(s)", sent)
            await asyncio.sleep(POLL_INTERVAL_SECONDS)
    finally:
        storage.close()


def main() -> None:
    configure_logging()
    settings = Settings.from_env()
    try:
        asyncio.run(run(settings))
    except KeyboardInterrupt:
        logger.info("worker stopped")


if __name__ == "__main__":
    main()
