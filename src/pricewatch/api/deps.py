from __future__ import annotations

from fastapi import Depends, Header, HTTPException, Request, status

from pricewatch.clock import Clock
from pricewatch.services.monitor import MonitorService
from pricewatch.settings import Settings
from pricewatch.storage.sqlite import SqliteStorage


def get_settings(request: Request) -> Settings:
    return request.app.state.settings  # type: ignore[no-any-return]


def get_storage(request: Request) -> SqliteStorage:
    return request.app.state.storage  # type: ignore[no-any-return]


def get_clock(request: Request) -> Clock:
    return request.app.state.clock  # type: ignore[no-any-return]


def get_monitor(request: Request) -> MonitorService:
    return request.app.state.monitor  # type: ignore[no-any-return]


def require_api_key(
    x_api_key: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> None:
    if not x_api_key or x_api_key != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid or missing API key"
        )
