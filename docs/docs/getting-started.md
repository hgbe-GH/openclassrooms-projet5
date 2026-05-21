# Demarrage

## Prerequis

- Python 3.12
- `uv`
- Docker et Docker Compose

## Installation

```bash
uv sync
cp .env.example .env
```

## Base de donnees

Demarrer PostgreSQL :

```bash
docker compose up -d postgres
```

Creer la base et appliquer les migrations :

```bash
uv run python scripts/create_db.py
```

Inserer le dataset d'exemples :

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

Documentation interactive :

- `http://127.0.0.1:8000/docs`
- `http://127.0.0.1:8000/health`
