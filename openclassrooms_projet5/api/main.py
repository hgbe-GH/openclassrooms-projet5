from fastapi import Depends, FastAPI, HTTPException
from loguru import logger

from openclassrooms_projet5.api.schemas import (
    HEALTH_RESPONSE_DEGRADED_EXAMPLE,
    HEALTH_RESPONSE_OK_EXAMPLE,
    PREDICTION_PAYLOAD_EXAMPLE,
    PREDICTION_RESPONSE_EXAMPLE,
    EmployeeFeatures,
    HealthResponse,
    PredictionResponse,
)
from openclassrooms_projet5.api.security import require_api_key
from openclassrooms_projet5.config import MODEL_PATH, is_authentication_enabled
from openclassrooms_projet5.db.service import log_prediction
from openclassrooms_projet5.db.session import (
    check_database_connection,
    is_database_logging_enabled,
)
from openclassrooms_projet5.modeling.predict import get_predictor

openapi_tags = [
    {
        "name": "monitoring",
        "description": "Supervision technique du service, du modele et de PostgreSQL.",
    },
    {
        "name": "prediction",
        "description": "Inference du modele d'attrition et persistance du logging.",
    },
]

app = FastAPI(
    title="OpenClassrooms Projet 5 - Attrition API",
    description="API FastAPI pour exposer le modele d'attrition du Projet 4.",
    version="0.1.0",
    openapi_tags=openapi_tags,
)


@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["monitoring"],
    summary="Verifier l'etat du service",
    description=(
        "Controle le chargement du modele, l'etat de PostgreSQL quand la journalisation "
        "est active, et le statut de l'authentification."
    ),
    responses={
        200: {
            "description": "Etat technique du service.",
            "content": {
                "application/json": {
                    "examples": {
                        "ok": {"summary": "Service operationnel", "value": HEALTH_RESPONSE_OK_EXAMPLE},
                        "degraded": {
                            "summary": "Service degrade",
                            "value": HEALTH_RESPONSE_DEGRADED_EXAMPLE,
                        },
                    }
                }
            },
        }
    },
)
def health() -> HealthResponse:
    details: list[str] = []
    model_loaded = False

    try:
        get_predictor()
        model_loaded = True
    except Exception as exc:
        details.append(f"model: {exc}")

    database_logging_enabled = is_database_logging_enabled()
    database_connected = False
    if database_logging_enabled:
        database_connected, database_detail = check_database_connection()
        if database_detail:
            details.append(f"database: {database_detail}")

    status = "ok" if model_loaded and (not database_logging_enabled or database_connected) else "degraded"

    return HealthResponse(
        status=status,
        model_loaded=model_loaded,
        model_path=str(MODEL_PATH),
        database_connected=database_connected,
        database_logging_enabled=database_logging_enabled,
        authentication_enabled=is_authentication_enabled(),
        detail=" | ".join(details) if details else None,
    )


@app.post(
    "/predict",
    response_model=PredictionResponse,
    tags=["prediction"],
    summary="Predire l'attrition d'un collaborateur",
    description=(
        "Valide le payload d'entree, calcule la prediction via l'artefact modele, "
        "puis persiste la trace dans PostgreSQL quand une configuration base est active. "
        "Si `API_KEY` est definie, l'appel doit fournir l'en-tete `X-API-Key`."
    ),
    responses={
        200: {
            "description": "Prediction calculee avec succes.",
            "content": {"application/json": {"example": PREDICTION_RESPONSE_EXAMPLE}},
        },
        401: {
            "description": "Cle API absente ou invalide.",
            "content": {
                "application/json": {"example": {"detail": "Invalid or missing API key."}}
            },
        },
        422: {
            "description": "Payload invalide ou champ obligatoire manquant.",
        },
        503: {
            "description": "Modele indisponible ou persistance PostgreSQL impossible.",
            "content": {
                "application/json": {
                    "examples": {
                        "model_missing": {
                            "summary": "Modele introuvable",
                            "value": {"detail": "Modele introuvable: [Errno 2] ..."},
                        },
                        "database_unavailable": {
                            "summary": "Base indisponible",
                            "value": {
                                "detail": "Database unavailable for prediction logging: database unavailable"
                            },
                        },
                    }
                }
            },
        },
    },
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {"application/json": {"example": PREDICTION_PAYLOAD_EXAMPLE}},
        }
    },
)
def predict(
    payload: EmployeeFeatures,
    _: None = Depends(require_api_key),
) -> PredictionResponse:
    database_logging_enabled = is_database_logging_enabled()
    if database_logging_enabled:
        database_connected, database_detail = check_database_connection()
        if not database_connected:
            detail = database_detail or "database unavailable"
            raise HTTPException(
                status_code=503,
                detail=f"Database unavailable for prediction logging: {detail}",
            )

    try:
        prediction = get_predictor().predict(payload.model_dump())
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=f"Modele introuvable: {exc}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        log_prediction(payload.model_dump(), prediction)
    except Exception as exc:
        logger.exception("Prediction logging failed.")
        raise HTTPException(
            status_code=503,
            detail=f"Prediction persistence failed: {exc}",
        ) from exc

    return PredictionResponse(
        probabilite_attrition=prediction.probabilite_attrition,
        prediction_attrition=prediction.prediction_attrition,
        threshold=prediction.threshold,
    )
