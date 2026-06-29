#!/bin/sh
set -eu

MODEL_PATH="${MODEL_PATH:-models/attrition_xgboost_pipeline.joblib}"
ENCRYPTED_MODEL_PATH="${MODEL_PATH}.enc"

if [ ! -f "$MODEL_PATH" ] && [ -f "$ENCRYPTED_MODEL_PATH" ]; then
  if [ -z "${MODEL_ARTIFACT_PASSPHRASE:-}" ]; then
    echo "MODEL_ARTIFACT_PASSPHRASE is required to decrypt the model artifact."
    exit 1
  fi

  openssl enc -d -aes-256-cbc -pbkdf2 \
    -in "$ENCRYPTED_MODEL_PATH" \
    -out "$MODEL_PATH" \
    -pass pass:"${MODEL_ARTIFACT_PASSPHRASE}"
fi

exec uv run uvicorn openclassrooms_projet5.api.main:app \
  --host 0.0.0.0 \
  --port "${PORT}"
