from __future__ import annotations

from openclassrooms_projet5.config import MODEL_PATH
from openclassrooms_projet5.db.models import PredictionLog
from openclassrooms_projet5.db.session import is_database_logging_enabled, session_scope
from openclassrooms_projet5.modeling.predict import PredictionResult


def log_prediction(payload: dict[str, object], prediction: PredictionResult) -> bool:
    if not is_database_logging_enabled():
        return False

    with session_scope() as session:
        session.add(
            PredictionLog(
                request_payload=payload,
                probabilite_attrition=prediction.probabilite_attrition,
                prediction_attrition=prediction.prediction_attrition,
                threshold=prediction.threshold,
                model_identifier=MODEL_PATH.name or None,
            )
        )

    return True
