import openclassrooms_projet5.config as config


def test_get_database_url_builds_value_from_postgres_env(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("POSTGRES_DB", "attrition_api")
    monkeypatch.setenv("POSTGRES_USER", "postgres")
    monkeypatch.setenv("POSTGRES_PASSWORD", "postgres")
    monkeypatch.setenv("POSTGRES_PORT", "5432")
    monkeypatch.setenv("POSTGRES_HOST", "db")

    assert (
        config.get_database_url()
        == "postgresql+psycopg://postgres:postgres@db:5432/attrition_api"
    )


def test_get_hf_space_url_uses_explicit_env_value(monkeypatch):
    monkeypatch.setenv("HF_SPACE_URL", "https://example.test/space")
    monkeypatch.setenv("HF_SPACE", "owner/project")

    assert config.get_hf_space_url() == "https://example.test/space"
