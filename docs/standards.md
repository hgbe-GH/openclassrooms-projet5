# Standards projet

## Gestion Git

- `main` contient uniquement du code stable et validé.
- `develop` sert de branche d'intégration avant fusion vers `main`.
- Les fonctionnalités sont développées dans des branches `feature/<nom-court>`.
- Les corrections peuvent utiliser `fix/<nom-court>`.
- Les commits doivent être descriptifs et suivre un préfixe simple : `feat:`, `fix:`,
  `test:`, `docs:`, `ci:`, `chore:`.
- Les versions livrables sont taguées avec le format `vMAJOR.MINOR.PATCH`, par exemple
  `v0.1.0`.

## Validation avant fusion

Avant toute fusion dans `develop` ou `main`, exécuter :

```bash
uv sync
uv run pytest
uv run ruff check .
```

Sur GitHub, ouvrir une Pull Request vers `develop` ou `main`. Le workflow GitHub
Actions exécute automatiquement les tests et le lint sur chaque push et pull request.

## Environnements et secrets

- `dev` : environnement local avec `.env`, non versionné.
- `test` : environnement GitHub Actions qui exécute tests et lint.
- `production` : déploiement Hugging Face Spaces déclenché par un tag `v*`.

Secrets et variables attendus pour GitHub Actions :

- `MODEL_ARTIFACT_PASSPHRASE` : phrase secrete permettant de dechiffrer
  `models/attrition_xgboost_pipeline.joblib.enc` pendant la CI.
- `HF_TOKEN` : token Hugging Face avec droit d'écriture sur le Space.
- `HF_SPACE` : variable GitHub contenant le chemin du Space Hugging Face, par exemple
  `username/space-name`.

## Standards ML

- Les modèles sérialisés et données réelles ne sont pas versionnés dans Git.
- Les artefacts locaux sont placés dans `models/`.
- Les entrées API sont validées avec Pydantic avant prédiction.
- Les tests doivent couvrir au minimum le chargement du modèle, `/health`, `/predict`
  et les erreurs de validation.
