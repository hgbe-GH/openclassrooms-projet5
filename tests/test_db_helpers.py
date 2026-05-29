from contextlib import contextmanager

import pytest

import openclassrooms_projet5.db.service as db_service
import openclassrooms_projet5.db.session as db_session
from openclassrooms_projet5.modeling.predict import PredictionResult


def test_log_prediction_returns_false_when_database_logging_is_disabled(monkeypatch):
    monkeypatch.setattr(db_service, "is_database_logging_enabled", lambda: False)

    result = db_service.log_prediction(
        {"age": 41},
        PredictionResult(0.5, 1, 0.4),
    )

    assert result is False


def test_log_prediction_adds_prediction_log_when_database_logging_is_enabled(monkeypatch):
    captured = {}

    class FakeSession:
        def add(self, value):
            captured["value"] = value

    @contextmanager
    def fake_session_scope():
        yield FakeSession()

    monkeypatch.setattr(db_service, "is_database_logging_enabled", lambda: True)
    monkeypatch.setattr(db_service, "session_scope", fake_session_scope)

    result = db_service.log_prediction(
        {"age": 41},
        PredictionResult(0.8, 1, 0.4781),
    )

    assert result is True
    prediction_log = captured["value"]
    assert prediction_log.request_payload == {"age": 41}
    assert prediction_log.probabilite_attrition == 0.8
    assert prediction_log.prediction_attrition == 1
    assert prediction_log.threshold == 0.4781
    assert prediction_log.model_identifier == db_service.MODEL_PATH.name


class FakeSession:
    def __init__(self):
        self.committed = False
        self.rolled_back = False
        self.closed = False
        self.executed = []
        self.raise_on_execute = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
        return False

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True

    def execute(self, statement):
        self.executed.append(str(statement))
        if self.raise_on_execute is not None:
            raise self.raise_on_execute
        return 1


def test_get_session_factory_returns_none_when_database_logging_is_disabled(monkeypatch):
    monkeypatch.setattr(db_session, "get_database_url", lambda: None)

    assert db_session.get_session_factory() is None


def test_session_scope_commits_and_closes_session(monkeypatch):
    fake_session = FakeSession()
    monkeypatch.setattr(db_session, "get_session_factory", lambda: (lambda: fake_session))

    with db_session.session_scope() as session:
        assert session is fake_session

    assert fake_session.committed is True
    assert fake_session.rolled_back is False
    assert fake_session.closed is True


def test_session_scope_rolls_back_and_closes_on_error(monkeypatch):
    fake_session = FakeSession()
    monkeypatch.setattr(db_session, "get_session_factory", lambda: (lambda: fake_session))

    with pytest.raises(RuntimeError, match="boom"):
        with db_session.session_scope():
            raise RuntimeError("boom")

    assert fake_session.committed is False
    assert fake_session.rolled_back is True
    assert fake_session.closed is True


def test_check_database_connection_returns_false_when_disabled(monkeypatch):
    monkeypatch.setattr(db_session, "get_session_factory", lambda: None)

    assert db_session.check_database_connection() == (False, None)


def test_check_database_connection_returns_true_when_query_succeeds(monkeypatch):
    fake_session = FakeSession()
    monkeypatch.setattr(db_session, "get_session_factory", lambda: (lambda: fake_session))

    assert db_session.check_database_connection() == (True, None)
    assert "SELECT 1" in fake_session.executed[0]


def test_check_database_connection_returns_error_when_query_fails(monkeypatch):
    fake_session = FakeSession()
    fake_session.raise_on_execute = RuntimeError("database unavailable")
    monkeypatch.setattr(db_session, "get_session_factory", lambda: (lambda: fake_session))

    connected, detail = db_session.check_database_connection()

    assert connected is False
    assert "database unavailable" in detail
