# Authentification et securisation

## Mecanisme retenu

L'API supporte une authentification simple par cle API HTTP :

- header attendu : `X-API-Key`
- variable d'environnement : `API_KEY`
- endpoint protege : `POST /predict`

`GET /health` reste accessible sans authentification pour permettre un controle de disponibilite simple.

## Comportement

- si `API_KEY` n'est pas definie, l'authentification est desactivee ;
- si `API_KEY` est definie, une cle absente ou invalide renvoie `401 Unauthorized`.

## Recommandations

- ne jamais versionner la vraie cle ;
- definir la cle dans `.env` en local ;
- utiliser un secret GitHub Actions pour les environnements CI/CD et deploiement ;
- faire varier les cles entre `dev`, `test` et `prod`.
