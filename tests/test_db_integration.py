import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from openclassrooms_projet5.api.main import app
from openclassrooms_projet5.config import MODEL_PATH, get_database_url
from openclassrooms_projet5.db.session import clear_database_state, get_session_factory


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


pytestmark = pytest.mark.skipif(
    not (os.getenv("DATABASE_URL") or get_database_url()),
    reason="A PostgreSQL configuration is required for integration tests.",
)

client = TestClient(app)


def _execute_scalar(statement: str) -> int:
    session_factory = get_session_factory()
    assert session_factory is not None

    with session_factory() as session:
        return session.execute(text(statement)).scalar_one()


def _fetch_prediction_log() -> dict[str, object]:
    session_factory = get_session_factory()
    assert session_factory is not None

    with session_factory() as session:
        result = session.execute(
            text(
                """
                SELECT request_payload, probabilite_attrition, prediction_attrition, threshold,
                       model_identifier
                FROM prediction_logs
                ORDER BY created_at DESC
                LIMIT 1
                """
            )
        )
        return dict(result.mappings().one())


@pytest.fixture(autouse=True)
def clean_prediction_logs():
    clear_database_state()
    session_factory = get_session_factory()
    assert session_factory is not None

    with session_factory() as session:
        session.execute(text("DELETE FROM prediction_logs"))
        session.commit()

    yield

    with session_factory() as session:
        session.execute(text("DELETE FROM prediction_logs"))
        session.commit()


def test_health_reports_connected_database():
    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["model_loaded"] is True
    assert body["database_logging_enabled"] is True
    assert body["database_connected"] is True


def test_predict_persists_prediction_log():
    response = client.post("/predict", json=VALID_PAYLOAD)

    assert response.status_code == 200
    body = response.json()
    assert _execute_scalar("SELECT COUNT(*) FROM prediction_logs") == 1

    row = _fetch_prediction_log()
    assert row["request_payload"]["age"] == VALID_PAYLOAD["age"]
    assert row["request_payload"]["poste"] == VALID_PAYLOAD["poste"]
    assert row["probabilite_attrition"] == body["probabilite_attrition"]
    assert row["prediction_attrition"] == body["prediction_attrition"]
    assert row["threshold"] == body["threshold"]
    assert row["model_identifier"] == MODEL_PATH.name


def test_predict_validation_error_does_not_write_log():
    payload = VALID_PAYLOAD.copy()
    payload.pop("age")

    response = client.post("/predict", json=payload)

    assert response.status_code == 422
    assert _execute_scalar("SELECT COUNT(*) FROM prediction_logs") == 0
