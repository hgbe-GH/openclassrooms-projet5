import os
from pathlib import Path

from dotenv import load_dotenv
from loguru import logger

# Load environment variables from .env file if it exists
load_dotenv()

# Paths
PROJ_ROOT = Path(__file__).resolve().parents[1]
logger.info(f"PROJ_ROOT path is: {PROJ_ROOT}")

DATA_DIR = PROJ_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
INTERIM_DATA_DIR = DATA_DIR / "interim"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
EXTERNAL_DATA_DIR = DATA_DIR / "external"

MODELS_DIR = PROJ_ROOT / "models"
_MODEL_PATH = Path(os.getenv("MODEL_PATH", "models/attrition_xgboost_pipeline.joblib"))
MODEL_PATH = _MODEL_PATH if _MODEL_PATH.is_absolute() else PROJ_ROOT / _MODEL_PATH


def _get_bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default

    return value.strip().lower() in {"1", "true", "yes", "on"}


def get_database_url() -> str | None:
    value = os.getenv("DATABASE_URL")
    if value is None:
        return None

    stripped_value = value.strip()
    return stripped_value or None


def get_db_echo() -> bool:
    return _get_bool_env("DB_ECHO", default=False)


DATABASE_URL = get_database_url()
DB_ECHO = get_db_echo()

REPORTS_DIR = PROJ_ROOT / "reports"
FIGURES_DIR = REPORTS_DIR / "figures"

# If tqdm is installed, configure loguru with tqdm.write
# https://github.com/Delgan/loguru/issues/135
try:
    from tqdm import tqdm

    logger.remove(0)
    logger.add(lambda msg: tqdm.write(msg, end=""), colorize=True)
except ModuleNotFoundError:
    pass
