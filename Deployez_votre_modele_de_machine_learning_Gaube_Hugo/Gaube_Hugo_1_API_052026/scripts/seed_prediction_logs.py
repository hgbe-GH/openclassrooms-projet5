from __future__ import annotations

import argparse
import csv
from datetime import datetime
import json
from pathlib import Path
from uuid import UUID

from loguru import logger
from sqlalchemy import create_engine, text

from openclassrooms_projet5.config import PROJ_ROOT, get_database_url

DEFAULT_CSV_PATH = PROJ_ROOT / "references" / "prediction_logs_examples.csv"
SeedRow = dict[str, object]


def load_seed_rows(csv_path: Path) -> list[SeedRow]:
    with csv_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows: list[SeedRow] = []

        for raw_row in reader:
            rows.append(
                {
                    "id": UUID(raw_row["id"]),
                    "created_at": datetime.fromisoformat(raw_row["created_at"]),
                    "request_payload": json.loads(raw_row["request_payload_json"]),
                    "probabilite_attrition": float(raw_row["probabilite_attrition"]),
                    "prediction_attrition": int(raw_row["prediction_attrition"]),
                    "threshold": float(raw_row["threshold"]),
                    "model_identifier": raw_row["model_identifier"] or None,
                }
            )

    return rows


def seed_prediction_logs(
    database_url: str,
    rows: list[SeedRow],
    *,
    truncate: bool = False,
) -> int:
    engine = create_engine(database_url, future=True)

    try:
        with engine.begin() as connection:
            if truncate:
                connection.execute(text("TRUNCATE TABLE prediction_logs"))

            statement = text(
                """
                INSERT INTO prediction_logs (
                    id,
                    created_at,
                    request_payload,
                    probabilite_attrition,
                    prediction_attrition,
                    threshold,
                    model_identifier
                ) VALUES (
                    :id,
                    :created_at,
                    CAST(:request_payload AS JSONB),
                    :probabilite_attrition,
                    :prediction_attrition,
                    :threshold,
                    :model_identifier
                )
                ON CONFLICT (id) DO UPDATE SET
                    created_at = EXCLUDED.created_at,
                    request_payload = EXCLUDED.request_payload,
                    probabilite_attrition = EXCLUDED.probabilite_attrition,
                    prediction_attrition = EXCLUDED.prediction_attrition,
                    threshold = EXCLUDED.threshold,
                    model_identifier = EXCLUDED.model_identifier
                """
            )

            for row in rows:
                connection.execute(
                    statement,
                    {
                        **row,
                        "request_payload": json.dumps(row["request_payload"]),
                    },
                )
    finally:
        engine.dispose()

    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Seed example prediction_logs rows into an existing PostgreSQL database.",
    )
    parser.add_argument(
        "--csv-path",
        type=Path,
        default=DEFAULT_CSV_PATH,
        help="CSV file containing example prediction_logs rows.",
    )
    parser.add_argument(
        "--truncate",
        action="store_true",
        help="Delete existing prediction_logs rows before inserting the seed dataset.",
    )
    args = parser.parse_args()

    database_url = get_database_url()
    if not database_url:
        raise RuntimeError(
            "A PostgreSQL configuration is required. Set DATABASE_URL or POSTGRES_* variables.",
        )

    rows = load_seed_rows(args.csv_path)
    inserted_count = seed_prediction_logs(database_url, rows, truncate=args.truncate)
    logger.info(
        "Seeded {} prediction_logs rows from '{}'.",
        inserted_count,
        args.csv_path,
    )


if __name__ == "__main__":
    main()
