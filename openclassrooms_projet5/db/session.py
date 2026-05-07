from __future__ import annotations

from contextlib import contextmanager
from functools import lru_cache
from typing import Iterator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from openclassrooms_projet5.config import get_database_url, get_db_echo


@lru_cache
def _create_engine(database_url: str, db_echo: bool):
    return create_engine(
        database_url,
        echo=db_echo,
        future=True,
        pool_pre_ping=True,
    )


@lru_cache
def _create_session_factory(database_url: str, db_echo: bool):
    engine = _create_engine(database_url, db_echo)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def is_database_logging_enabled() -> bool:
    return bool(get_database_url())


def get_session_factory():
    database_url = get_database_url()
    if not database_url:
        return None

    return _create_session_factory(database_url, get_db_echo())


@contextmanager
def session_scope() -> Iterator[Session]:
    session_factory = get_session_factory()
    if session_factory is None:
        raise RuntimeError("Database logging is disabled.")

    session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def check_database_connection() -> tuple[bool, str | None]:
    session_factory = get_session_factory()
    if session_factory is None:
        return False, None

    try:
        with session_factory() as session:
            session.execute(text("SELECT 1"))
        return True, None
    except Exception as exc:
        return False, str(exc)


def clear_database_state() -> None:
    _create_session_factory.cache_clear()
    _create_engine.cache_clear()
