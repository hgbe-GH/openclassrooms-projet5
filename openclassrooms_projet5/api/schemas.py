from pydantic import BaseModel, ConfigDict, Field

PREDICTION_PAYLOAD_EXAMPLE = {
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

PREDICTION_RESPONSE_EXAMPLE = {
    "probabilite_attrition": 0.7342,
    "prediction_attrition": 1,
    "threshold": 0.4781,
}

HEALTH_RESPONSE_OK_EXAMPLE = {
    "status": "ok",
    "model_loaded": True,
    "model_path": "models/attrition_xgboost_pipeline.joblib",
    "database_connected": False,
    "database_logging_enabled": False,
    "authentication_enabled": True,
    "detail": None,
}

HEALTH_RESPONSE_DEGRADED_EXAMPLE = {
    "status": "degraded",
    "model_loaded": False,
    "model_path": "models/attrition_xgboost_pipeline.joblib",
    "database_connected": False,
    "database_logging_enabled": True,
    "authentication_enabled": True,
    "detail": "model: [Errno 2] No such file or directory",
}


class EmployeeFeatures(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={"example": PREDICTION_PAYLOAD_EXAMPLE},
    )

    age: int = Field(ge=0, description="Age du collaborateur.")
    genre: str = Field(description="Genre declare dans le dataset source.")
    revenu_mensuel: float = Field(ge=0, description="Revenu mensuel brut.")
    statut_marital: str = Field(description="Statut marital.")
    departement: str = Field(description="Departement ou famille metier.")
    poste: str = Field(description="Intitule de poste.")
    nombre_experiences_precedentes: int = Field(
        ge=0,
        description="Nombre d'experiences professionnelles precedentes.",
    )
    annee_experience_totale: int = Field(ge=0, description="Experience totale en annees.")
    annees_dans_l_entreprise: int = Field(ge=0, description="Anciennete dans l'entreprise.")
    annees_dans_le_poste_actuel: int = Field(ge=0, description="Anciennete sur le poste actuel.")
    satisfaction_employee_environnement: int = Field(
        ge=1,
        le=4,
        description="Satisfaction employee sur l'environnement de travail, echelle 1-4.",
    )
    note_evaluation_precedente: int = Field(
        ge=1,
        le=4,
        description="Evaluation precedente, echelle 1-4.",
    )
    niveau_hierarchique_poste: int = Field(
        ge=1,
        description="Niveau hierarchique du poste.",
    )
    satisfaction_employee_nature_travail: int = Field(
        ge=1,
        le=4,
        description="Satisfaction employee sur la nature du travail, echelle 1-4.",
    )
    satisfaction_employee_equipe: int = Field(
        ge=1,
        le=4,
        description="Satisfaction employee sur l'equipe, echelle 1-4.",
    )
    satisfaction_employee_equilibre_pro_perso: int = Field(
        ge=1,
        le=4,
        description="Satisfaction sur l'equilibre vie pro / vie perso, echelle 1-4.",
    )
    note_evaluation_actuelle: int = Field(
        ge=1,
        le=4,
        description="Evaluation actuelle, echelle 1-4.",
    )
    heure_supplementaires: int = Field(
        ge=0,
        le=1,
        description="Indicateur binaire de recours aux heures supplementaires.",
    )
    augementation_salaire_precedente: float = Field(
        description="Derniere augmentation de salaire en pourcentage.",
    )
    nombre_participation_pee: int = Field(
        ge=0,
        description="Nombre de participations au plan d'epargne entreprise.",
    )
    nb_formations_suivies: int = Field(ge=0, description="Nombre de formations suivies.")
    distance_domicile_travail: float = Field(
        ge=0,
        description="Distance domicile-travail.",
    )
    niveau_education: int = Field(ge=1, description="Niveau d'education.")
    domaine_etude: str = Field(description="Domaine d'etude principal.")
    frequence_deplacement: str = Field(description="Frequence des deplacements professionnels.")
    annees_depuis_la_derniere_promotion: int = Field(
        ge=0,
        description="Nombre d'annees depuis la derniere promotion.",
    )
    annes_sous_responsable_actuel: int = Field(
        ge=0,
        description="Nombre d'annees sous le responsable actuel.",
    )


class PredictionResponse(BaseModel):
    model_config = ConfigDict(json_schema_extra={"example": PREDICTION_RESPONSE_EXAMPLE})

    probabilite_attrition: float = Field(
        ge=0,
        le=1,
        description="Probabilite predite d'attrition.",
    )
    prediction_attrition: int = Field(
        ge=0,
        le=1,
        description="Decision binaire finale du modele.",
    )
    threshold: float = Field(
        ge=0,
        le=1,
        description="Seuil de decision stocke avec l'artefact modele.",
    )


class HealthResponse(BaseModel):
    model_config = ConfigDict(json_schema_extra={"example": HEALTH_RESPONSE_OK_EXAMPLE})

    status: str = Field(description="Etat global du service : ok ou degraded.")
    model_loaded: bool = Field(description="Indique si l'artefact modele a ete charge.")
    model_path: str = Field(description="Chemin du modele attendu par l'application.")
    database_connected: bool = Field(description="Indique si PostgreSQL repond.")
    database_logging_enabled: bool = Field(
        description="Indique si une configuration PostgreSQL est active.",
    )
    authentication_enabled: bool = Field(
        description="Indique si `POST /predict` exige une cle `X-API-Key`.",
    )
    detail: str | None = Field(
        default=None,
        description="Detail technique utile en cas d'etat degrade.",
    )
