---
title: OpenClassrooms Projet 5 - Attrition API
emoji: 🧠
colorFrom: red
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
---

# openclassrooms-projet5

<a target="_blank" href="https://cookiecutter-data-science.drivendata.org/">
    <img src="https://img.shields.io/badge/CCDS-Project%20template-328F97?logo=cookiecutter" />
</a>

API de deploiement du modele d'attrition du Projet 4 pour Futurisys.

## Objectif

Ce projet transforme le modele de machine learning du Projet 4 en une API FastAPI
testee, documentee, securisee et prete a etre integree dans un pipeline CI/CD.
Le depot couvre l'exposition du modele, la persistance PostgreSQL des predictions,
la qualite logicielle et la preparation du deploiement Hugging Face Spaces.

## Demarrage rapide

Les dependances sont declarees dans `pyproject.toml` et verrouillees dans `uv.lock`,
ce qui remplace un `requirements.txt` classique.

Initialiser l'environnement :

```bash
uv sync
cp .env.example .env
```

Demarrer PostgreSQL puis creer la base et les tables :

```bash
docker compose up -d postgres
uv run python scripts/create_db.py
```

Lancer les verifications :

```bash
uv run pytest --cov=openclassrooms_projet5 --cov-report=term-missing --cov-report=xml
uv run ruff check .
```

Lancer l'API en local :

```bash
uv run uvicorn openclassrooms_projet5.api.main:app --reload
```

## API

Endpoints disponibles :

- `GET /health` : verifie que l'API repond, que le modele est chargeable et expose
  l'etat de PostgreSQL et de l'authentification.
- `POST /predict` : retourne `probabilite_attrition`, `prediction_attrition` et
  `threshold` pour un employe. Si PostgreSQL est configure, la prediction doit aussi
  etre persistable en base.
- `GET /docs` : documentation Swagger/OpenAPI generee par FastAPI.

Exemple d'appel authentifie :

```bash
curl -X POST "http://127.0.0.1:8000/predict" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: change-me-for-local-dev" \
  -d @payload.json
```

## Authentification et securisation

Le projet implemente une authentification simple par cle API :

- variable d'environnement : `API_KEY`
- header attendu : `X-API-Key`
- route protegee : `POST /predict`

Si `API_KEY` n'est pas definie, l'authentification reste desactivee pour faciliter
le travail local. Pour la soutenance, la configuration cible est d'executer l'API
avec une cle definie.

Les secrets locaux restent hors Git. Utiliser `.env.example` comme base pour le
fichier `.env` local.

## Modele local

Artefact attendu par l'API :

```text
models/attrition_xgboost_pipeline.joblib
```

Artefact chiffre versionne pour la CI/CD et le deploiement :

```text
models/attrition_xgboost_pipeline.joblib.enc
```

Le secret `MODEL_ARTIFACT_PASSPHRASE` permet de dechiffrer cet artefact dans GitHub
Actions ou dans Hugging Face Spaces.

## PostgreSQL et migrations

Variables prises en charge :

- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `POSTGRES_HOST`
- `POSTGRES_PORT`
- `DATABASE_URL`
- `DB_ECHO` (optionnel)

`DATABASE_URL` est prioritaire. Si elle n'est pas definie, l'application peut la
reconstruire a partir des variables `POSTGRES_*`.

Artefacts BDD fournis :

- `scripts/create_db.py` : cree la base si besoin puis applique les migrations ;
- `alembic/versions/20260507_01_create_prediction_logs.py` : migration versionnee ;
- `sql/create_prediction_logs.sql` : script SQL brut de creation ;
- `sql/example_prediction_logs.sql` : exemple d'insertion ;
- `references/prediction_logs_examples.csv` : exemples d'entrees/sorties ;
- `docs/docs/database.md` : documentation et schema UML/ER.

## Tests et couverture

Le projet couvre :

- le chargement du modele ;
- `/health` ;
- `/predict` ;
- l'erreur de validation ;
- la persistence PostgreSQL quand elle est active ;
- l'authentification par cle API ;
- la resolution de configuration.

Commande recommandee :

```bash
uv run pytest --cov=openclassrooms_projet5 --cov-report=term-missing --cov-report=xml
```

Le rapport XML est genere dans `coverage.xml` et peut etre collecte par la CI.

## CI/CD

Le fichier `.github/workflows/ci.yml` configure GitHub Actions :

- execution automatique sur `push`, `pull_request` et tags `v*` ;
- installation de Python 3.12 et `uv` ;
- demarrage d'un service PostgreSQL pour les tests d'integration ;
- restauration du modele depuis l'artefact chiffre ;
- application des migrations via `scripts/create_db.py` ;
- lancement des tests Pytest avec couverture ;
- lancement de `ruff` ;
- publication de `coverage.xml` en artefact ;
- deploiement vers Hugging Face Spaces sur tag `v*`.

## Deploiement Hugging Face Spaces

Le depot est prepare pour un Space Docker :

- front matter Hugging Face en tete de ce `README.md` ;
- `Dockerfile` pour construire l'API ;
- `scripts/start_api.sh` pour restaurer le modele chiffre puis lancer Uvicorn.

Variables/secrets attendus cote deploiement :

- `HF_TOKEN`
- `HF_SPACE`
- `MODEL_ARTIFACT_PASSPHRASE`
- `API_KEY` si l'on veut forcer l'authentification en ligne

URL de reference du Space une fois configure :

- UI Hugging Face : `https://huggingface.co/spaces/<namespace>/<space>`
- runtime : `https://<namespace>-<space>.hf.space`

Je n'ai pas pu confirmer une URL publique existante depuis le depot seul. La
configuration de deploiement est maintenant complete, mais la preuve finale depend
encore des variables/secrets du projet distant.

## Git et versionnement

Workflow retenu :

- `main` : branche stable ;
- `develop` : branche d'integration ;
- `feature/<nom-court>` : branche par fonctionnalite ;
- tags de version au format `vMAJOR.MINOR.PATCH`.

Les conventions completes sont decrites dans `docs/standards.md`.

## Support de soutenance

Artefacts utiles pour l'oral :

- `reports/mentor_status_2026-05-07.html` : support mentor intermediaire ;
- `reports/soutenance_projet5.html` : support de soutenance synthese ;
- `docs/docs/database.md` et `docs/docs/security.md` : appui technique.

## Project Organization

```text
├── .github/workflows      <- Pipeline CI/CD GitHub Actions
├── alembic                <- Migrations Alembic
├── docs                   <- Documentation MkDocs
├── models                 <- Artefacts ML locaux et chiffres
├── openclassrooms_projet5 <- Code source applicatif
├── references             <- Exemples et artefacts de soutenance
├── reports                <- Supports HTML
├── scripts                <- Scripts utilitaires (DB, deploiement)
└── sql                    <- Scripts SQL de reference
```
