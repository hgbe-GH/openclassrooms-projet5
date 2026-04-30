from fastapi.testclient import TestClient

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


def test_health_returns_model_status():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["model_loaded"] is True


def test_predict_returns_attrition_prediction():
    response = client.post("/predict", json=VALID_PAYLOAD)

    assert response.status_code == 200
    body = response.json()
    assert 0 <= body["probabilite_attrition"] <= 1
    assert body["prediction_attrition"] in {0, 1}
    assert 0 <= body["threshold"] <= 1


def test_predict_rejects_missing_required_field():
    payload = VALID_PAYLOAD.copy()
    payload.pop("age")

    response = client.post("/predict", json=payload)

    assert response.status_code == 422
