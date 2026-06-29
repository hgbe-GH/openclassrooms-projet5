# Demarrage

## Prerequis

- Python 3.12
- `uv`
- Docker

## Installation

```bash
uv sync
cp .env.example .env
```

## Base de donnees

Demarrage standard :

```bash
docker compose up -d postgres
```

Si `5432` est deja occupe :

```bash
POSTGRES_PORT=55433 docker compose up -d postgres
```

Creation / migrations :

```bash
uv run python scripts/create_db.py
```

Seed :

```bash
uv run python scripts/seed_prediction_logs.py --truncate
```

## Qualite

```bash
uv run pytest --cov=openclassrooms_projet5 --cov-report=term-missing --cov-report=xml
uv run ruff check .
```

## Execution locale

```bash
uv run uvicorn openclassrooms_projet5.api.main:app --reload
```

## Endpoints utiles

- `http://127.0.0.1:8000/docs`
- `http://127.0.0.1:8000/health`
- `http://127.0.0.1:8000/openapi.json`
