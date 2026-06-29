# openclassrooms-projet5 documentation

## Objectif

Ce depot expose un modele de prediction d'attrition via FastAPI, avec persistance
PostgreSQL, tests, securisation par cle API et preparation du deploiement sur Hugging Face
Spaces.

## Contenu

- demarrage local et commandes reproductibles ;
- API FastAPI et documentation Swagger/OpenAPI ;
- base PostgreSQL, migrations et jeu d'exemples ;
- securisation par `X-API-Key` ;
- workflow GitHub Actions et deploiement Space Docker.

## Commandes rapides

```bash
uv sync
cp .env.example .env
uv run python scripts/create_db.py
uv run python scripts/seed_prediction_logs.py --truncate
uv run pytest --cov=openclassrooms_projet5 --cov-report=term-missing --cov-report=xml
uv run ruff check .
uv run uvicorn openclassrooms_projet5.api.main:app --reload
```

## Points d'appui

- `docs/docs/database.md`
- `docs/docs/security.md`
- `docs/docs/getting-started.md`
