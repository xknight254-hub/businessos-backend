"""Override database with SQLite for testing. Must be imported before app."""
import os
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test.db"

import pytest
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from app.core.database import Base, get_db, get_engine, get_session_factory
from app.main import app


@pytest.fixture(autouse=True)
async def setup_db():
    # Reset engine for SQLite
    import app.core.database as db
    db._engine = create_async_engine(os.environ["DATABASE_URL"], echo=False)
    db._async_session_factory = async_sessionmaker(
        db._engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with db._engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield
    
    await db._engine.dispose()
    db._engine = None
    db._async_session_factory = None
    
    # Clean up test.db
    if os.path.exists("./test.db"):
        os.remove("./test.db")
