from __future__ import annotations

import re
import sqlite3
from datetime import UTC, datetime
from importlib import resources
from typing import Any


def _migration_files() -> list[Any]:
    migrations_dir = resources.files("pricewatch.storage.migrations")
    files = [f for f in migrations_dir.iterdir() if f.name.endswith(".sql")]
    return sorted(files, key=lambda f: f.name)


def _version_of(filename: str) -> int:
    match = re.match(r"(\d+)_", filename)
    if not match:
        raise ValueError(f"migration file must start with a numeric version: {filename}")
    return int(match.group(1))


def apply_migrations(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL
        )
        """
    )
    applied = {row[0] for row in connection.execute("SELECT version FROM schema_migrations")}

    for migration_file in _migration_files():
        version = _version_of(migration_file.name)
        if version in applied:
            continue

        script = migration_file.read_text(encoding="utf-8")
        connection.executescript(script)
        connection.execute(
            "INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)",
            (version, datetime.now(UTC).isoformat()),
        )
        connection.commit()
