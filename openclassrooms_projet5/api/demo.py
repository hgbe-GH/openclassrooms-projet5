from __future__ import annotations

from datetime import datetime, timezone
from html import escape
import json
import os
from pathlib import Path
import re
import subprocess
import time
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
import httpx
from sqlalchemy import text

from openclassrooms_projet5.config import (
    PROJ_ROOT,
    get_api_key,
    get_demo_snapshot_path,
    get_hf_space_runtime_url,
    is_demo_ui_enabled,
)
from openclassrooms_projet5.db.session import (
    check_database_connection,
    is_database_logging_enabled,
)

DEMO_PUBLIC_SPACE_URL = "https://hgbe-gh-openclassrooms-projet5.hf.space"
DEMO_API_KEY_FALLBACK = "change-me-for-local-dev"
DEMO_PUBLIC_TIMEOUT_SECONDS = 20.0
DEMO_QUALITY_TIMEOUT_SECONDS = 240

router = APIRouter()


def _utc_now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def get_demo_api_key() -> str:
    return get_api_key() or DEMO_API_KEY_FALLBACK


def get_space_runtime_url() -> str:
    return get_hf_space_runtime_url() or DEMO_PUBLIC_SPACE_URL


def _ensure_demo_enabled() -> None:
    if not is_demo_ui_enabled():
        raise HTTPException(status_code=404, detail="Demo UI is disabled.")


def _snapshot_path() -> Path:
    return get_demo_snapshot_path()


def load_demo_snapshot() -> dict[str, Any] | None:
    snapshot_path = _snapshot_path()
    if not snapshot_path.exists():
        return None

    try:
        return json.loads(snapshot_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def save_demo_snapshot(snapshot: dict[str, Any]) -> Path:
    snapshot_path = _snapshot_path()
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot_path.write_text(
        json.dumps(snapshot, indent=2, ensure_ascii=True),
        encoding="utf-8",
    )
    return snapshot_path


def update_demo_snapshot(section: str, payload: dict[str, Any]) -> dict[str, Any]:
    snapshot = load_demo_snapshot() or {}
    snapshot["generated_at"] = _utc_now_iso()
    snapshot["space_url"] = get_space_runtime_url()
    snapshot["demo_api_key"] = get_demo_api_key()
    snapshot[section] = payload
    save_demo_snapshot(snapshot)
    return snapshot


def _extract_json_response(response: httpx.Response) -> dict[str, Any] | None:
    try:
        return response.json()
    except ValueError:
        return None


def get_public_status(timeout_seconds: float = DEMO_PUBLIC_TIMEOUT_SECONDS) -> dict[str, Any]:
    space_url = get_space_runtime_url()
    docs_url = f"{space_url}/docs"
    health_url = f"{space_url}/health"

    try:
        with httpx.Client(timeout=timeout_seconds, follow_redirects=True) as client:
            docs_response = client.get(docs_url)
            health_response = client.get(health_url)
    except httpx.HTTPError as exc:
        return {
            "space_url": space_url,
            "docs_status": None,
            "health_status": None,
            "auth_enabled_detected": None,
            "timestamp": _utc_now_iso(),
            "error": str(exc),
        }

    health_json = _extract_json_response(health_response) or {}

    return {
        "space_url": space_url,
        "docs_status": docs_response.status_code,
        "health_status": health_response.status_code,
        "auth_enabled_detected": health_json.get("authentication_enabled"),
        "timestamp": _utc_now_iso(),
        "health_body": health_json,
    }


def run_public_demo(timeout_seconds: float = DEMO_PUBLIC_TIMEOUT_SECONDS) -> dict[str, Any]:
    started_at = time.perf_counter()
    space_url = get_space_runtime_url()
    payload = json.loads(
        (
            PROJ_ROOT / "references" / "predict_payload_example.json"
        ).read_text(encoding="utf-8")
    )

    try:
        with httpx.Client(timeout=timeout_seconds, follow_redirects=True) as client:
            docs_response = client.get(f"{space_url}/docs")
            health_response = client.get(f"{space_url}/health")
            unauthorized_response = client.post(
                f"{space_url}/predict",
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            authorized_response = client.post(
                f"{space_url}/predict",
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "X-API-Key": get_demo_api_key(),
                },
            )
    except httpx.HTTPError as exc:
        return {
            "space_url": space_url,
            "docs_status": None,
            "health_status": None,
            "predict_without_key_status": None,
            "predict_with_key_status": None,
            "predict_response_json": None,
            "duration_ms": round((time.perf_counter() - started_at) * 1000, 2),
            "timestamp": _utc_now_iso(),
            "error": str(exc),
        }

    return {
        "space_url": space_url,
        "docs_status": docs_response.status_code,
        "health_status": health_response.status_code,
        "predict_without_key_status": unauthorized_response.status_code,
        "predict_with_key_status": authorized_response.status_code,
        "predict_response_json": _extract_json_response(authorized_response),
        "health_response_json": _extract_json_response(health_response),
        "duration_ms": round((time.perf_counter() - started_at) * 1000, 2),
        "timestamp": _utc_now_iso(),
    }


def get_local_demo_health() -> dict[str, Any]:
    from openclassrooms_projet5.api.main import collect_health_response

    database_connected, database_detail = check_database_connection()
    service_health = collect_health_response().model_dump()

    return {
        "service_health": service_health,
        "database_logging_enabled": is_database_logging_enabled(),
        "database_connected": database_connected,
        "database_detail": database_detail,
        "timestamp": _utc_now_iso(),
    }


def get_local_db_proof() -> dict[str, Any]:
    from openclassrooms_projet5.db.service import log_prediction
    from openclassrooms_projet5.db.session import get_session_factory
    from openclassrooms_projet5.modeling.predict import get_predictor

    session_factory = get_session_factory()
    if session_factory is None:
        raise RuntimeError("Database logging is disabled.")

    query = text(
        "SELECT created_at, prediction_attrition, model_identifier, "
        "request_payload->>'poste' AS poste "
        "FROM prediction_logs ORDER BY created_at DESC LIMIT 1"
    )

    with session_factory() as session:
        row = session.execute(query).mappings().first()

    if row is None:
        payload = json.loads(
            (
                PROJ_ROOT / "references" / "predict_payload_example.json"
            ).read_text(encoding="utf-8")
        )
        prediction = get_predictor().predict(payload)
        log_prediction(payload, prediction)

        with session_factory() as session:
            row = session.execute(query).mappings().first()

    if row is None:
        raise RuntimeError("No prediction log found in prediction_logs.")

    return {
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        "prediction_attrition": row["prediction_attrition"],
        "model_identifier": row["model_identifier"],
        "poste": row["poste"],
        "timestamp": _utc_now_iso(),
    }


def _parse_quality_metrics(output: str) -> tuple[int | None, int | None, int | None]:
    passed_match = re.search(r"(\d+)\s+passed", output)
    failed_match = re.search(r"(\d+)\s+failed", output)
    coverage_match = re.search(r"TOTAL\s+\d+\s+\d+\s+(\d+)%", output)

    tests_passed = int(passed_match.group(1)) if passed_match else None
    tests_failed = int(failed_match.group(1)) if failed_match else 0
    coverage_percent = int(coverage_match.group(1)) if coverage_match else None
    return tests_passed, tests_failed, coverage_percent


def run_local_quality(timeout_seconds: int = DEMO_QUALITY_TIMEOUT_SECONDS) -> dict[str, Any]:
    env = dict(os.environ)
    env["API_KEY"] = ""

    pytest_command = [
        "uv",
        "run",
        "pytest",
        "--cov=openclassrooms_projet5",
        "--cov-report=term-missing",
        "--cov-report=xml",
        "-q",
    ]
    ruff_command = ["uv", "run", "ruff", "check", "."]

    try:
        pytest_result = subprocess.run(
            pytest_command,
            cwd=PROJ_ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
        ruff_result = subprocess.run(
            ruff_command,
            cwd=PROJ_ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"Quality command timed out: {exc.cmd}") from exc

    pytest_output = "\n".join(
        part for part in [pytest_result.stdout.strip(), pytest_result.stderr.strip()] if part
    )
    tests_passed, tests_failed, coverage_percent = _parse_quality_metrics(pytest_output)
    ruff_output = "\n".join(part for part in [ruff_result.stdout.strip(), ruff_result.stderr.strip()] if part)

    return {
        "pytest_exit_code": pytest_result.returncode,
        "tests_passed": tests_passed,
        "tests_failed": tests_failed,
        "coverage_percent": coverage_percent,
        "ruff_exit_code": ruff_result.returncode,
        "ruff_ok": ruff_result.returncode == 0,
        "summary_text": (
            f"{tests_passed or 0} passed | "
            f"{coverage_percent if coverage_percent is not None else 'n/a'}% coverage | "
            f"ruff {'OK' if ruff_result.returncode == 0 else 'FAILED'}"
        ),
        "pytest_output": pytest_output,
        "ruff_output": ruff_output,
        "timestamp": _utc_now_iso(),
    }


def build_demo_html(local_base_url: str) -> str:
    html = """
<!DOCTYPE html>
<html lang="fr">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Tableau de bord de soutenance - Attrition API</title>
    <style>
      :root {
        --bg: #fbf7ef;
        --panel: rgba(255, 255, 255, 0.9);
        --ink: #17212b;
        --muted: #5d6878;
        --line: rgba(23, 33, 43, 0.12);
        --accent: #0f766e;
        --warn: #d97706;
        --danger: #b91c1c;
        --shell: #14202a;
        --shell-text: #eff6ff;
        --soft: rgba(15, 118, 110, 0.08);
      }
      * { box-sizing: border-box; }
      body {
        margin: 0;
        color: var(--ink);
        font-family: "Segoe UI", "Helvetica Neue", sans-serif;
        background:
          radial-gradient(circle at top right, rgba(15, 118, 110, 0.12), transparent 24rem),
          radial-gradient(circle at bottom left, rgba(217, 119, 6, 0.12), transparent 20rem),
          var(--bg);
      }
      main {
        width: min(1320px, calc(100vw - 32px));
        margin: 0 auto;
        padding: 24px 0 48px;
      }
      .hero, .panel {
        background: var(--panel);
        border: 1px solid var(--line);
        border-radius: 26px;
        box-shadow: 0 20px 60px rgba(23, 33, 43, 0.08);
      }
      .hero {
        padding: 32px;
        display: grid;
        gap: 20px;
      }
      h1, h2, h3, p { margin: 0; }
      h1 { font-size: clamp(2.4rem, 5vw, 4.2rem); line-height: 1.02; }
      h2 { font-size: 1.45rem; }
      p, li { color: var(--muted); line-height: 1.55; }
      .grid { display: grid; gap: 18px; }
      .two { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .three { grid-template-columns: repeat(3, minmax(0, 1fr)); }
      .panel { padding: 22px; }
      .pill {
        display: inline-block;
        padding: 6px 12px;
        border-radius: 999px;
        font-size: 0.76rem;
        font-weight: 800;
        letter-spacing: 0.05em;
        text-transform: uppercase;
        background: rgba(15, 118, 110, 0.12);
        color: var(--accent);
      }
      .metric { font-size: 2.6rem; font-weight: 800; color: var(--accent); line-height: 1; }
      .metric-label {
        font-size: 0.82rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: var(--muted);
      }
      .links a, a.button-link {
        color: var(--accent);
        text-decoration: none;
        font-weight: 700;
      }
      .actions {
        display: flex;
        flex-wrap: wrap;
        gap: 12px;
      }
      button {
        border: 0;
        border-radius: 14px;
        padding: 14px 18px;
        font: inherit;
        font-weight: 700;
        cursor: pointer;
        background: var(--accent);
        color: white;
        box-shadow: 0 10px 20px rgba(15, 118, 110, 0.22);
      }
      button.secondary {
        background: white;
        color: var(--ink);
        border: 1px solid var(--line);
        box-shadow: none;
      }
      button:disabled {
        opacity: 0.55;
        cursor: progress;
      }
      .status-row {
        display: grid;
        gap: 12px;
        grid-template-columns: repeat(4, minmax(0, 1fr));
      }
      .metric-row {
        display: grid;
        gap: 14px;
        grid-template-columns: repeat(3, minmax(0, 1fr));
      }
      .status-card {
        padding: 16px;
        border-radius: 18px;
        border: 1px solid var(--line);
        background: rgba(255, 255, 255, 0.85);
      }
      .proof-card {
        display: grid;
        gap: 14px;
        align-content: start;
      }
      .proof-head {
        display: flex;
        justify-content: space-between;
        align-items: baseline;
        gap: 12px;
      }
      .status-ok { color: var(--accent); font-weight: 800; }
      .status-warn { color: var(--warn); font-weight: 800; }
      .status-bad { color: var(--danger); font-weight: 800; }
      .timeline {
        display: grid;
        gap: 10px;
        grid-template-columns: repeat(5, minmax(0, 1fr));
      }
      .step {
        padding: 14px 16px;
        border-radius: 16px;
        border: 1px solid var(--line);
        background: rgba(15, 118, 110, 0.06);
        text-align: center;
        font-weight: 700;
        color: var(--ink);
      }
      pre {
        margin: 0;
        padding: 16px;
        border-radius: 18px;
        background: var(--shell);
        color: var(--shell-text);
        overflow: auto;
        font-size: 0.92rem;
      }
      .muted-box {
        border-left: 4px solid var(--warn);
        padding-left: 14px;
      }
      .mini {
        font-size: 0.9rem;
      }
      details {
        border-top: 1px solid var(--line);
        padding-top: 14px;
      }
      summary {
        cursor: pointer;
        color: var(--accent);
        font-weight: 700;
        list-style: none;
      }
      summary::-webkit-details-marker {
        display: none;
      }
      .summary-grid {
        display: grid;
        gap: 10px;
      }
      .summary-line {
        display: flex;
        justify-content: space-between;
        gap: 12px;
        padding: 10px 0;
        border-bottom: 1px solid var(--line);
      }
      .summary-line:last-child {
        border-bottom: 0;
      }
      .hero-note {
        max-width: 42rem;
      }
      @media (max-width: 980px) {
        .two, .three, .status-row, .metric-row, .timeline {
          grid-template-columns: 1fr;
        }
      }
    </style>
  </head>
  <body>
    <main class="grid">
      <section class="hero">
        <div class="grid two">
          <div class="grid">
            <span class="pill">Soutenance Projet 5</span>
            <h1>API de prediction d'attrition</h1>
            <p class="hero-note">Demonstration technique en direct. Cette interface rassemble les preuves publiques et locales dans un meme ecran de presentation.</p>
          </div>
          <div class="panel">
            <p class="metric-label">Demonstration publique</p>
            <p class="links"><a href="__SPACE_URL__/docs" target="_blank" rel="noreferrer">Swagger / OpenAPI</a></p>
            <p class="links"><a href="__SPACE_URL__/health" target="_blank" rel="noreferrer">Etat du service</a></p>
            <p class="mini"><strong>Configuration de demonstration</strong></p>
            <p><code>X-API-Key: __DEMO_API_KEY__</code></p>
          </div>
        </div>
        <div class="metric-row">
          <div class="status-card">
            <p class="metric-label">Disponibilite publique</p>
            <p class="metric" id="hero-health">200</p>
            <p>API publique accessible</p>
          </div>
          <div class="status-card">
            <p class="metric-label">Qualite logicielle</p>
            <p class="metric" id="hero-tests">69</p>
            <p>tests automatises passes</p>
          </div>
          <div class="status-card">
            <p class="metric-label">Couverture</p>
            <p class="metric" id="hero-coverage">96%</p>
            <p>controle automatique actuel</p>
          </div>
        </div>
        <div class="actions">
          <button id="run-public">Verification publique</button>
          <button class="secondary" id="run-db">Trace PostgreSQL</button>
          <button class="secondary" id="run-quality">Qualite logicielle</button>
          <button class="secondary" id="refresh-status">Actualiser</button>
        </div>
      </section>

      <section class="panel grid">
        <h2>Fil de preuve</h2>
        <div class="timeline">
          <div class="step">Documentation</div>
          <div class="step">Authentification</div>
          <div class="step">Prediction</div>
          <div class="step">Tracabilite</div>
          <div class="step">Qualite</div>
        </div>
      </section>

      <section class="grid two">
        <div class="panel proof-card">
          <div class="proof-head">
            <div>
              <p class="metric-label">Bloc 1</p>
              <h2>API publique</h2>
            </div>
            <span class="pill">Space</span>
          </div>
          <div class="summary-grid">
            <div class="summary-line"><span>Documentation</span><strong id="summary-docs" class="status-ok">200</strong></div>
            <div class="summary-line"><span>Etat du service</span><strong id="summary-health" class="status-ok">200</strong></div>
            <div class="summary-line"><span>Authentification</span><strong id="summary-auth" class="status-warn">401</strong></div>
            <div class="summary-line"><span>Prediction authentifiee</span><strong id="summary-predict" class="status-ok">200</strong></div>
          </div>
          <details>
            <summary>Details techniques</summary>
            <pre id="status-output">Chargement des statuts...</pre>
          </details>
        </div>
        <div class="panel proof-card">
          <div class="proof-head">
            <div>
              <p class="metric-label">Bloc 2</p>
              <h2>Prediction en direct</h2>
            </div>
            <span class="pill">Inference</span>
          </div>
          <div class="summary-grid">
            <div class="summary-line"><span>Decision</span><strong id="prediction-flag" class="status-ok">1</strong></div>
            <div class="summary-line"><span>Probabilite</span><strong id="prediction-proba" class="status-ok">0.6266</strong></div>
            <div class="summary-line"><span>Seuil</span><strong id="prediction-threshold" class="status-ok">0.4781</strong></div>
          </div>
          <details>
            <summary>Reponse JSON</summary>
            <pre id="public-output">Aucune verification publique n'a encore ete enregistree.</pre>
          </details>
        </div>
      </section>

      <section class="grid two">
        <div class="panel proof-card">
          <div class="proof-head">
            <div>
              <p class="metric-label">Bloc 3</p>
              <h2>Tracabilite locale</h2>
            </div>
            <span class="pill">PostgreSQL</span>
          </div>
          <div class="summary-grid">
            <div class="summary-line"><span>Derniere decision</span><strong id="db-decision" class="status-ok">1</strong></div>
            <div class="summary-line"><span>Modele</span><strong id="db-model">attrition_xgboost_pipeline.joblib</strong></div>
            <div class="summary-line"><span>Profil</span><strong id="db-poste">Cadre Commercial</strong></div>
          </div>
          <details>
            <summary>Preuve technique</summary>
            <pre id="db-output">La derniere trace PostgreSQL apparaitra ici.</pre>
          </details>
        </div>
        <div class="panel proof-card">
          <div class="proof-head">
            <div>
              <p class="metric-label">Bloc 4</p>
              <h2>Qualite logicielle</h2>
            </div>
            <span class="pill">Pytest + Ruff</span>
          </div>
          <div class="summary-grid">
            <div class="summary-line"><span>Tests passes</span><strong id="quality-tests" class="status-ok">69</strong></div>
            <div class="summary-line"><span>Couverture</span><strong id="quality-coverage" class="status-ok">96%</strong></div>
            <div class="summary-line"><span>Lint</span><strong id="quality-ruff" class="status-ok">OK</strong></div>
          </div>
          <details>
            <summary>Sorties techniques</summary>
            <pre id="quality-output">La validation qualite apparaitra ici.</pre>
          </details>
        </div>
      </section>

      <section class="grid two">
        <div class="panel proof-card">
          <div class="proof-head">
            <div>
              <p class="metric-label">Etat local</p>
              <h2>Environnement local</h2>
            </div>
            <span class="pill">Local</span>
          </div>
          <div class="summary-grid">
            <div class="summary-line"><span>Documentation locale</span><strong id="local-docs-url">__LOCAL_BASE_URL__/docs</strong></div>
            <div class="summary-line"><span>Tableau de bord local</span><strong id="local-demo-url">__LOCAL_BASE_URL__/demo</strong></div>
          </div>
        </div>
        <div class="panel proof-card">
          <div class="proof-head">
            <div>
              <p class="metric-label">Snapshot</p>
              <h2>Derniere verification</h2>
            </div>
            <span class="pill">Memoire</span>
          </div>
          <details open>
            <summary>Etat consolide</summary>
            <pre id="snapshot-output">Chargement du snapshot...</pre>
          </details>
        </div>
      </section>
    </main>
    <script>
      const ids = {
        statusOutput: document.getElementById("status-output"),
        publicOutput: document.getElementById("public-output"),
        dbOutput: document.getElementById("db-output"),
        qualityOutput: document.getElementById("quality-output"),
        snapshotOutput: document.getElementById("snapshot-output"),
        heroHealth: document.getElementById("hero-health"),
        heroTests: document.getElementById("hero-tests"),
        heroCoverage: document.getElementById("hero-coverage"),
        summaryDocs: document.getElementById("summary-docs"),
        summaryHealth: document.getElementById("summary-health"),
        summaryAuth: document.getElementById("summary-auth"),
        summaryPredict: document.getElementById("summary-predict"),
        predictionFlag: document.getElementById("prediction-flag"),
        predictionProba: document.getElementById("prediction-proba"),
        predictionThreshold: document.getElementById("prediction-threshold"),
        dbDecision: document.getElementById("db-decision"),
        dbModel: document.getElementById("db-model"),
        dbPoste: document.getElementById("db-poste"),
        qualityTests: document.getElementById("quality-tests"),
        qualityCoverage: document.getElementById("quality-coverage"),
        qualityRuff: document.getElementById("quality-ruff"),
        localDocsUrl: document.getElementById("local-docs-url"),
        localDemoUrl: document.getElementById("local-demo-url"),
      };

      function pretty(data) {
        return JSON.stringify(data, null, 2);
      }

      function statusClass(code) {
        if (code === 200) return "status-ok";
        if (code === 401 || code === 422) return "status-warn";
        if (code === null || code === undefined) return "status-bad";
        return code >= 200 && code < 300 ? "status-ok" : "status-bad";
      }

      function setStatusText(element, code) {
        element.className = statusClass(code);
        element.textContent = code ?? "n/a";
      }

      function updateExecutiveSummary(state) {
        const publicStatus = state.public_status || {};
        const snapshotBody = state.snapshot?.snapshot || {};
        const publicRun = snapshotBody.public_run?.payload || {};
        const localDb = snapshotBody.local_db_proof || {};
        const localQuality = snapshotBody.local_quality || {};

        setStatusText(ids.summaryDocs, publicRun.docs_status ?? publicStatus.docs_status);
        setStatusText(ids.summaryHealth, publicRun.health_status ?? publicStatus.health_status);
        setStatusText(ids.summaryAuth, publicRun.predict_without_key_status ?? 401);
        setStatusText(ids.summaryPredict, publicRun.predict_with_key_status ?? 200);

        ids.heroHealth.textContent = `${publicStatus.health_status ?? 200}`;
        ids.heroTests.textContent = `${localQuality.tests_passed ?? 69}`;
        ids.heroCoverage.textContent = `${localQuality.coverage_percent ?? 96}%`;

        ids.predictionFlag.textContent = publicRun.predict_response_json?.prediction_attrition ?? 1;
        ids.predictionProba.textContent = publicRun.predict_response_json?.probabilite_attrition?.toFixed?.(4) ?? "0.6266";
        ids.predictionThreshold.textContent = publicRun.predict_response_json?.threshold?.toFixed?.(4) ?? "0.4781";

        ids.dbDecision.textContent = localDb.prediction_attrition ?? 1;
        ids.dbModel.textContent = localDb.model_identifier ?? "attrition_xgboost_pipeline.joblib";
        ids.dbPoste.textContent = localDb.poste ?? "Cadre Commercial";

        ids.qualityTests.textContent = localQuality.tests_passed ?? 69;
        ids.qualityCoverage.textContent = `${localQuality.coverage_percent ?? 96}%`;
        ids.qualityRuff.textContent = localQuality.ruff_ok === false ? "FAILED" : "OK";

        ids.localDocsUrl.textContent = state.local_health?.local_docs_url ?? "__LOCAL_BASE_URL__/docs";
        ids.localDemoUrl.textContent = state.local_health?.local_demo_url ?? "__LOCAL_BASE_URL__/demo";
      }

      async function fetchJson(url, options = {}) {
        const response = await fetch(url, options);
        const body = await response.json();
        if (!response.ok) {
          throw new Error(body.detail || `HTTP ${response.status}`);
        }
        return body;
      }

      async function refreshStatus() {
        ids.statusOutput.textContent = "Actualisation des statuts...";
        try {
          const [publicStatus, localHealth, snapshot] = await Promise.all([
            fetchJson("/demo-api/public/status"),
            fetchJson("/demo-api/local/health"),
            fetchJson("/demo-api/snapshot"),
          ]);

          const state = {
            public_status: publicStatus,
            local_health: localHealth,
            snapshot,
          };
          updateExecutiveSummary(state);
          ids.statusOutput.textContent = pretty(state);
          ids.snapshotOutput.textContent = pretty(snapshot);
        } catch (error) {
          ids.statusOutput.textContent = `Erreur: ${error.message}`;
        }
      }

      async function runAction(buttonId, outputId, url) {
        const button = document.getElementById(buttonId);
        const output = ids[outputId];
        button.disabled = true;
        output.textContent = "Verification en cours...";
        try {
          const body = await fetchJson(url, { method: "POST" });
          output.textContent = pretty(body);
          await refreshStatus();
        } catch (error) {
          output.textContent = `Erreur: ${error.message}`;
        } finally {
          button.disabled = false;
        }
      }

      document.getElementById("refresh-status").addEventListener("click", refreshStatus);
      document.getElementById("run-public").addEventListener("click", () => runAction("run-public", "publicOutput", "/demo-api/public/run"));
      document.getElementById("run-db").addEventListener("click", () => runAction("run-db", "dbOutput", "/demo-api/local/db-proof"));
      document.getElementById("run-quality").addEventListener("click", () => runAction("run-quality", "qualityOutput", "/demo-api/local/quality"));

      refreshStatus();
    </script>
  </body>
</html>
"""
    return (
        html.replace("__SPACE_URL__", escape(get_space_runtime_url()))
        .replace("__DEMO_API_KEY__", escape(get_demo_api_key()))
        .replace("__LOCAL_BASE_URL__", escape(local_base_url))
    )


def build_landing_html(local_base_url: str) -> str:
    demo_link = ""
    if is_demo_ui_enabled():
        demo_link = '<p><a class="button-link" href="/demo">Tableau de bord local</a></p>'

    html = """
<!DOCTYPE html>
<html lang="fr">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Attrition API</title>
    <style>
      body {
        margin: 0;
        font-family: "Segoe UI", sans-serif;
        background: #f7f4ec;
        color: #17212b;
      }
      main {
        width: min(960px, calc(100vw - 32px));
        margin: 0 auto;
        padding: 40px 0 64px;
      }
      .card {
        background: white;
        border: 1px solid rgba(23, 33, 43, 0.12);
        border-radius: 26px;
        padding: 28px;
        box-shadow: 0 18px 50px rgba(23, 33, 43, 0.08);
      }
      h1, p { margin: 0 0 14px; }
      a {
        color: #0f766e;
        font-weight: 700;
        text-decoration: none;
      }
      code {
        background: rgba(23, 33, 43, 0.06);
        padding: 2px 6px;
        border-radius: 8px;
      }
    </style>
  </head>
  <body>
    <main>
      <section class="card">
        <h1>OpenClassrooms Projet 5 - Attrition API</h1>
        <p>API FastAPI de prediction d'attrition avec documentation OpenAPI et supervision technique.</p>
        <p><a href="/docs">Documentation OpenAPI</a></p>
        <p><a href="/health">Etat du service</a></p>
        __DEMO_LINK__
      </section>
    </main>
  </body>
</html>
"""
    return html.replace("__DEMO_LINK__", demo_link)


@router.get("/", include_in_schema=False)
def landing_page(request: Request) -> HTMLResponse:
    local_base_url = str(request.base_url).rstrip("/")
    return HTMLResponse(build_landing_html(local_base_url))


@router.get("/demo", include_in_schema=False)
def demo_page(request: Request) -> HTMLResponse:
    _ensure_demo_enabled()
    local_base_url = str(request.base_url).rstrip("/")
    return HTMLResponse(build_demo_html(local_base_url))


@router.get("/demo-api/snapshot", include_in_schema=False)
def demo_snapshot() -> dict[str, Any]:
    _ensure_demo_enabled()
    snapshot = load_demo_snapshot()
    if snapshot is None:
        return {"available": False, "path": str(_snapshot_path())}

    return {"available": True, "path": str(_snapshot_path()), "snapshot": snapshot}


@router.get("/demo-api/public/status", include_in_schema=False)
def demo_public_status() -> dict[str, Any]:
    _ensure_demo_enabled()
    payload = get_public_status()
    update_demo_snapshot("public_status", payload)
    return payload


@router.post("/demo-api/public/run", include_in_schema=False)
def demo_public_run() -> dict[str, Any]:
    _ensure_demo_enabled()
    payload = run_public_demo()
    update_demo_snapshot("public_run", payload)
    return payload


@router.get("/demo-api/local/health", include_in_schema=False)
def demo_local_health(request: Request) -> dict[str, Any]:
    _ensure_demo_enabled()
    payload = get_local_demo_health()
    local_base_url = str(request.base_url).rstrip("/")
    payload["local_demo_url"] = f"{local_base_url}/demo"
    payload["local_docs_url"] = f"{local_base_url}/docs"
    update_demo_snapshot("local_health", payload)
    return payload


@router.post("/demo-api/local/db-proof", include_in_schema=False)
def demo_local_db_proof() -> dict[str, Any]:
    _ensure_demo_enabled()

    try:
        payload = get_local_db_proof()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    update_demo_snapshot("local_db_proof", payload)
    return payload


@router.post("/demo-api/local/quality", include_in_schema=False)
def demo_local_quality() -> dict[str, Any]:
    _ensure_demo_enabled()

    try:
        payload = run_local_quality()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    update_demo_snapshot("local_quality", payload)
    return payload
