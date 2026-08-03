---
title: OpenClassrooms Projet 5 - Attrition API
colorFrom: red
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
---

# openclassrooms-projet5

API FastAPI de prediction d'attrition pour Futurisys.

## Fonctionnalites

- exposition du modele ML via une API HTTP documentee ;
- validation des entrees avec Pydantic ;
- persistance PostgreSQL des predictions ;
- securisation de `POST /predict` par cle API ;
- tests Pytest, couverture et lint Ruff ;
- CI/CD GitHub Actions ;
- preparation du deploiement sur Hugging Face Spaces.

## Architecture

```text
Client HTTP
    |
    v
FastAPI (/predict, /health, /docs)
    |
    +--> Validation Pydantic
    |
    +--> Preprocessing
    |
    +--> Artefact modele XGBoost
    |
    +--> Logging PostgreSQL (prediction_logs)
    |
    +--> Tests Pytest + couverture
    |
    +--> GitHub Actions
```

## Demarrage local

### Prerequis

- Python `3.12`
- `uv`
- Docker

### Installation

```bash
uv sync
cp .env.example .env
```

Variables principales :

- `MODEL_PATH`
- `API_KEY`
- `DATABASE_URL`
- ou `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, `POSTGRES_PORT`

### Base PostgreSQL

Demarrage standard :

```bash
docker compose up -d postgres
```

Si le port `5432` est deja occupe :

```bash
POSTGRES_PORT=55433 docker compose up -d postgres
POSTGRES_DB=attrition_api \
POSTGRES_USER=postgres \
POSTGRES_PASSWORD=postgres \
POSTGRES_HOST=localhost \
POSTGRES_PORT=55433 \
uv run python scripts/create_db.py --skip-create-db
```

Creation de la base et migrations :

```bash
uv run python scripts/create_db.py
```

Seed des donnees d'exemple :

```bash
uv run python scripts/seed_prediction_logs.py --truncate
```

### Lancer l'API

```bash
uv run uvicorn openclassrooms_projet5.api.main:app --reload
```

URLs locales :

- `http://127.0.0.1:8000/`
- `http://127.0.0.1:8000/health`
- `http://127.0.0.1:8000/docs`
- `http://127.0.0.1:8000/openapi.json`

## API

### `GET /health`

Controle :

- le chargement du modele ;
- la connexion PostgreSQL si elle est configuree ;
- l'etat de l'authentification.

Champs retournes :

- `status`
- `model_loaded`
- `model_path`
- `database_connected`
- `database_logging_enabled`
- `authentication_enabled`
- `detail`

### `POST /predict`

Role :

- valide le payload d'entree ;
- calcule `probabilite_attrition`, `prediction_attrition` et `threshold` ;
- persiste la prediction dans `prediction_logs` quand PostgreSQL est configure.

Authentification :

- header attendu : `X-API-Key`
- si `API_KEY` est absente, la route reste ouverte pour le developpement local ;
- si `API_KEY` est definie, une cle absente ou invalide renvoie `401`.

Payload d'exemple : `references/predict_payload_example.json`

Exemple d'appel :

```bash
curl -X POST "http://127.0.0.1:8000/predict" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: change-me-local" \
  -d @references/predict_payload_example.json
```

`change-me-local` est uniquement un placeholder de documentation. Utilisez une valeur
distincte et non versionnée dans `.env` ou dans le gestionnaire de secrets du runtime.

## Base de donnees PostgreSQL

Artefacts fournis :

- `scripts/create_db.py`
- `scripts/seed_prediction_logs.py`
- `alembic/versions/20260507_01_create_prediction_logs.py`
- `sql/create_prediction_logs.sql`
- `sql/example_prediction_logs.sql`
- `references/prediction_logs_examples.csv`
- `docs/docs/database.md`

La table `prediction_logs` stocke :

- le payload d'entree en `JSONB` ;
- la probabilite retournee ;
- la prediction binaire ;
- le seuil ;
- l'identifiant du modele ;
- la date de creation.

## Qualite

Commandes :

```bash
uv run pytest --cov=openclassrooms_projet5 --cov-report=term-missing --cov-report=xml
uv run ruff check .
```

Le perimetre de test couvre notamment :

- chargement du modele ;
- `GET /health` en mode `ok` et `degraded` ;
- `POST /predict` en succes, erreur de validation, erreur modele et erreur DB ;
- authentification par `X-API-Key` ;
- scripts et comportement de persistence ;
- integration PostgreSQL ;
- resolution de configuration.

## CI/CD

Workflow versionne :

- `.github/workflows/ci.yml`

Automatisation :

- installation de Python `3.12` et `uv` ;
- demarrage d'un service PostgreSQL ;
- restauration du modele chiffre ;
- migrations Alembic ;
- tests Pytest avec couverture ;
- lint Ruff ;
- publication de `coverage.xml` ;
- deploiement vers Hugging Face Spaces sur tag `v*`.

Secrets et variables requis :

- `MODEL_ARTIFACT_PASSPHRASE`
- `HF_TOKEN`
- `HF_SPACE`
- `API_KEY` si l'authentification doit etre activee en runtime

## Organisation du projet

```text
├── .github/workflows      <- Pipeline CI/CD
├── alembic                <- Migrations Alembic
├── docs                   <- Documentation MkDocs
├── models                 <- Artefacts ML locaux et chiffres
├── openclassrooms_projet5 <- Code source applicatif
├── references             <- Jeux d'exemples et payloads
├── scripts                <- Scripts DB et lancement runtime
├── sql                    <- Scripts SQL de reference
└── tests                  <- Tests unitaires et integration
```
