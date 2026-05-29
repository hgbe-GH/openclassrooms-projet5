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
    <title>Cockpit Soutenance - Attrition API</title>
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
      .metric { font-size: 2.2rem; font-weight: 800; color: var(--accent); }
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
      .status-card {
        padding: 16px;
        border-radius: 18px;
        border: 1px solid var(--line);
        background: rgba(255, 255, 255, 0.85);
      }
      .status-ok { color: var(--accent); font-weight: 800; }
      .status-warn { color: var(--warn); font-weight: 800; }
      .status-bad { color: var(--danger); font-weight: 800; }
      .timeline {
        display: grid;
        gap: 10px;
      }
      .step {
        padding: 14px 16px;
        border-radius: 16px;
        border: 1px solid var(--line);
        background: rgba(15, 118, 110, 0.06);
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
      @media (max-width: 980px) {
        .two, .three, .status-row {
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
            <span class="pill">Cockpit Jury</span>
            <h1>Demo soutenance quasi autonome</h1>
            <p>
              Cette page orchestre la demo publique du Space Hugging Face et les preuves
              locales PostgreSQL / qualite dans une seule interface.
            </p>
          </div>
          <div class="panel">
            <p class="mini"><strong>Space public</strong></p>
            <p class="links"><a href="__SPACE_URL__/docs" target="_blank" rel="noreferrer">__SPACE_URL__/docs</a></p>
            <p class="mini"><strong>Cle de demo</strong></p>
            <p><code>X-API-Key: __DEMO_API_KEY__</code></p>
            <p class="mini"><strong>Plan B local</strong></p>
            <p class="links"><a href="__LOCAL_BASE_URL__/docs" target="_blank" rel="noreferrer">__LOCAL_BASE_URL__/docs</a></p>
          </div>
        </div>
        <div class="actions">
          <button id="run-public">Lancer la demo publique</button>
          <button class="secondary" id="run-db">Afficher preuve PostgreSQL</button>
          <button class="secondary" id="run-quality">Afficher qualite / couverture</button>
          <button class="secondary" id="refresh-status">Actualiser les statuts</button>
        </div>
      </section>

      <section class="panel grid">
        <h2>1. Checklist de demo</h2>
        <div class="timeline">
          <div class="step">1. Ouvrir <code>/demo</code> et cliquer sur <strong>Lancer la demo publique</strong>.</div>
          <div class="step">2. Montrer les statuts <code>/docs 200</code>, <code>/health 200</code>, <code>/predict 401</code>, <code>/predict 200</code>.</div>
          <div class="step">3. Ouvrir le Space <code>/docs</code> dans un nouvel onglet si le jury veut voir Swagger.</div>
          <div class="step">4. Cliquer sur <strong>Afficher preuve PostgreSQL</strong> pour la traçabilite locale.</div>
          <div class="step">5. Cliquer sur <strong>Afficher qualite / couverture</strong> pour afficher les tests et Ruff.</div>
        </div>
      </section>

      <section class="grid two">
        <div class="panel grid">
          <h2>2. Statuts publics et locaux</h2>
          <div class="status-row" id="status-cards"></div>
          <pre id="status-output">Chargement des statuts...</pre>
        </div>
        <div class="panel grid">
          <h2>3. Dernier snapshot</h2>
          <pre id="snapshot-output">Chargement du snapshot...</pre>
        </div>
      </section>

      <section class="grid two">
        <div class="panel grid">
          <h2>4. Resultat demo publique</h2>
          <pre id="public-output">Aucun run public lance pour le moment.</pre>
        </div>
        <div class="panel grid">
          <h2>5. Preuve locale PostgreSQL</h2>
          <pre id="db-output">Aucune preuve SQL chargee pour le moment.</pre>
        </div>
      </section>

      <section class="grid two">
        <div class="panel grid">
          <h2>6. Qualite / couverture</h2>
          <pre id="quality-output">Aucune commande qualite lancee pour le moment.</pre>
        </div>
        <div class="panel grid">
          <h2>7. Plan B oral</h2>
          <div class="muted-box">
            <p>Si le Space ralentit :</p>
            <p>1. ouvrir <code>__LOCAL_BASE_URL__/docs</code></p>
            <p>2. garder cette page comme cockpit</p>
            <p>3. finir avec la preuve SQL et la couverture locale</p>
          </div>
        </div>
      </section>
    </main>
    <script>
      const ids = {
        statusCards: document.getElementById("status-cards"),
        statusOutput: document.getElementById("status-output"),
        publicOutput: document.getElementById("public-output"),
        dbOutput: document.getElementById("db-output"),
        qualityOutput: document.getElementById("quality-output"),
        snapshotOutput: document.getElementById("snapshot-output"),
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

      function renderStatusCards(data) {
        const cards = [
          ["Space /docs", data.public_status?.docs_status],
          ["Space /health", data.public_status?.health_status],
          ["Local DB", data.local_health?.database_connected ? 200 : 503],
          ["Snapshot", data.snapshot?.available ? 200 : 404],
        ];

        ids.statusCards.innerHTML = cards.map(([label, code]) => `
          <div class="status-card">
            <p>${label}</p>
            <p class="${statusClass(code)}">${code ?? "n/a"}</p>
          </div>
        `).join("");
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
          renderStatusCards(state);
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
        output.textContent = "Execution en cours...";
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
        demo_link = (
            '<p><a class="button-link" href="/demo">Ouvrir le cockpit de soutenance</a></p>'
        )

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
        <p>API FastAPI de prediction d'attrition avec documentation OpenAPI et supervision.</p>
        <p><a href="/docs">Ouvrir Swagger / OpenAPI</a></p>
        <p><a href="/health">Verifier /health</a></p>
        <p><a href="__LOCAL_BASE_URL__/docs">URL locale directe de secours</a></p>
        __DEMO_LINK__
      </section>
    </main>
  </body>
</html>
"""
    return html.replace("__DEMO_LINK__", demo_link).replace(
        "__LOCAL_BASE_URL__", escape(local_base_url)
    )


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
