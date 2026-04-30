# openclassrooms-projet5

<a target="_blank" href="https://cookiecutter-data-science.drivendata.org/">
    <img src="https://img.shields.io/badge/CCDS-Project%20template-328F97?logo=cookiecutter" />
</a>

API de deploiement du modele attrition Projet 4 pour Futurisys.

## Demarrage rapide

Ce depot est initialise avec Cookiecutter Data Science v2 pour le Projet 5
OpenClassrooms. Il utilisera le modele d'attrition XGBoost du Projet 4 lors de
la prochaine etape d'integration.

```bash
uv sync
uv run pytest
uv run ruff check .
```

Lancer l'API en local :

```bash
uv run uvicorn openclassrooms_projet5.api.main:app --reload
```

Endpoints disponibles :

- `GET /health` : verifie que l'API repond et que le modele est chargeable.
- `POST /predict` : retourne `probabilite_attrition`, `prediction_attrition` et `threshold`
  pour un employe.
- `GET /docs` : documentation Swagger/OpenAPI generee par FastAPI.

## Modele local

L'artefact cible du Projet 4 est copie localement pour les tests et l'API :

```text
models/attrition_xgboost_pipeline.joblib
```

Le fichier source vient de :

```text
/home/hgbe/openclassrooms/projet4/models/attrition_xgboost_pipeline.joblib
```

Les fichiers de donnees, les modeles serialises et les secrets locaux sont ignores
par Git. Utiliser `.env.example` comme base pour creer un fichier `.env` local non
versionne.

## Project Organization

```
├── README.md          <- The top-level README for developers using this project.
├── data
│   ├── external       <- Data from third party sources.
│   ├── interim        <- Intermediate data that has been transformed.
│   ├── processed      <- The final, canonical data sets for modeling.
│   └── raw            <- The original, immutable data dump.
│
├── docs               <- A default mkdocs project; see www.mkdocs.org for details
│
├── models             <- Trained and serialized models, model predictions, or model summaries
│
├── notebooks          <- Jupyter notebooks. Naming convention is a number (for ordering),
│                         the creator's initials, and a short `-` delimited description, e.g.
│                         `1.0-jqp-initial-data-exploration`.
│
├── pyproject.toml     <- Project configuration file with package metadata for 
│                         openclassrooms_projet5 and configuration for tools like black
│
├── references         <- Data dictionaries, manuals, and all other explanatory materials.
│
├── reports            <- Generated analysis as HTML, PDF, LaTeX, etc.
│   └── figures        <- Generated graphics and figures to be used in reporting
│
└── openclassrooms_projet5   <- Source code for use in this project.
    │
    ├── __init__.py             <- Makes openclassrooms_projet5 a Python module
    │
    ├── config.py               <- Store useful variables and configuration
    │
    ├── dataset.py              <- Scripts to download or generate data
    │
    ├── features.py             <- Code to create features for modeling
    │
    ├── modeling                
    │   ├── __init__.py 
    │   ├── predict.py          <- Code to run model inference with trained models          
    │   └── train.py            <- Code to train models
    │
    └── plots.py                <- Code to create visualizations
```

--------
