from __future__ import annotations

import time
from contextlib import contextmanager
from dataclasses import dataclass
from functools import lru_cache
from typing import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from core.config import database_url


@dataclass
class QueryStats:
    total: int = 0
    slow: int = 0
    p50_ms: float = 0.0
    p95_ms: float = 0.0


_query_samples: list[float] = []


@lru_cache(maxsize=1)
def get_engine():
    engine = create_engine(database_url(), pool_pre_ping=True)

    @event.listens_for(engine, "before_cursor_execute")
    def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        context._query_start_time = time.perf_counter()

    @event.listens_for(engine, "after_cursor_execute")
    def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        elapsed = (time.perf_counter() - context._query_start_time) * 1000
        _query_samples.append(elapsed)
        if len(_query_samples) > 1000:
            _query_samples.pop(0)

    return engine


@lru_cache(maxsize=1)
def get_session_factory():
    return sessionmaker(bind=get_engine(), autoflush=False, autocommit=False)


@contextmanager
def db_session() -> Iterator[Session]:
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_query_stats() -> QueryStats:
    if not _query_samples:
        return QueryStats()
    ordered = sorted(_query_samples)
    p50 = ordered[int(len(ordered) * 0.5)]
    p95 = ordered[int(len(ordered) * 0.95)]
    return QueryStats(
        total=len(_query_samples),
        slow=sum(1 for s in _query_samples if s > 250),
        p50_ms=round(p50, 2),
        p95_ms=round(p95, 2),
    )
