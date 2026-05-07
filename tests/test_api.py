from fastapi.testclient import TestClient

import openclassrooms_projet5.api.main as app_main
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


def test_model_loads():
    predictor = get_predictor()

    assert predictor.threshold > 0
    assert len(predictor.feature_columns) == 30


def test_health_returns_model_status_when_database_disabled(monkeypatch):
    monkeypatch.setattr(app_main, "get_predictor", lambda: object())
    monkeypatch.setattr(app_main, "is_database_logging_enabled", lambda: False)

    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["model_loaded"] is True
    assert body["database_logging_enabled"] is False
    assert body["database_connected"] is False
    assert body["detail"] is None


def test_health_returns_model_status_when_database_available(monkeypatch):
    monkeypatch.setattr(app_main, "get_predictor", lambda: object())
    monkeypatch.setattr(app_main, "is_database_logging_enabled", lambda: True)
    monkeypatch.setattr(app_main, "check_database_connection", lambda: (True, None))

    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["model_loaded"] is True
    assert body["database_logging_enabled"] is True
    assert body["database_connected"] is True
    assert body["detail"] is None


def test_health_returns_degraded_status_when_database_unavailable(monkeypatch):
    monkeypatch.setattr(app_main, "get_predictor", lambda: object())
    monkeypatch.setattr(app_main, "is_database_logging_enabled", lambda: True)
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


def test_predict_returns_attrition_prediction(monkeypatch):
    monkeypatch.setattr(app_main, "log_prediction", lambda payload, prediction: False)

    response = client.post("/predict", json=VALID_PAYLOAD)

    assert response.status_code == 200
    body = response.json()
    assert 0 <= body["probabilite_attrition"] <= 1
    assert body["prediction_attrition"] in {0, 1}
    assert 0 <= body["threshold"] <= 1


def test_predict_returns_attrition_prediction_when_logging_fails(monkeypatch):
    def fake_log_prediction(payload, prediction):
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(app_main, "log_prediction", fake_log_prediction)

    response = client.post("/predict", json=VALID_PAYLOAD)

    assert response.status_code == 200
    body = response.json()
    assert 0 <= body["probabilite_attrition"] <= 1
    assert body["prediction_attrition"] in {0, 1}
    assert 0 <= body["threshold"] <= 1


def test_predict_rejects_missing_required_field_without_logging(monkeypatch):
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
