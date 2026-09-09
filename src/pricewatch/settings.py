from __future__ import annotations

import os
from dataclasses import dataclass


def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name)
    return int(raw) if raw else default


def _float_env(name: str, default: float) -> float:
    raw = os.environ.get(name)
    return float(raw) if raw else default


def _bool_env(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True, slots=True)
class Settings:
    database_path: str
    api_key: str
    bind_host: str
    bind_port: int
    default_check_interval_seconds: int
    http_connect_timeout_seconds: float
    http_read_timeout_seconds: float
    http_max_response_bytes: int
    http_max_redirects: int
    telegram_enabled: bool
    telegram_bot_token: str
    telegram_chat_id: str

    @classmethod
    def from_env(cls) -> Settings:
        database_url = os.environ.get("PRICE_DATABASE_URL", "sqlite:///./data/price.db")
        database_path = database_url.removeprefix("sqlite:///")
        return cls(
            database_path=database_path,
            api_key=os.environ.get("PRICE_API_KEY", "change-me"),
            bind_host=os.environ.get("PRICE_BIND_HOST", "127.0.0.1"),
            bind_port=_int_env("PRICE_BIND_PORT", 8000),
            default_check_interval_seconds=_int_env("PRICE_DEFAULT_CHECK_INTERVAL_SECONDS", 3600),
            http_connect_timeout_seconds=_float_env("PRICE_HTTP_CONNECT_TIMEOUT_SECONDS", 5.0),
            http_read_timeout_seconds=_float_env("PRICE_HTTP_READ_TIMEOUT_SECONDS", 10.0),
            http_max_response_bytes=_int_env("PRICE_HTTP_MAX_RESPONSE_BYTES", 3_000_000),
            http_max_redirects=_int_env("PRICE_HTTP_MAX_REDIRECTS", 3),
            telegram_enabled=_bool_env("TELEGRAM_ENABLED", False),
            telegram_bot_token=os.environ.get("TELEGRAM_BOT_TOKEN", ""),
            telegram_chat_id=os.environ.get("TELEGRAM_CHAT_ID", ""),
        )
