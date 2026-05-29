---
title: OpenClassrooms Projet 5 - Attrition API
colorFrom: red
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
---

# openclassrooms-projet5

API FastAPI de deploiement d'un modele de prediction d'attrition pour Futurisys.

Le depot couvre les criteres principaux du Projet 5 OpenClassrooms :

- exposition du modele ML via une API HTTP documentee ;
- validation des entrees avec Pydantic ;
- persistance PostgreSQL des predictions ;
- securisation de `POST /predict` par cle API ;
- tests Pytest, couverture et lint Ruff ;
- CI/CD GitHub Actions ;
- preparation du deploiement Hugging Face Spaces ;
- supports HTML pour le suivi mentor et la soutenance.

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
    |
    +--> Hugging Face Space Docker
```

## Soutenance

Le point d'entree recommande pour l'oral est un tableau de bord local qui centralise :

- la verification du Space public ;
- la prediction authentifiee ;
- la trace PostgreSQL locale ;
- la qualite logicielle.

References utiles :

- tableau de bord local : URL annoncee par `./scripts/start_demo.sh`
- Space public : `https://hgbe-gh-openclassrooms-projet5.hf.space`
- Swagger / OpenAPI : `https://hgbe-gh-openclassrooms-projet5.hf.space/docs`
- cle de demo : `X-API-Key: cle-test`

Lancement recommande :

```bash
./scripts/start_demo.sh
```

Ce script :

- active `ENABLE_DEMO_UI=true` ;
- demarre l'API locale si necessaire ;
- annonce l'URL locale du tableau de bord.

Etat verifie le `29 mai 2026` :

- `GET /health` : `200`
- `GET /docs` : `200`
- `POST /predict` sans cle : `401`
- `POST /predict` avec `X-API-Key: cle-test` : `200`

Si le Space ralentit, le tableau de bord local et `/docs` restent disponibles en secours.

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

Variables locales principales :

- `MODEL_PATH`
- `API_KEY`
- `DATABASE_URL`
- ou `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, `POSTGRES_PORT`

### PostgreSQL

Le projet fonctionne sans base, mais la journalisation PostgreSQL est necessaire pour
demonstrer completement le livrable BDD.

Demarrage standard :

```bash
docker compose up -d postgres
```

Si le port `5432` est deja occupe, utiliser une surcharge locale :

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

Verification rapide :

```bash
uv run python - <<'PY'
from sqlalchemy import create_engine, text
from openclassrooms_projet5.config import get_database_url

engine = create_engine(get_database_url(), future=True)
with engine.connect() as connection:
    result = connection.execute(text("SELECT COUNT(*) FROM prediction_logs"))
    print({"prediction_logs_count": result.scalar_one()})
engine.dispose()
PY
```

### Lancer l'API

```bash
uv run uvicorn openclassrooms_projet5.api.main:app --reload
```

URLs locales :

- `http://127.0.0.1:8000/health`
- `http://127.0.0.1:8000/docs`
- `http://127.0.0.1:8000/openapi.json`

## Verification locale

Payload d'exemple versionne : `references/predict_payload_example.json`

Appel authentifie :

```bash
curl -X POST "http://127.0.0.1:8000/predict" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: cle-test" \
  -d @references/predict_payload_example.json
```

Trace PostgreSQL :

```bash
uv run python - <<'PY'
from sqlalchemy import create_engine, text
from openclassrooms_projet5.config import get_database_url

engine = create_engine(get_database_url(), future=True)
with engine.connect() as connection:
    result = connection.execute(
        text(
            "SELECT created_at, prediction_attrition, model_identifier "
            "FROM prediction_logs ORDER BY created_at DESC LIMIT 3"
        )
    )
    for row in result.mappings():
        print(dict(row))
engine.dispose()
PY
```

Qualite et couverture :

```bash
uv run pytest --cov=openclassrooms_projet5 --cov-report=term-missing --cov-report=xml
uv run ruff check .
```

Le snapshot de demonstration reste disponible si une capture d'etat prealable est utile :

```bash
uv run python scripts/demo_snapshot.py
```

## API et OpenAPI

### `GET /health`

Role :

- verifie le chargement du modele ;
- indique si PostgreSQL est configure et connecte ;
- indique si l'authentification est active.

Sortie :

- `status`
- `model_loaded`
- `model_path`
- `database_connected`
- `database_logging_enabled`
- `authentication_enabled`
- `detail`

### `POST /predict`

Role :

- valide le payload Pydantic ;
- calcule `probabilite_attrition`, `prediction_attrition` et `threshold` ;
- persiste la prediction dans `prediction_logs` quand PostgreSQL est configure.

Authentification :

- header attendu : `X-API-Key`
- comportement :
  - si `API_KEY` est absente, la route reste ouverte pour le developpement local ;
  - si `API_KEY` est definie, une cle absente ou invalide renvoie `401`.

Erreurs documentees dans Swagger/OpenAPI :

- `401` : cle API absente ou invalide ;
- `422` : payload invalide ;
- `503` : modele introuvable ou persistance indisponible.

Les exemples de requete et de reponse sont exposes dans :

- `http://127.0.0.1:8000/docs`
- `http://127.0.0.1:8000/openapi.json`

## Base de donnees PostgreSQL

Artefacts BDD fournis :

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

Usages analytiques deja couverts :

- audit d'un appel API ;
- suivi du volume de predictions ;
- distribution des scores ;
- comparaison de versions d'artefacts modele.

## Tests, couverture et qualite

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
- resolution de configuration ;
- smoke tests des commandes auxiliaires.

## CI/CD

Le workflow versionne est :

- `.github/workflows/ci.yml`

Il automatise :

- installation de Python `3.12` et `uv` ;
- demarrage d'un service PostgreSQL ;
- restauration du modele chiffre ;
- migrations Alembic ;
- tests Pytest avec couverture ;
- lint Ruff ;
- publication de `coverage.xml` ;
- deploiement vers Hugging Face Spaces sur tag `v*`.

Secrets et variables requis pour le pipeline :

- `MODEL_ARTIFACT_PASSPHRASE`
- `HF_TOKEN`
- `HF_SPACE`
- `API_KEY` si l'authentification doit etre activee en runtime

## Hugging Face Spaces

Le depot est prepare pour un Space Docker avec :

- front matter Hugging Face en tete de ce `README.md` ;
- `Dockerfile` ;
- `scripts/start_api.sh` ;
- landing HTML minimal sur `GET /` ;
- artefact modele chiffre `models/attrition_xgboost_pipeline.joblib.enc`.

Etat de verification date du `29 mai 2026` :

- page Space : `https://huggingface.co/spaces/hgbe-gh/openclassrooms-projet5` repond `200`
- runtime public : `https://hgbe-gh-openclassrooms-projet5.hf.space/health` repond `200`
- documentation publique : `https://hgbe-gh-openclassrooms-projet5.hf.space/docs` repond `200`
- `POST /predict` sans cle repond `401`
- `POST /predict` avec `X-API-Key: cle-test` repond `200`

Choix de demonstration :

- le Space public sert de preuve de deploiement et de demonstration API ;
- PostgreSQL reste demontre localement pour la preuve de persistance ;
- la meme cle API est utilisee en local et sur le Space pour eviter toute friction pendant l'oral.

La verification la plus simple pendant l'oral reste l'usage du tableau de bord local, qui
rejoue ces controles contre le Space sans multiplier les commandes manuelles.

## Preuves par competence OpenClassrooms

| Competence / attendu | Preuve dans le depot |
| --- | --- |
| Configurer l'environnement de travail | `pyproject.toml`, `uv.lock`, `.env.example`, `README.md` |
| Definir le traitement et le stockage des donnees | `openclassrooms_projet5/api/main.py`, `openclassrooms_projet5/db/service.py`, `docs/docs/database.md` |
| Etablir et executer un processus de test du SGBD | `tests/test_db_integration.py`, `scripts/create_db.py`, `scripts/seed_prediction_logs.py` |
| Installer et parametrer PostgreSQL | `compose.yaml`, `alembic/`, `sql/`, `README.md` |
| Mettre en place l'authentification | `openclassrooms_projet5/api/security.py`, `tests/test_api.py`, `docs/docs/security.md` |
| Modeliser une infrastructure compatible SI | `Dockerfile`, `.github/workflows/ci.yml`, `scripts/start_api.sh` |
| Structurer l'architecture des donnees | `openclassrooms_projet5/db/models.py`, `docs/docs/database.md`, `references/prediction_logs_examples.csv` |
| Prouver la qualite logicielle | `tests/`, `pytest`, `ruff`, `README.md` |

## Supports de suivi et de soutenance

Artefacts versionnes :

- `reports/mentor_status_2026-05-07.html`
- `reports/soutenance_projet5.html`
- `docs/docs/database.md`
- `docs/docs/security.md`

## Organisation du projet

```text
├── .github/workflows      <- Pipeline CI/CD
├── alembic                <- Migrations Alembic
├── docs                   <- Documentation MkDocs
├── models                 <- Artefacts ML locaux et chiffres
├── openclassrooms_projet5 <- Code source applicatif
├── references             <- Jeux d'exemples et payloads
├── reports                <- Supports HTML de mentorat et soutenance
├── scripts                <- Scripts DB et lancement runtime
├── sql                    <- Scripts SQL de reference
└── tests                  <- Tests unitaires et integration
```
