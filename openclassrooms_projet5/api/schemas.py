from pydantic import BaseModel, ConfigDict, Field


class EmployeeFeatures(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
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
        },
    )

    age: int = Field(ge=0)
    genre: str
    revenu_mensuel: float = Field(ge=0)
    statut_marital: str
    departement: str
    poste: str
    nombre_experiences_precedentes: int = Field(ge=0)
    annee_experience_totale: int = Field(ge=0)
    annees_dans_l_entreprise: int = Field(ge=0)
    annees_dans_le_poste_actuel: int = Field(ge=0)
    satisfaction_employee_environnement: int = Field(ge=1, le=4)
    note_evaluation_precedente: int = Field(ge=1, le=4)
    niveau_hierarchique_poste: int = Field(ge=1)
    satisfaction_employee_nature_travail: int = Field(ge=1, le=4)
    satisfaction_employee_equipe: int = Field(ge=1, le=4)
    satisfaction_employee_equilibre_pro_perso: int = Field(ge=1, le=4)
    note_evaluation_actuelle: int = Field(ge=1, le=4)
    heure_supplementaires: int = Field(ge=0, le=1)
    augementation_salaire_precedente: float
    nombre_participation_pee: int = Field(ge=0)
    nb_formations_suivies: int = Field(ge=0)
    distance_domicile_travail: float = Field(ge=0)
    niveau_education: int = Field(ge=1)
    domaine_etude: str
    frequence_deplacement: str
    annees_depuis_la_derniere_promotion: int = Field(ge=0)
    annes_sous_responsable_actuel: int = Field(ge=0)


class PredictionResponse(BaseModel):
    probabilite_attrition: float = Field(ge=0, le=1)
    prediction_attrition: int = Field(ge=0, le=1)
    threshold: float = Field(ge=0, le=1)


class HealthResponse(BaseModel):
    status: str
    model_loaded: bool
    model_path: str
    database_connected: bool
    database_logging_enabled: bool
    detail: str | None = None
