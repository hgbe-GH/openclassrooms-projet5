from fastapi import FastAPI, HTTPException

from openclassrooms_projet5.api.schemas import (
    EmployeeFeatures,
    HealthResponse,
    PredictionResponse,
)
from openclassrooms_projet5.config import MODEL_PATH
from openclassrooms_projet5.modeling.predict import get_predictor

app = FastAPI(
    title="OpenClassrooms Projet 5 - Attrition API",
    description="API FastAPI pour exposer le modele d'attrition du Projet 4.",
    version="0.1.0",
)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    try:
        get_predictor()
    except Exception as exc:
        return HealthResponse(
            status="degraded",
            model_loaded=False,
            model_path=str(MODEL_PATH),
            detail=str(exc),
        )

    return HealthResponse(
        status="ok",
        model_loaded=True,
        model_path=str(MODEL_PATH),
    )


@app.post("/predict", response_model=PredictionResponse)
def predict(payload: EmployeeFeatures) -> PredictionResponse:
    try:
        prediction = get_predictor().predict(payload.model_dump())
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=f"Modele introuvable: {exc}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return PredictionResponse(
        probabilite_attrition=prediction.probabilite_attrition,
        prediction_attrition=prediction.prediction_attrition,
        threshold=prediction.threshold,
    )
