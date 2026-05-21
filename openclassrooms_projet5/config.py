import os
from pathlib import Path
from urllib.parse import quote_plus

from dotenv import load_dotenv

# Load environment variables from .env file if it exists
load_dotenv()

# Paths
PROJ_ROOT = Path(__file__).resolve().parents[1]

DATA_DIR = PROJ_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
INTERIM_DATA_DIR = DATA_DIR / "interim"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
EXTERNAL_DATA_DIR = DATA_DIR / "external"

MODELS_DIR = PROJ_ROOT / "models"


def _resolve_project_path(env_name: str, default: str) -> Path:
    configured_path = Path(os.getenv(env_name, default))
    if configured_path.is_absolute():
        return configured_path

    return PROJ_ROOT / configured_path


MODEL_PATH = _resolve_project_path("MODEL_PATH", "models/attrition_xgboost_pipeline.joblib")


def _get_bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default

    return value.strip().lower() in {"1", "true", "yes", "on"}


def _get_str_env(name: str) -> str | None:
    value = os.getenv(name)
    if value is None:
        return None

    stripped_value = value.strip()
    return stripped_value or None


def _build_database_url_from_postgres_env() -> str | None:
    db_name = _get_str_env("POSTGRES_DB")
    db_user = _get_str_env("POSTGRES_USER")
    db_password = _get_str_env("POSTGRES_PASSWORD")
    db_host = _get_str_env("POSTGRES_HOST") or "localhost"
    db_port = _get_str_env("POSTGRES_PORT") or "5432"

    if not all([db_name, db_user, db_password]):
        return None

    return (
        "postgresql+psycopg://"
        f"{quote_plus(db_user)}:{quote_plus(db_password)}@"
        f"{db_host}:{db_port}/{quote_plus(db_name)}"
    )


def get_database_url() -> str | None:
    explicit_url = _get_str_env("DATABASE_URL")
    if explicit_url:
        return explicit_url

    return _build_database_url_from_postgres_env()


def get_db_echo() -> bool:
    return _get_bool_env("DB_ECHO", default=False)


def get_api_key() -> str | None:
    return _get_str_env("API_KEY")


def is_authentication_enabled() -> bool:
    return bool(get_api_key())


def get_hf_space() -> str | None:
    return _get_str_env("HF_SPACE")


def get_hf_space_url() -> str | None:
    explicit_url = _get_str_env("HF_SPACE_URL")
    if explicit_url:
        return explicit_url

    hf_space = get_hf_space()
    if not hf_space:
        return None

    return f"https://huggingface.co/spaces/{hf_space}"


DATABASE_URL = get_database_url()
DB_ECHO = get_db_echo()
API_KEY = get_api_key()
HF_SPACE_URL = get_hf_space_url()

REPORTS_DIR = PROJ_ROOT / "reports"
FIGURES_DIR = REPORTS_DIR / "figures"
