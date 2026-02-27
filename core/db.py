from __future__ import annotations

from contextlib import contextmanager
import logging
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from core.config import get_settings

Base = declarative_base()
logger = logging.getLogger(__name__)


_engine = None
_SessionLocal = None


def get_engine():
    global _engine
    if _engine is None:
        db_url = get_settings().resolved_database_url
        _engine = create_engine(db_url, future=True, pool_pre_ping=True)
        try:
            parsed = make_url(db_url)
            logger.info(
                "db_engine_initialized",
                extra={
                    "db_driver": parsed.drivername,
                    "db_host": parsed.host or "",
                    "db_name": parsed.database or "",
                },
            )
        except Exception:
            logger.info("db_engine_initialized")
    return _engine


def get_session_factory():
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine(), autoflush=False, autocommit=False, future=True)
        logger.info("db_session_factory_initialized")
    return _SessionLocal


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    session = get_session_factory()()
    try:
        yield session
        session.commit()
        logger.info("db_session_committed")
    except Exception:
        session.rollback()
        logger.exception("db_session_rolled_back")
        raise
    finally:
        session.close()
