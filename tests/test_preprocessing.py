import pandas as pd
import pytest

from openclassrooms_projet5.modeling.preprocessing import (
    add_engineered_features,
    prepare_prediction_features,
)


def test_add_engineered_features_computes_expected_ratios():
    df = pd.DataFrame(
        [
            {
                "annees_dans_l_entreprise": 6,
                "annee_experience_totale": 8,
                "annees_dans_le_poste_actuel": 4,
                "annees_depuis_la_derniere_promotion": 2,
            }
        ]
    )

    result = add_engineered_features(df)

    assert result.loc[0, "ratio_anciennete_entreprise_experience"] == pytest.approx(6 / 9)
    assert result.loc[0, "ratio_anciennete_poste_entreprise"] == pytest.approx(4 / 7)
    assert result.loc[0, "ratio_temps_depuis_promotion_entreprise"] == pytest.approx(2 / 7)


def test_add_engineered_features_raises_when_required_columns_are_missing():
    df = pd.DataFrame([{"annees_dans_l_entreprise": 6}])

    with pytest.raises(ValueError, match="Colonnes manquantes pour les ratios"):
        add_engineered_features(df)


def test_prepare_prediction_features_drops_excluded_columns_and_preserves_order():
    df = pd.DataFrame(
        [
            {
                "id_employee": 1,
                "eval_number": 99,
                "code_sondage": "A",
                "a_quitte_l_entreprise": 0,
                "annees_dans_l_entreprise": 6,
                "annee_experience_totale": 8,
                "annees_dans_le_poste_actuel": 4,
                "annees_depuis_la_derniere_promotion": 2,
                "revenu_mensuel": 5993,
            }
        ]
    )
    feature_columns = [
        "revenu_mensuel",
        "ratio_anciennete_entreprise_experience",
        "ratio_anciennete_poste_entreprise",
        "ratio_temps_depuis_promotion_entreprise",
    ]

    result = prepare_prediction_features(df, feature_columns)

    assert list(result.columns) == feature_columns
    assert result.loc[0, "revenu_mensuel"] == 5993


def test_prepare_prediction_features_raises_when_feature_column_is_missing():
    df = pd.DataFrame(
        [
            {
                "annees_dans_l_entreprise": 6,
                "annee_experience_totale": 8,
                "annees_dans_le_poste_actuel": 4,
                "annees_depuis_la_derniere_promotion": 2,
            }
        ]
    )

    with pytest.raises(ValueError, match="Colonnes manquantes pour la prediction"):
        prepare_prediction_features(df, ["revenu_mensuel"])
