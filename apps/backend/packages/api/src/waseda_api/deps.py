import os
from collections.abc import AsyncGenerator
from typing import Annotated

import sqlalchemy.ext.asyncio as sa_async
from fastapi import Depends
from sqlalchemy.ext.asyncio import create_async_engine

_engine: sa_async.AsyncEngine | None = None


def _get_database_url() -> str:
    if url := os.environ.get("DATABASE_URL"):
        return url
    password = os.environ["POSTGRES_PASSWORD"]
    user = os.environ.get("POSTGRES_USER", "postgres")
    host = os.environ.get("POSTGRES_HOST", "localhost")
    port = os.environ.get("POSTGRES_PORT", "5432")
    db = os.environ.get("POSTGRES_DB", "waseda_syllabus")
    return f"postgresql+psycopg://{user}:{password}@{host}:{port}/{db}"


def get_engine() -> sa_async.AsyncEngine:
    global _engine
    if _engine is None:
        _engine = create_async_engine(_get_database_url(), pool_pre_ping=True)
    return _engine


async def get_conn() -> AsyncGenerator[sa_async.AsyncConnection, None]:
    async with get_engine().connect() as conn:
        yield conn


DbConn = Annotated[sa_async.AsyncConnection, Depends(get_conn)]
