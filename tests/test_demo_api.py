from __future__ import annotations

from pathlib import Path
import subprocess
from types import SimpleNamespace
from urllib.parse import urlparse

from fastapi.testclient import TestClient
import httpx
import pytest

from openclassrooms_projet5.api.demo import (
    _parse_quality_metrics,
    get_public_status,
    get_local_db_proof,
    get_local_demo_health,
    load_demo_snapshot,
    run_local_quality,
    run_public_demo,
    save_demo_snapshot,
    update_demo_snapshot,
)
import openclassrooms_projet5.api.demo as demo_routes
from openclassrooms_projet5.api.main import app


client = TestClient(app)


@pytest.fixture(autouse=True)
def disable_authentication_by_default(monkeypatch):
    monkeypatch.delenv("API_KEY", raising=False)


def test_landing_page_is_available():
    response = client.get("/")

    assert response.status_code == 200
    assert "Swagger / OpenAPI" in response.text


def test_demo_page_returns_404_when_demo_ui_is_disabled(monkeypatch):
    monkeypatch.setattr(demo_routes, "is_demo_ui_enabled", lambda: False)

    response = client.get("/demo")

    assert response.status_code == 404


def test_demo_page_renders_cockpit_when_enabled(monkeypatch):
    monkeypatch.setattr(demo_routes, "is_demo_ui_enabled", lambda: True)
    monkeypatch.setattr(
        demo_routes,
        "get_space_runtime_url",
        lambda: "https://example-demo.hf.space",
    )
    monkeypatch.setattr(demo_routes, "get_demo_api_key", lambda: "demo-key")

    response = client.get("/demo")

    assert response.status_code == 200
    assert "Cockpit Jury" in response.text
    assert "https://example-demo.hf.space/docs" in response.text
    assert "demo-key" in response.text


def test_demo_public_status_route_returns_payload(monkeypatch):
    monkeypatch.setattr(demo_routes, "is_demo_ui_enabled", lambda: True)
    monkeypatch.setattr(
        demo_routes,
        "get_public_status",
        lambda: {
            "space_url": "https://example-demo.hf.space",
            "docs_status": 200,
            "health_status": 200,
            "auth_enabled_detected": True,
            "timestamp": "2026-05-29T09:00:00+00:00",
        },
    )
    monkeypatch.setattr(demo_routes, "update_demo_snapshot", lambda section, payload: {})

    response = client.get("/demo-api/public/status")

    assert response.status_code == 200
    assert response.json()["docs_status"] == 200


def test_demo_local_db_proof_route_returns_503_on_failure(monkeypatch):
    monkeypatch.setattr(demo_routes, "is_demo_ui_enabled", lambda: True)

    def fail():
        raise RuntimeError("Database logging is disabled.")

    monkeypatch.setattr(demo_routes, "get_local_db_proof", fail)

    response = client.post("/demo-api/local/db-proof")

    assert response.status_code == 503
    assert "Database logging is disabled" in response.json()["detail"]


def test_demo_local_quality_route_returns_payload(monkeypatch):
    monkeypatch.setattr(demo_routes, "is_demo_ui_enabled", lambda: True)
    monkeypatch.setattr(
        demo_routes,
        "run_local_quality",
        lambda: {
            "pytest_exit_code": 0,
            "tests_passed": 42,
            "tests_failed": 0,
            "coverage_percent": 97,
            "ruff_exit_code": 0,
            "ruff_ok": True,
            "summary_text": "42 passed | 97% coverage | ruff OK",
            "timestamp": "2026-05-29T09:00:00+00:00",
        },
    )
    monkeypatch.setattr(demo_routes, "update_demo_snapshot", lambda section, payload: {})

    response = client.post("/demo-api/local/quality")

    assert response.status_code == 200
    assert response.json()["coverage_percent"] == 97


def test_demo_snapshot_route_returns_unavailable_when_missing(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(demo_routes, "is_demo_ui_enabled", lambda: True)
    monkeypatch.setattr(demo_routes, "load_demo_snapshot", lambda: None)
    monkeypatch.setattr(demo_routes, "_snapshot_path", lambda: tmp_path / "demo_snapshot.json")

    response = client.get("/demo-api/snapshot")

    assert response.status_code == 200
    assert response.json()["available"] is False


def test_demo_snapshot_route_returns_snapshot_when_available(monkeypatch):
    monkeypatch.setattr(demo_routes, "is_demo_ui_enabled", lambda: True)
    monkeypatch.setattr(
        demo_routes,
        "load_demo_snapshot",
        lambda: {"generated_at": "2026-05-29T09:00:00+00:00"},
    )
    monkeypatch.setattr(demo_routes, "_snapshot_path", lambda: Path("/tmp/demo_snapshot.json"))

    response = client.get("/demo-api/snapshot")

    assert response.status_code == 200
    assert response.json()["available"] is True


def test_demo_public_run_route_returns_payload(monkeypatch):
    monkeypatch.setattr(demo_routes, "is_demo_ui_enabled", lambda: True)
    monkeypatch.setattr(
        demo_routes,
        "run_public_demo",
        lambda: {
            "space_url": "https://example-demo.hf.space",
            "docs_status": 200,
            "health_status": 200,
            "predict_without_key_status": 401,
            "predict_with_key_status": 200,
            "predict_response_json": {"prediction_attrition": 1},
            "duration_ms": 123.45,
            "timestamp": "2026-05-29T09:00:00+00:00",
        },
    )
    monkeypatch.setattr(demo_routes, "update_demo_snapshot", lambda section, payload: {})

    response = client.post("/demo-api/public/run")

    assert response.status_code == 200
    assert response.json()["predict_with_key_status"] == 200


def test_demo_local_health_route_returns_local_urls(monkeypatch):
    monkeypatch.setattr(demo_routes, "is_demo_ui_enabled", lambda: True)
    monkeypatch.setattr(
        demo_routes,
        "get_local_demo_health",
        lambda: {
            "database_logging_enabled": True,
            "database_connected": True,
            "database_detail": None,
            "service_health": {"status": "ok"},
            "timestamp": "2026-05-29T09:00:00+00:00",
        },
    )
    monkeypatch.setattr(demo_routes, "update_demo_snapshot", lambda section, payload: {})

    response = client.get("/demo-api/local/health")

    assert response.status_code == 200
    assert response.json()["local_demo_url"].endswith("/demo")
    assert response.json()["local_docs_url"].endswith("/docs")


def test_parse_quality_metrics_extracts_expected_values():
    output = """
    tests/test_api.py ................
    ---------- coverage: platform linux, python 3.12 ----------
    Name    Stmts   Miss  Cover
    TOTAL     100      3    97%
    42 passed in 1.23s
    """

    assert _parse_quality_metrics(output) == (42, 0, 97)


def test_run_local_quality_parses_subprocess_outputs(monkeypatch):
    commands_seen = []

    def fake_run(command, **kwargs):
        commands_seen.append(command)
        if "pytest" in command:
            return SimpleNamespace(
                returncode=0,
                stdout="TOTAL 100 3 97%\n42 passed in 1.23s",
                stderr="",
            )

        return SimpleNamespace(returncode=0, stdout="All checks passed!", stderr="")

    monkeypatch.setattr(demo_routes.subprocess, "run", fake_run)

    payload = run_local_quality()

    assert commands_seen[0][0:3] == ["uv", "run", "pytest"]
    assert commands_seen[1][0:3] == ["uv", "run", "ruff"]
    assert payload["tests_passed"] == 42
    assert payload["coverage_percent"] == 97
    assert payload["ruff_ok"] is True


def test_run_local_quality_handles_timeout(monkeypatch):
    def raise_timeout(command, **kwargs):
        raise subprocess.TimeoutExpired(cmd=command, timeout=1)

    monkeypatch.setattr(demo_routes.subprocess, "run", raise_timeout)

    with pytest.raises(RuntimeError, match="timed out"):
        run_local_quality(timeout_seconds=1)


def test_get_public_status_handles_success(monkeypatch):
    class FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get(self, url):
            if url.endswith("/docs"):
                return SimpleNamespace(status_code=200, json=lambda: {"ok": True})
            return SimpleNamespace(
                status_code=200,
                json=lambda: {"authentication_enabled": True},
            )

    monkeypatch.setattr(demo_routes, "get_space_runtime_url", lambda: "https://demo.hf.space")
    monkeypatch.setattr(demo_routes.httpx, "Client", lambda **kwargs: FakeClient())

    payload = get_public_status()

    assert payload["space_url"] == "https://demo.hf.space"
    assert payload["docs_status"] == 200
    assert payload["health_status"] == 200
    assert payload["auth_enabled_detected"] is True


def test_get_public_status_handles_http_error(monkeypatch):
    class FailingClient:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get(self, url):
            raise httpx.HTTPError("boom")

    monkeypatch.setattr(demo_routes, "get_space_runtime_url", lambda: "https://demo.hf.space")
    monkeypatch.setattr(demo_routes.httpx, "Client", lambda **kwargs: FailingClient())

    payload = get_public_status()

    assert payload["docs_status"] is None
    assert payload["error"] == "boom"


def test_run_public_demo_handles_success(monkeypatch):
    class FakeResponse:
        def __init__(self, status_code, payload):
            self.status_code = status_code
            self._payload = payload

        def json(self):
            return self._payload

    class FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get(self, url):
            if url.endswith("/docs"):
                return FakeResponse(200, {"ok": True})
            return FakeResponse(200, {"authentication_enabled": True})

        def post(self, url, json, headers):
            parsed = urlparse(url)
            if "X-API-Key" in headers:
                return FakeResponse(200, {"prediction_attrition": 1, "threshold": 0.4})
            assert parsed.path.endswith("/predict")
            return FakeResponse(401, {"detail": "Invalid or missing API key."})

    monkeypatch.setattr(demo_routes.httpx, "Client", lambda **kwargs: FakeClient())
    monkeypatch.setattr(demo_routes, "get_space_runtime_url", lambda: "https://demo.hf.space")
    monkeypatch.setattr(demo_routes, "get_demo_api_key", lambda: "demo-key")

    payload = run_public_demo()

    assert payload["docs_status"] == 200
    assert payload["predict_without_key_status"] == 401
    assert payload["predict_with_key_status"] == 200
    assert payload["predict_response_json"]["prediction_attrition"] == 1


def test_run_public_demo_handles_http_error(monkeypatch):
    class FailingClient:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get(self, url):
            raise httpx.HTTPError("network down")

    monkeypatch.setattr(demo_routes.httpx, "Client", lambda **kwargs: FailingClient())
    monkeypatch.setattr(demo_routes, "get_space_runtime_url", lambda: "https://demo.hf.space")

    payload = run_public_demo()

    assert payload["predict_with_key_status"] is None
    assert payload["error"] == "network down"


def test_snapshot_helpers_roundtrip(monkeypatch, tmp_path: Path):
    snapshot_path = tmp_path / "demo_snapshot.json"
    monkeypatch.setattr(demo_routes, "_snapshot_path", lambda: snapshot_path)
    monkeypatch.setattr(demo_routes, "get_space_runtime_url", lambda: "https://demo.hf.space")
    monkeypatch.setattr(demo_routes, "get_demo_api_key", lambda: "demo-key")

    saved_path = save_demo_snapshot({"hello": "world"})
    assert saved_path == snapshot_path
    assert load_demo_snapshot() == {"hello": "world"}

    updated = update_demo_snapshot("public_status", {"docs_status": 200})
    assert updated["space_url"] == "https://demo.hf.space"
    assert updated["demo_api_key"] == "demo-key"
    assert updated["public_status"] == {"docs_status": 200}


def test_load_demo_snapshot_returns_none_for_invalid_json(monkeypatch, tmp_path: Path):
    snapshot_path = tmp_path / "demo_snapshot.json"
    snapshot_path.write_text("{invalid", encoding="utf-8")
    monkeypatch.setattr(demo_routes, "_snapshot_path", lambda: snapshot_path)

    assert load_demo_snapshot() is None


def test_get_local_demo_health_collects_service_state(monkeypatch):
    monkeypatch.setattr(demo_routes, "check_database_connection", lambda: (True, None))
    monkeypatch.setattr(demo_routes, "is_database_logging_enabled", lambda: True)

    monkeypatch.setattr(
        "openclassrooms_projet5.api.main.collect_health_response",
        lambda: SimpleNamespace(model_dump=lambda: {"status": "ok", "database_connected": True}),
    )

    payload = get_local_demo_health()

    assert payload["service_health"]["status"] == "ok"
    assert payload["database_connected"] is True


def test_get_local_db_proof_handles_disabled_database(monkeypatch):
    monkeypatch.setattr("openclassrooms_projet5.db.session.get_session_factory", lambda: None)

    with pytest.raises(RuntimeError, match="disabled"):
        get_local_db_proof()


def test_get_local_db_proof_handles_empty_result(monkeypatch):
    class FakeResult:
        def mappings(self):
            return self

        def first(self):
            return None

    class FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, query):
            return FakeResult()

    monkeypatch.setattr("openclassrooms_projet5.db.session.get_session_factory", lambda: FakeSession)
    monkeypatch.setattr(
        "openclassrooms_projet5.modeling.predict.get_predictor",
        lambda: SimpleNamespace(predict=lambda payload: SimpleNamespace()),
    )
    monkeypatch.setattr("openclassrooms_projet5.db.service.log_prediction", lambda payload, prediction: True)

    with pytest.raises(RuntimeError, match="No prediction log found"):
        get_local_db_proof()


def test_get_local_db_proof_creates_demo_log_when_table_is_empty(monkeypatch):
    rows = [
        None,
        {
            "created_at": None,
            "prediction_attrition": 1,
            "model_identifier": "model.joblib",
            "poste": "Cadre Commercial",
        },
    ]
    captured = {"logged": False}

    class FakeResult:
        def mappings(self):
            return self

        def first(self):
            return rows.pop(0)

    class FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, query):
            return FakeResult()

    monkeypatch.setattr("openclassrooms_projet5.db.session.get_session_factory", lambda: FakeSession)
    monkeypatch.setattr(
        "openclassrooms_projet5.modeling.predict.get_predictor",
        lambda: SimpleNamespace(predict=lambda payload: SimpleNamespace()),
    )
    monkeypatch.setattr(
        "openclassrooms_projet5.db.service.log_prediction",
        lambda payload, prediction: captured.__setitem__("logged", True),
    )

    payload = get_local_db_proof()

    assert captured["logged"] is True
    assert payload["prediction_attrition"] == 1


def test_get_local_db_proof_returns_latest_row(monkeypatch):
    class FakeResult:
        def mappings(self):
            return self

        def first(self):
            return {
                "created_at": None,
                "prediction_attrition": 1,
                "model_identifier": "model.joblib",
                "poste": "Cadre Commercial",
            }

    class FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, query):
            return FakeResult()

    monkeypatch.setattr("openclassrooms_projet5.db.session.get_session_factory", lambda: FakeSession)

    payload = get_local_db_proof()

    assert payload["prediction_attrition"] == 1
    assert payload["poste"] == "Cadre Commercial"
