from __future__ import annotations

import pandas as pd

TARGET_COLUMN = "target_attrition"

LEAKAGE_COLUMNS = (
    "id_employee",
    "eval_number",
    "code_sondage",
    "a_quitte_l_entreprise",
)
CONSTANT_COLUMNS = (
    "nombre_heures_travailless",
    "nombre_employee_sous_responsabilite",
    "ayant_enfants",
)
EXCLUDED_FEATURE_COLUMNS = LEAKAGE_COLUMNS + CONSTANT_COLUMNS + (TARGET_COLUMN,)
ENGINEERING_SOURCE_COLUMNS = (
    "annees_dans_l_entreprise",
    "annee_experience_totale",
    "annees_dans_le_poste_actuel",
    "annees_depuis_la_derniere_promotion",
)


def add_engineered_features(df: pd.DataFrame) -> pd.DataFrame:
    missing_columns = sorted(set(ENGINEERING_SOURCE_COLUMNS).difference(df.columns))
    if missing_columns:
        raise ValueError(f"Colonnes manquantes pour les ratios: {missing_columns}")

    engineered = df.copy()
    engineered["ratio_anciennete_entreprise_experience"] = engineered[
        "annees_dans_l_entreprise"
    ] / (engineered["annee_experience_totale"] + 1)
    engineered["ratio_anciennete_poste_entreprise"] = engineered["annees_dans_le_poste_actuel"] / (
        engineered["annees_dans_l_entreprise"] + 1
    )
    engineered["ratio_temps_depuis_promotion_entreprise"] = engineered[
        "annees_depuis_la_derniere_promotion"
    ] / (engineered["annees_dans_l_entreprise"] + 1)

    return engineered


def prepare_prediction_features(df: pd.DataFrame, feature_columns: list[str]) -> pd.DataFrame:
    df_with_features = add_engineered_features(df)
    columns_to_drop = [column for column in EXCLUDED_FEATURE_COLUMNS if column in df_with_features]
    X = df_with_features.drop(columns=columns_to_drop)

    missing_columns = sorted(set(feature_columns).difference(X.columns))
    if missing_columns:
        raise ValueError(f"Colonnes manquantes pour la prediction: {missing_columns}")

    return X.loc[:, feature_columns]
