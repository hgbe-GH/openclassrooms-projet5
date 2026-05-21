# openclassrooms-projet5 documentation!

## Description

API de deploiement du modele attrition Projet 4 pour Futurisys.

## Contenu

- demarrage local ;
- base PostgreSQL et jeu d'exemples ;
- securisation par cle API ;
- deploiement via GitHub Actions et Hugging Face Spaces.

## Commandes rapides

Utiliser directement `uv` pour les taches courantes :

```bash
uv sync
uv run python scripts/create_db.py
uv run python scripts/seed_prediction_logs.py --truncate
uv run pytest --cov=openclassrooms_projet5 --cov-report=term-missing --cov-report=xml
uv run ruff check .
```
