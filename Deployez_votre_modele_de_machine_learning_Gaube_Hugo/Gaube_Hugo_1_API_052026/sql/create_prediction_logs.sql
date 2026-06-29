CREATE TABLE IF NOT EXISTS prediction_logs (
    id UUID PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    request_payload JSONB NOT NULL,
    probabilite_attrition DOUBLE PRECISION NOT NULL,
    prediction_attrition SMALLINT NOT NULL,
    threshold DOUBLE PRECISION NOT NULL,
    model_identifier TEXT,
    CONSTRAINT ck_prediction_logs_prediction_attrition_binary
        CHECK (prediction_attrition IN (0, 1))
);
