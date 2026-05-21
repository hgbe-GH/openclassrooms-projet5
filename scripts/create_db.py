from __future__ import annotations

import argparse

from alembic import command
from alembic.config import Config
from loguru import logger
from sqlalchemy import create_engine, text
from sqlalchemy.engine.url import make_url

from openclassrooms_projet5.config import PROJ_ROOT, get_database_url


def ensure_database_exists(database_url: str) -> None:
    url = make_url(database_url)
    if url.get_backend_name() != "postgresql":
        raise RuntimeError("create_db.py only supports PostgreSQL URLs.")

    if not url.database:
        raise RuntimeError("The PostgreSQL URL must include a database name.")

    admin_url = url.set(database="postgres")
    database_name = url.database.replace('"', '""')

    engine = create_engine(admin_url, isolation_level="AUTOCOMMIT", future=True)
    try:
        with engine.connect() as connection:
            database_exists = connection.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :database_name"),
                {"database_name": url.database},
            ).scalar_one_or_none()

            if database_exists:
                logger.info("Database '{}' already exists.", url.database)
                return

            connection.execute(text(f'CREATE DATABASE "{database_name}"'))
            logger.info("Database '{}' created.", url.database)
    finally:
        engine.dispose()


def run_migrations() -> None:
    alembic_config = Config(str(PROJ_ROOT / "alembic.ini"))
    command.upgrade(alembic_config, "head")
    logger.info("Alembic migrations applied.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create the PostgreSQL database if needed, then apply Alembic migrations.",
    )
    parser.add_argument(
        "--skip-create-db",
        action="store_true",
        help="Only apply Alembic migrations on an existing database.",
    )
    args = parser.parse_args()

    database_url = get_database_url()
    if not database_url:
        raise RuntimeError(
            "A PostgreSQL configuration is required. Set DATABASE_URL or POSTGRES_* variables.",
        )

    if not args.skip_create_db:
        ensure_database_exists(database_url)

    run_migrations()


if __name__ == "__main__":
    main()
