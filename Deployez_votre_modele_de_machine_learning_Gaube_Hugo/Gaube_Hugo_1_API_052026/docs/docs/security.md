# Authentification et securisation

## Mecanisme retenu

L'API supporte une authentification simple par cle API HTTP :

- header attendu : `X-API-Key`
- variable d'environnement : `API_KEY`
- endpoint protege : `POST /predict`

`GET /health` reste accessible sans authentification pour permettre un controle de
disponibilite simple.

## Comportement

- si `API_KEY` n'est pas definie, l'authentification est desactivee ;
- si `API_KEY` est definie, une cle absente ou invalide renvoie `401 Unauthorized`.

## Gestion des environnements

Le projet distingue trois contextes :

- `dev` : configuration locale via `.env` non versionne ;
- `test` : execution automatisee via GitHub Actions ;
- `production` : deploiement Hugging Face Spaces pousse depuis GitHub Actions.

Bonnes pratiques retenues :

- ne jamais versionner une vraie cle ;
- partir de `.env.example` pour le developpement local ;
- faire varier les cles entre `dev`, `test` et `prod` ;
- utiliser GitHub Secrets pour les valeurs sensibles du pipeline.

## Secrets et artefacts

Secrets/variables utilises par le projet :

- `API_KEY` : protection de `POST /predict` ;
- `MODEL_ARTIFACT_PASSPHRASE` : dechiffrement du modele chiffre ;
- `HF_TOKEN` : push du depot vers Hugging Face Spaces ;
- `HF_SPACE` : chemin du Space cible ;
- `DATABASE_URL` ou `POSTGRES_*` : configuration base de donnees.

Le README ne suppose plus que ces secrets soient deja configures. Ils sont requis pour que
la CI/CD et le runtime cible fonctionnent, mais doivent etre verifies explicitement au
moment du deploiement.

Le modele versionne pour la CI/CD et le deploiement est l'artefact chiffre
`models/attrition_xgboost_pipeline.joblib.enc`. La passphrase de dechiffrement reste hors
du depot.

## Limites assumees

Le mecanisme retenu est volontairement simple pour ce projet : il ne remplace pas une
gestion d'identite complete, mais il suffit pour demontrer :

- la protection d'un endpoint sensible ;
- la separation entre endpoint public de supervision et endpoint metier ;
- la gestion correcte des secrets entre developpement, CI et deploiement.
