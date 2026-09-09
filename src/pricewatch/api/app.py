from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse
from starlette.staticfiles import StaticFiles

from pricewatch.api.errors import register_exception_handlers
from pricewatch.api.routers import alerts, products, rules
from pricewatch.api.ui import UI_HTML
from pricewatch.clock import SystemClock
from pricewatch.collectors.demo import DemoCollector
from pricewatch.collectors.generic import GenericStructuredDataCollector
from pricewatch.collectors.registry import CollectorRegistry
from pricewatch.logging_config import configure_logging
from pricewatch.net.http_client import SecureHttpClient
from pricewatch.services.monitor import MonitorService
from pricewatch.settings import Settings
from pricewatch.storage.sqlite import SqliteStorage

STATIC_DIR = Path(__file__).parent / "static"

CONTENT_SECURITY_POLICY = (
    "default-src 'self'; script-src 'self'; style-src 'self'; "
    "img-src 'self' data:; connect-src 'self'; object-src 'none'; "
    "base-uri 'none'; frame-ancestors 'none'"
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    settings = Settings.from_env()
    storage = SqliteStorage(settings.database_path)
    http_client = SecureHttpClient(
        connect_timeout_seconds=settings.http_connect_timeout_seconds,
        read_timeout_seconds=settings.http_read_timeout_seconds,
        max_redirects=settings.http_max_redirects,
        max_response_bytes=settings.http_max_response_bytes,
    )
    registry = CollectorRegistry([DemoCollector(), GenericStructuredDataCollector(http_client)])
    clock = SystemClock()

    app.state.settings = settings
    app.state.storage = storage
    app.state.clock = clock
    app.state.monitor = MonitorService(storage, registry, clock)

    try:
        yield
    finally:
        storage.close()


app = FastAPI(title="Price", version="0.1.0", lifespan=lifespan)
register_exception_handlers(app)
app.include_router(products.router, prefix="/api/v1")
app.include_router(rules.router, prefix="/api/v1")
app.include_router(alerts.router, prefix="/api/v1")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.middleware("http")
async def add_security_headers(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    response = await call_next(request)
    response.headers["Content-Security-Policy"] = CONTENT_SECURITY_POLICY
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def ui() -> str:
    return UI_HTML
