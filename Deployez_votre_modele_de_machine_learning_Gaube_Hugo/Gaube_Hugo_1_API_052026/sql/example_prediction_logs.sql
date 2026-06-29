INSERT INTO prediction_logs (
    id,
    created_at,
    request_payload,
    probabilite_attrition,
    prediction_attrition,
    threshold,
    model_identifier
) VALUES (
    '5f094a53-1b57-4580-a436-c1a4b276fd11',
    '2026-05-21T10:15:00+00:00',
    '{
      "age": 41,
      "genre": "F",
      "revenu_mensuel": 5993,
      "statut_marital": "Celibataire",
      "departement": "Commercial",
      "poste": "Cadre Commercial"
    }'::jsonb,
    0.73,
    1,
    0.50,
    'attrition_xgboost_pipeline.joblib'
);
