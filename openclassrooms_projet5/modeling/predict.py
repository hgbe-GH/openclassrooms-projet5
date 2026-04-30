from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import joblib
import pandas as pd

from openclassrooms_projet5.config import MODEL_PATH
from openclassrooms_projet5.modeling.preprocessing import prepare_prediction_features


@dataclass(frozen=True)
class PredictionResult:
    probabilite_attrition: float
    prediction_attrition: int
    threshold: float


@dataclass(frozen=True)
class AttritionPredictor:
    pipeline: Any
    threshold: float
    feature_columns: list[str]

    @classmethod
    def from_path(cls, model_path: Path) -> "AttritionPredictor":
        artifact = joblib.load(model_path)
        if not isinstance(artifact, dict):
            raise ValueError("L'artefact modele doit etre un dictionnaire.")

        missing_keys = {"pipeline", "threshold", "feature_columns"}.difference(artifact)
        if missing_keys:
            raise ValueError(f"Cles manquantes dans l'artefact modele: {sorted(missing_keys)}")

        return cls(
            pipeline=artifact["pipeline"],
            threshold=float(artifact["threshold"]),
            feature_columns=list(artifact["feature_columns"]),
        )

    def predict(self, features: dict[str, Any]) -> PredictionResult:
        df = pd.DataFrame([features])
        X = prepare_prediction_features(df, self.feature_columns)
        probability = float(self.pipeline.predict_proba(X)[:, 1][0])
        prediction = int(probability >= self.threshold)

        return PredictionResult(
            probabilite_attrition=probability,
            prediction_attrition=prediction,
            threshold=self.threshold,
        )


@lru_cache
def _load_predictor(model_path: str) -> AttritionPredictor:
    return AttritionPredictor.from_path(Path(model_path))


def get_predictor(model_path: Path | str | None = None) -> AttritionPredictor:
    resolved_model_path = Path(model_path or MODEL_PATH).resolve()
    return _load_predictor(str(resolved_model_path))
