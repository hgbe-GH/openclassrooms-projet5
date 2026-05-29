from fastapi.testclient import TestClient
import pytest

import openclassrooms_projet5.api.main as app_main
import openclassrooms_projet5.api.security as api_security
from openclassrooms_projet5.api.main import app
from openclassrooms_projet5.modeling.predict import get_predictor


VALID_PAYLOAD = {
    "age": 41,
    "genre": "F",
    "revenu_mensuel": 5993,
    "statut_marital": "Celibataire",
    "departement": "Commercial",
    "poste": "Cadre Commercial",
    "nombre_experiences_precedentes": 8,
    "annee_experience_totale": 8,
    "annees_dans_l_entreprise": 6,
    "annees_dans_le_poste_actuel": 4,
    "satisfaction_employee_environnement": 2,
    "note_evaluation_precedente": 3,
    "niveau_hierarchique_poste": 2,
    "satisfaction_employee_nature_travail": 4,
    "satisfaction_employee_equipe": 1,
    "satisfaction_employee_equilibre_pro_perso": 1,
    "note_evaluation_actuelle": 3,
    "heure_supplementaires": 1,
    "augementation_salaire_precedente": 11,
    "nombre_participation_pee": 0,
    "nb_formations_suivies": 0,
    "distance_domicile_travail": 1,
    "niveau_education": 2,
    "domaine_etude": "Infra & Cloud",
    "frequence_deplacement": "Occasionnel",
    "annees_depuis_la_derniere_promotion": 0,
    "annes_sous_responsable_actuel": 5,
}


client = TestClient(app)


@pytest.fixture(autouse=True)
def disable_authentication_by_default(monkeypatch):
    monkeypatch.delenv("API_KEY", raising=False)


def test_model_loads():
    predictor = get_predictor()

    assert predictor.threshold > 0
    assert len(predictor.feature_columns) == 30


def test_health_returns_model_status_when_database_disabled(monkeypatch):
    monkeypatch.setattr(app_main, "get_predictor", lambda: object())
    monkeypatch.setattr(app_main, "is_database_logging_enabled", lambda: False)
    monkeypatch.setattr(app_main, "is_authentication_enabled", lambda: False)

    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["model_loaded"] is True
    assert body["database_logging_enabled"] is False
    assert body["database_connected"] is False
    assert body["authentication_enabled"] is False
    assert body["detail"] is None


def test_health_returns_model_status_when_database_available(monkeypatch):
    monkeypatch.setattr(app_main, "get_predictor", lambda: object())
    monkeypatch.setattr(app_main, "is_database_logging_enabled", lambda: True)
    monkeypatch.setattr(app_main, "check_database_connection", lambda: (True, None))
    monkeypatch.setattr(app_main, "is_authentication_enabled", lambda: True)

    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["model_loaded"] is True
    assert body["database_logging_enabled"] is True
    assert body["database_connected"] is True
    assert body["authentication_enabled"] is True
    assert body["detail"] is None


def test_health_returns_degraded_status_when_database_unavailable(monkeypatch):
    monkeypatch.setattr(app_main, "get_predictor", lambda: object())
    monkeypatch.setattr(app_main, "is_database_logging_enabled", lambda: True)
    monkeypatch.setattr(app_main, "is_authentication_enabled", lambda: False)
    monkeypatch.setattr(
        app_main,
        "check_database_connection",
        lambda: (False, "database unavailable"),
    )

    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "degraded"
    assert body["model_loaded"] is True
    assert body["database_logging_enabled"] is True
    assert body["database_connected"] is False
    assert "database unavailable" in body["detail"]


def test_health_returns_degraded_status_when_model_is_unavailable(monkeypatch):
    def raise_model_error():
        raise FileNotFoundError("missing model")

    monkeypatch.setattr(app_main, "get_predictor", raise_model_error)
    monkeypatch.setattr(app_main, "is_database_logging_enabled", lambda: False)
    monkeypatch.setattr(app_main, "is_authentication_enabled", lambda: True)

    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "degraded"
    assert body["model_loaded"] is False
    assert body["authentication_enabled"] is True
    assert "missing model" in body["detail"]


def test_predict_returns_attrition_prediction(monkeypatch):
    monkeypatch.setattr(app_main, "is_database_logging_enabled", lambda: False)
    monkeypatch.setattr(app_main, "log_prediction", lambda payload, prediction: False)

    response = client.post("/predict", json=VALID_PAYLOAD)

    assert response.status_code == 200
    body = response.json()
    assert 0 <= body["probabilite_attrition"] <= 1
    assert body["prediction_attrition"] in {0, 1}
    assert 0 <= body["threshold"] <= 1


def test_predict_returns_503_when_model_file_is_missing(monkeypatch):
    monkeypatch.setattr(app_main, "is_database_logging_enabled", lambda: False)

    def raise_model_error():
        raise FileNotFoundError("missing model")

    monkeypatch.setattr(app_main, "get_predictor", raise_model_error)

    response = client.post("/predict", json=VALID_PAYLOAD)

    assert response.status_code == 503
    assert "Modele introuvable" in response.json()["detail"]


def test_predict_returns_400_when_predictor_rejects_payload(monkeypatch):
    class RejectingPredictor:
        def predict(self, features):
            raise ValueError("bad features")

    monkeypatch.setattr(app_main, "is_database_logging_enabled", lambda: False)
    monkeypatch.setattr(app_main, "get_predictor", lambda: RejectingPredictor())

    response = client.post("/predict", json=VALID_PAYLOAD)

    assert response.status_code == 400
    assert response.json() == {"detail": "bad features"}


def test_predict_returns_503_when_logging_fails_without_database_preflight(monkeypatch):
    monkeypatch.setattr(app_main, "is_database_logging_enabled", lambda: False)

    def fake_log_prediction(payload, prediction):
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(app_main, "log_prediction", fake_log_prediction)

    response = client.post("/predict", json=VALID_PAYLOAD)

    assert response.status_code == 503
    assert "Prediction persistence failed" in response.json()["detail"]


def test_predict_returns_503_when_database_is_required_but_unavailable(monkeypatch):
    monkeypatch.setattr(app_main, "is_database_logging_enabled", lambda: True)
    monkeypatch.setattr(
        app_main,
        "check_database_connection",
        lambda: (False, "database unavailable"),
    )

    response = client.post("/predict", json=VALID_PAYLOAD)

    assert response.status_code == 503
    assert "database unavailable" in response.json()["detail"]


def test_predict_returns_503_when_logging_fails_with_database_enabled(monkeypatch):
    monkeypatch.setattr(app_main, "is_database_logging_enabled", lambda: True)
    monkeypatch.setattr(app_main, "check_database_connection", lambda: (True, None))

    def fake_log_prediction(payload, prediction):
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(app_main, "log_prediction", fake_log_prediction)

    response = client.post("/predict", json=VALID_PAYLOAD)

    assert response.status_code == 503
    assert "Prediction persistence failed" in response.json()["detail"]


def test_predict_rejects_missing_required_field_without_logging(monkeypatch):
    monkeypatch.setattr(app_main, "is_database_logging_enabled", lambda: False)
    calls = {"count": 0}

    def fake_log_prediction(payload, prediction):
        calls["count"] += 1
        return True

    monkeypatch.setattr(app_main, "log_prediction", fake_log_prediction)
    payload = VALID_PAYLOAD.copy()
    payload.pop("age")

    response = client.post("/predict", json=payload)

    assert response.status_code == 422
    assert calls["count"] == 0


def test_predict_requires_api_key_when_authentication_is_enabled(monkeypatch):
    monkeypatch.setenv("API_KEY", "test-api-key")
    monkeypatch.setattr(app_main, "is_database_logging_enabled", lambda: False)
    monkeypatch.setattr(app_main, "log_prediction", lambda payload, prediction: False)

    unauthorized_response = client.post("/predict", json=VALID_PAYLOAD)
    authorized_response = client.post(
        "/predict",
        json=VALID_PAYLOAD,
        headers={"X-API-Key": "test-api-key"},
    )

    assert unauthorized_response.status_code == 401
    assert authorized_response.status_code == 200


def test_openapi_documents_prediction_security_examples_and_errors():
    response = client.get("/openapi.json")

    assert response.status_code == 200
    schema = response.json()
    predict_operation = schema["paths"]["/predict"]["post"]

    assert set(predict_operation["responses"]) >= {"200", "401", "422", "503"}
    assert predict_operation["requestBody"]["content"]["application/json"]["example"]["age"] == 41
    assert predict_operation["responses"]["200"]["content"]["application/json"]["example"][
        "prediction_attrition"
    ] in {0, 1}
    assert predict_operation["security"] == [{"APIKeyHeader": []}]
