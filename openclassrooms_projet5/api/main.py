from fastapi import FastAPI, HTTPException
from loguru import logger

from openclassrooms_projet5.api.schemas import (
    EmployeeFeatures,
    HealthResponse,
    PredictionResponse,
)
from openclassrooms_projet5.config import MODEL_PATH
from openclassrooms_projet5.db.service import log_prediction
from openclassrooms_projet5.db.session import (
    check_database_connection,
    is_database_logging_enabled,
)
from openclassrooms_projet5.modeling.predict import get_predictor

app = FastAPI(
    title="OpenClassrooms Projet 5 - Attrition API",
    description="API FastAPI pour exposer le modele d'attrition du Projet 4.",
    version="0.1.0",
)


@app.get("/health", response_model=HealthResponse)
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
        detail=" | ".join(details) if details else None,
    )


@app.post("/predict", response_model=PredictionResponse)
def predict(payload: EmployeeFeatures) -> PredictionResponse:
    try:
        prediction = get_predictor().predict(payload.model_dump())
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=f"Modele introuvable: {exc}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        log_prediction(payload.model_dump(), prediction)
    except Exception:
        logger.exception("Prediction logging failed.")

    return PredictionResponse(
        probabilite_attrition=prediction.probabilite_attrition,
        prediction_attrition=prediction.prediction_attrition,
        threshold=prediction.threshold,
    )
