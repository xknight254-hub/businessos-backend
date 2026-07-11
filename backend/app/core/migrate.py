"""Startup migration hook (runs inside the container before uvicorn).

Creates all tables idempotently via SQLAlchemy metadata. Real schema
evolution uses Alembic (see migrations/); this is the zero-downtime
bootstrap so a fresh Postgres is ready on first launch.
"""
from __future__ import annotations

import asyncio

from app.core.database import init_db
from app.core.logging import get_logger

logger = get_logger("businessos.migrate")


async def run() -> None:
    await init_db()
    logger.info("migrate", extra={"event": "tables_ready"})


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
