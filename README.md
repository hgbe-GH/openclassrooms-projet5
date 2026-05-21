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

Ce projet transforme un modele de machine learning en service FastAPI testable,
documente, securise et deployable. Le depot couvre :

- l'exposition du modele via une API HTTP ;
- la persistance PostgreSQL des predictions ;
- la validation et la tracabilite des appels ;
- la qualite logicielle avec Pytest, couverture et Ruff ;
- la preparation du deploiement sur Hugging Face Spaces via GitHub Actions.

## Demarrage rapide

Les dependances sont declarees dans `pyproject.toml` et verrouillees dans `uv.lock`.

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

Inserer le jeu d'exemples versionne :

```bash
uv run python scripts/seed_prediction_logs.py --truncate
```

Verifier les lignes inserees :

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

- `GET /health` : verifie l'etat du service, du chargement modele, de PostgreSQL et de
  l'authentification.
- `POST /predict` : valide le payload, calcule la prediction et persiste la trace quand
  PostgreSQL est configure.
- `GET /docs` : documentation Swagger/OpenAPI generee par FastAPI.

Exemple d'appel authentifie :

```bash
curl -X POST "http://127.0.0.1:8000/predict" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: change-me-for-local-dev" \
  -d @payload.json
```

## Processus de traitement et stockage des donnees

Le cycle de vie d'une prediction est le suivant :

1. FastAPI recoit un payload JSON sur `POST /predict`.
2. Pydantic valide les champs obligatoires, les types et les bornes.
3. Le pipeline charge le modele XGBoost serialise et calcule :
   `probabilite_attrition`, `prediction_attrition` et `threshold`.
4. Si PostgreSQL est configure, l'API verifie d'abord la disponibilite de la base.
5. Le service de persistance enregistre dans `prediction_logs` :
   - le payload d'entree ;
   - le score du modele ;
   - la prediction binaire ;
   - le seuil ;
   - l'identifiant de l'artefact modele.
6. La reponse HTTP renvoie uniquement les sorties utiles au consommateur de l'API.

Ce flux permet de separer :

- la validation d'entree ;
- la logique de prediction ;
- la tracabilite base de donnees ;
- la supervision via `/health`.

## Authentification et securisation

Le projet implemente une authentification simple par cle API :

- variable d'environnement : `API_KEY`
- header attendu : `X-API-Key`
- route protegee : `POST /predict`

Comportement :

- si `API_KEY` n'est pas definie, l'authentification reste desactivee pour faciliter le
  developpement local ;
- si `API_KEY` est definie, une cle absente ou invalide renvoie `401 Unauthorized`.

Bonnes pratiques appliquees :

- les secrets locaux restent hors Git ;
- `.env.example` sert de base au fichier `.env` local ;
- les secrets de CI/CD sont geres via GitHub Secrets ;
- les cles doivent varier entre `dev`, `test` et `prod` ;
- le modele chiffre (`.enc`) peut etre versionne, mais pas la passphrase de dechiffrement.

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
- `scripts/seed_prediction_logs.py` : insere le dataset d'exemples versionne ;
- `alembic/versions/20260507_01_create_prediction_logs.py` : migration versionnee ;
- `sql/create_prediction_logs.sql` : script SQL brut de creation ;
- `sql/example_prediction_logs.sql` : exemple d'insertion SQL manuelle ;
- `references/prediction_logs_examples.csv` : dataset d'exemples pour le seed ;
- `docs/docs/database.md` : documentation et schema UML/ER.

## Besoins analytiques couverts

La table `prediction_logs` ne constitue pas un dashboard a elle seule, mais elle fournit
un socle directement exploitable pour l'analyse et le reporting. Elle permet notamment :

- l'audit d'un appel API et la tracabilite du payload ayant conduit a une prediction ;
- le suivi du volume de predictions dans le temps ;
- la distribution des probabilites d'attrition renvoyees par le modele ;
- le suivi du taux de predictions positives ;
- la comparaison des resultats entre versions d'artefacts modele.

Ce positionnement repond a la demande du projet : preparer une base interrogeable pour des
usages analytiques ou un tableau de bord ulterieur, sans ajouter ici un frontend BI.

## Tests et couverture

Le projet couvre :

- le chargement du modele ;
- `/health` ;
- `/predict` ;
- les erreurs de validation ;
- l'authentification par cle API ;
- la persistance PostgreSQL quand elle est active ;
- le seed du dataset d'exemples et son idempotence ;
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
- `scripts/start_api.sh` pour restaurer le modele chiffre puis lancer Uvicorn ;
- variable GitHub `HF_SPACE` deja configuree ;
- secrets GitHub `HF_TOKEN` et `MODEL_ARTIFACT_PASSPHRASE` deja configures.

Variables/secrets attendus cote deploiement :

- `HF_TOKEN`
- `HF_SPACE`
- `MODEL_ARTIFACT_PASSPHRASE`
- `API_KEY` si l'on veut forcer l'authentification en ligne
- `HF_SPACE_URL` si l'on veut documenter explicitement l'URL publique finale

URLs verifiees :

- UI Hugging Face : `https://huggingface.co/spaces/hgbe-gh/openclassrooms-projet5`
- runtime : `https://hgbe-gh-openclassrooms-projet5.hf.space`

Etat verifie le `21 mai 2026` :

- `GET /health` repond `200` ;
- `GET /docs` repond `200` ;
- `POST /predict` sans cle repond `401` ;
- `POST /predict` avec la cle runtime configuree repond `200`.

Le runtime public actuellement expose :

- un modele charge avec succes ;
- une authentification activee ;
- une persistance PostgreSQL desactivee cote Space.

Exemple `curl` aligne sur le runtime public :

```bash
curl -X POST "https://hgbe-gh-openclassrooms-projet5.hf.space/predict" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: <API_KEY>" \
  -d @payload.json
```

## Verifications realisees

Verifications locales deja executees :

- `uv run ruff check .`
- `uv run pytest --cov=openclassrooms_projet5 --cov-report=term-missing --cov-report=xml`
- tests d'integration PostgreSQL avec base active
- verification du seed PostgreSQL et de son idempotence
- execution reelle de `uv run python scripts/seed_prediction_logs.py --truncate`

Verifications distantes executees le `21 mai 2026` :

- `https://huggingface.co/spaces/hgbe-gh/openclassrooms-projet5` : `200`
- `https://hgbe-gh-openclassrooms-projet5.hf.space/health` : `200`
- `https://hgbe-gh-openclassrooms-projet5.hf.space/docs` : `200`
- `POST /predict` sans cle : `401`
- `POST /predict` avec cle runtime configuree : `200`

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
├── references             <- Jeux d'exemples et artefacts de soutenance
├── reports                <- Supports HTML
├── scripts                <- Scripts utilitaires (DB, seed, deploiement)
└── sql                    <- Scripts SQL de reference
```
