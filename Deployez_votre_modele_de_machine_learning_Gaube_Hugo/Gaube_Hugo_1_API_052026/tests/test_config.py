import openclassrooms_projet5.config as config


def test_get_database_url_prefers_explicit_value(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:pass@db:5432/custom")
    monkeypatch.setenv("POSTGRES_DB", "attrition_api")
    monkeypatch.setenv("POSTGRES_USER", "postgres")
    monkeypatch.setenv("POSTGRES_PASSWORD", "postgres")

    assert config.get_database_url() == "postgresql+psycopg://user:pass@db:5432/custom"


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


def test_get_database_url_returns_none_when_missing_required_values(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("POSTGRES_DB", raising=False)
    monkeypatch.setenv("POSTGRES_USER", "postgres")
    monkeypatch.setenv("POSTGRES_PASSWORD", "postgres")

    assert config.get_database_url() is None


def test_get_db_echo_and_api_key_strip_whitespace(monkeypatch):
    monkeypatch.setenv("DB_ECHO", " yes ")
    monkeypatch.setenv("API_KEY", "  secret-key  ")

    assert config.get_db_echo() is True
    assert config.get_api_key() == "secret-key"
    assert config.is_authentication_enabled() is True


def test_get_hf_space_url_builds_from_space(monkeypatch):
    monkeypatch.delenv("HF_SPACE_URL", raising=False)
    monkeypatch.setenv("HF_SPACE", "owner/project")

    assert config.get_hf_space_url() == "https://huggingface.co/spaces/owner/project"


def test_get_hf_space_url_uses_explicit_env_value(monkeypatch):
    monkeypatch.setenv("HF_SPACE_URL", "https://example.test/space")
    monkeypatch.setenv("HF_SPACE", "owner/project")

    assert config.get_hf_space_url() == "https://example.test/space"


def test_get_hf_space_runtime_url_prefers_explicit_value(monkeypatch):
    monkeypatch.setenv("HF_SPACE_URL", "https://example-runtime.hf.space")
    monkeypatch.setenv("HF_SPACE", "owner/project")

    assert config.get_hf_space_runtime_url() == "https://example-runtime.hf.space"


def test_get_hf_space_runtime_url_builds_runtime_domain(monkeypatch):
    monkeypatch.delenv("HF_SPACE_URL", raising=False)
    monkeypatch.setenv("HF_SPACE", "owner/project")

    assert config.get_hf_space_runtime_url() == "https://owner-project.hf.space"
