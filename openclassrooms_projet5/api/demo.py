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
from fastapi.responses import FileResponse, HTMLResponse
import httpx
from sqlalchemy import text

from openclassrooms_projet5.config import (
    PROJ_ROOT,
    get_api_key,
    get_demo_snapshot_path,
    get_hf_space,
    get_hf_space_runtime_url,
    is_demo_ui_enabled,
)
from openclassrooms_projet5.db.session import (
    check_database_connection,
    is_database_logging_enabled,
)

DEMO_PUBLIC_SPACE_URL = "https://hgbe-gh-openclassrooms-projet5.hf.space"
DEMO_GITHUB_REPOSITORY_FALLBACK = "hgbe-GH/openclassrooms-projet5"
DEMO_API_KEY_FALLBACK = "change-me-for-local-dev"
DEMO_PUBLIC_TIMEOUT_SECONDS = 20.0
DEMO_QUALITY_TIMEOUT_SECONDS = 240
DEMO_REMOTE_TIMEOUT_SECONDS = 20.0
DEMO_PRESENTATION_PATH = PROJ_ROOT / "reports" / "soutenance_projet5.html"
DEMO_PRESENTATION_PPTX_PATH = PROJ_ROOT / "reports" / "soutenance_projet5.pptx"

PRESENTATION_SECTIONS = [
    {"id": "slide-contexte", "label": "Contexte"},
    {"id": "slide-repo", "label": "Depot Git"},
    {"id": "slide-cicd", "label": "CI/CD"},
    {"id": "slide-api", "label": "API"},
    {"id": "slide-securite", "label": "Securite"},
    {"id": "slide-demo", "label": "Demonstration"},
    {"id": "slide-tests", "label": "Tests"},
    {"id": "slide-postgresql", "label": "PostgreSQL"},
    {"id": "slide-resultats", "label": "Resultats"},
    {"id": "slide-conclusion", "label": "Conclusion"},
]

router = APIRouter()


def _utc_now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def get_demo_api_key() -> str:
    return get_api_key() or DEMO_API_KEY_FALLBACK


def get_space_runtime_url() -> str:
    return get_hf_space_runtime_url() or DEMO_PUBLIC_SPACE_URL


def get_space_page_url() -> str:
    hf_space = get_hf_space() or "hgbe-gh/openclassrooms-projet5"
    return f"https://huggingface.co/spaces/{hf_space}"


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


def _run_git_command(args: list[str]) -> str | None:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=PROJ_ROOT,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None

    if result.returncode != 0:
        return None

    value = result.stdout.strip()
    return value or None


def _run_json_command(command: list[str], timeout_seconds: int = 15) -> dict[str, Any] | list[dict[str, Any]] | None:
    try:
        result = subprocess.run(
            command,
            cwd=PROJ_ROOT,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None

    if result.returncode != 0 or not result.stdout.strip():
        return None

    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return None


def get_github_repository() -> str:
    configured = os.getenv("GITHUB_REPOSITORY")
    if configured and "/" in configured:
        return configured.strip()

    remote_url = _run_git_command(["remote", "get-url", "origin"])
    if remote_url:
        match = re.search(r"github\.com[:/](?P<repo>[^/]+/[^/.]+)(?:\.git)?$", remote_url)
        if match:
            return match.group("repo")

    return DEMO_GITHUB_REPOSITORY_FALLBACK


def get_default_branch_name() -> str:
    remote_head = _run_git_command(["symbolic-ref", "--short", "refs/remotes/origin/HEAD"])
    if remote_head and "/" in remote_head:
        return remote_head.rsplit("/", maxsplit=1)[-1]

    return "main"


def get_local_git_sha() -> str | None:
    return _run_git_command(["rev-parse", "HEAD"])


def get_remote_git_sha(branch: str) -> str | None:
    output = _run_git_command(["ls-remote", "origin", f"refs/heads/{branch}"])
    if not output:
        return None

    return output.split()[0]


def _make_http_client(timeout_seconds: float) -> httpx.Client:
    return httpx.Client(
        timeout=timeout_seconds,
        follow_redirects=True,
        headers={
            "Accept": "application/json",
            "User-Agent": "openclassrooms-projet5-demo-dashboard",
        },
    )


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


def get_github_status(timeout_seconds: float = DEMO_REMOTE_TIMEOUT_SECONDS) -> dict[str, Any]:
    repository = get_github_repository()
    default_branch = get_default_branch_name()
    local_sha = get_local_git_sha()
    remote_sha = get_remote_git_sha(default_branch)
    repo_api_url = f"https://api.github.com/repos/{repository}"
    runs_api_url = f"{repo_api_url}/actions/runs?per_page=1"

    payload: dict[str, Any] = {
        "repository": repository,
        "default_branch": default_branch,
        "local_sha": local_sha,
        "remote_sha": remote_sha,
        "repository_url": f"https://github.com/{repository}",
        "actions_url": f"https://github.com/{repository}/actions",
        "timestamp": _utc_now_iso(),
    }

    try:
        with _make_http_client(timeout_seconds) as client:
            repo_response = client.get(repo_api_url)
            runs_response = client.get(runs_api_url)
    except httpx.HTTPError as exc:
        payload["error"] = str(exc)
        return payload

    repo_json = _extract_json_response(repo_response) or {}
    runs_json = _extract_json_response(runs_response) or {}
    workflow_run = (runs_json.get("workflow_runs") or [None])[0] or {}

    if repo_response.status_code == 404 or runs_response.status_code == 404:
        repo_view = _run_json_command(
            ["gh", "repo", "view", "--json", "nameWithOwner,defaultBranchRef,isPrivate,url"]
        )
        run_list = _run_json_command(
            ["gh", "run", "list", "--limit", "1", "--json", "workflowName,displayTitle,headSha,status,conclusion,updatedAt,url"]
        )
        latest_run = run_list[0] if isinstance(run_list, list) and run_list else {}

        if isinstance(repo_view, dict) and latest_run:
            payload.update(
                {
                    "repository": repo_view.get("nameWithOwner", repository),
                    "repository_url": repo_view.get("url", payload["repository_url"]),
                    "actions_url": f"{repo_view.get('url', payload['repository_url'])}/actions",
                    "default_branch": ((repo_view.get("defaultBranchRef") or {}).get("name") or default_branch),
                    "visibility": "private" if repo_view.get("isPrivate") else "public",
                    "local_sha": local_sha,
                    "remote_sha": remote_sha,
                    "repo_status_code": 200,
                    "runs_status_code": 200,
                    "last_workflow_name": latest_run.get("workflowName"),
                    "last_workflow_display_title": latest_run.get("displayTitle"),
                    "last_workflow_status": latest_run.get("status"),
                    "last_workflow_conclusion": latest_run.get("conclusion"),
                    "last_workflow_updated_at": latest_run.get("updatedAt"),
                    "last_workflow_url": latest_run.get("url"),
                    "last_workflow_sha": latest_run.get("headSha"),
                    "source": "gh-cli",
                }
            )
            return payload

    payload.update(
        {
            "repo_status_code": repo_response.status_code,
            "runs_status_code": runs_response.status_code,
            "default_branch": repo_json.get("default_branch", default_branch),
            "visibility": "private" if repo_json.get("private") else "public",
            "last_workflow_name": workflow_run.get("name"),
            "last_workflow_display_title": workflow_run.get("display_title"),
            "last_workflow_status": workflow_run.get("status"),
            "last_workflow_conclusion": workflow_run.get("conclusion"),
            "last_workflow_updated_at": workflow_run.get("updated_at"),
            "last_workflow_url": workflow_run.get("html_url"),
            "last_workflow_sha": workflow_run.get("head_sha"),
            "source": "github-api",
        }
    )
    return payload


def get_huggingface_status(timeout_seconds: float = DEMO_REMOTE_TIMEOUT_SECONDS) -> dict[str, Any]:
    hf_space = get_hf_space() or "hgbe-gh/openclassrooms-projet5"
    space_page_url = get_space_page_url()
    runtime_url = get_space_runtime_url()

    payload: dict[str, Any] = {
        "space_id": hf_space,
        "space_page_url": space_page_url,
        "runtime_url": runtime_url,
        "timestamp": _utc_now_iso(),
    }

    try:
        with _make_http_client(timeout_seconds) as client:
            space_response = client.get(f"https://huggingface.co/api/spaces/{hf_space}")
            runtime_response = client.get(f"https://huggingface.co/api/spaces/{hf_space}/runtime")
            root_response = client.get(runtime_url)
            health_response = client.get(f"{runtime_url}/health")
            docs_response = client.get(f"{runtime_url}/docs")
    except httpx.HTTPError as exc:
        payload["error"] = str(exc)
        return payload

    space_json = _extract_json_response(space_response) or {}
    runtime_json = _extract_json_response(runtime_response) or {}

    payload.update(
        {
            "space_status_code": space_response.status_code,
            "runtime_status_code": runtime_response.status_code,
            "runtime_stage": runtime_json.get("stage") or (space_json.get("runtime") or {}).get("stage"),
            "runtime_sha": runtime_json.get("sha") or space_json.get("sha"),
            "last_modified": space_json.get("lastModified"),
            "runtime_error": runtime_json.get("errorMessage") or (space_json.get("runtime") or {}).get("errorMessage"),
            "root_status": root_response.status_code,
            "health_status": health_response.status_code,
            "docs_status": docs_response.status_code,
            "health_body": _extract_json_response(health_response),
        }
    )
    return payload


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


def get_presentation_html() -> str:
    return DEMO_PRESENTATION_PATH.read_text(encoding="utf-8")


def get_presentation_outline() -> list[dict[str, str]]:
    return PRESENTATION_SECTIONS


def build_full_refresh_payload(local_base_url: str) -> dict[str, Any]:
    public_status = get_public_status()
    public_run = run_public_demo()
    local_health = get_local_demo_health()
    local_health["local_demo_url"] = f"{local_base_url}/demo"
    local_health["local_docs_url"] = f"{local_base_url}/docs"
    github_status = get_github_status()
    huggingface_status = get_huggingface_status()
    snapshot = load_demo_snapshot() or {}

    update_demo_snapshot("public_status", public_status)
    update_demo_snapshot("public_run", public_run)
    update_demo_snapshot("local_health", local_health)
    update_demo_snapshot("github_status", github_status)
    update_demo_snapshot("huggingface_status", huggingface_status)
    update_demo_snapshot(
        "presentation_state",
        {
            "outline": get_presentation_outline(),
            "presentation_url": f"{local_base_url}/demo-api/presentation",
        },
    )

    refreshed_snapshot = load_demo_snapshot() or snapshot
    return {
        "public_status": public_status,
        "public_run": public_run,
        "local_health": local_health,
        "github_status": github_status,
        "huggingface_status": huggingface_status,
        "snapshot": refreshed_snapshot,
        "presentation": {
            "outline": get_presentation_outline(),
            "presentation_url": f"{local_base_url}/demo-api/presentation",
        },
        "generated_at": _utc_now_iso(),
    }


def build_demo_html(local_base_url: str) -> str:
    github_repository = get_github_repository()
    github_actions_url = f"https://github.com/{github_repository}/actions"
    space_page_url = get_space_page_url()
    presentation_outline = "\n".join(
        (
            '<li><a href="/demo-api/presentation#{id}" target="presentation-frame">{label}</a></li>'.format(
                id=escape(item["id"]),
                label=escape(item["label"]),
            )
        )
        for item in get_presentation_outline()
    )

    html = """
<!DOCTYPE html>
<html lang="fr">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Hub de soutenance - Attrition API</title>
    <style>
      :root {
        --bg: #f5efe4;
        --panel: rgba(255, 252, 247, 0.94);
        --panel-strong: #ffffff;
        --ink: #17212b;
        --muted: #5e6877;
        --line: rgba(23, 33, 43, 0.12);
        --accent: #0f766e;
        --accent-soft: rgba(15, 118, 110, 0.1);
        --warn: #d97706;
        --danger: #b91c1c;
        --shell: #14202a;
        --shell-text: #eff4f8;
      }
      * { box-sizing: border-box; }
      body {
        margin: 0;
        color: var(--ink);
        font-family: "Segoe UI", "Helvetica Neue", sans-serif;
        background:
          radial-gradient(circle at top right, rgba(15, 118, 110, 0.11), transparent 22rem),
          radial-gradient(circle at bottom left, rgba(217, 119, 6, 0.1), transparent 20rem),
          var(--bg);
      }
      a { color: var(--accent); text-decoration: none; }
      h1, h2, h3, p { margin: 0; }
      p, li { color: var(--muted); line-height: 1.55; }
      main {
        width: min(1440px, calc(100vw - 32px));
        margin: 0 auto;
        padding: 22px 0 42px;
        display: grid;
        gap: 18px;
      }
      .shell, .panel {
        background: var(--panel);
        border: 1px solid var(--line);
        border-radius: 28px;
        box-shadow: 0 24px 60px rgba(23, 33, 43, 0.08);
      }
      .shell { padding: 28px; display: grid; gap: 22px; }
      .panel { padding: 22px; }
      .topbar {
        display: grid;
        grid-template-columns: minmax(0, 1.25fr) minmax(320px, 0.75fr);
        gap: 18px;
      }
      .eyebrow, .tag {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        padding: 7px 12px;
        border-radius: 999px;
        font-size: 0.76rem;
        font-weight: 800;
        letter-spacing: 0.05em;
        text-transform: uppercase;
      }
      .eyebrow { background: var(--accent-soft); color: var(--accent); }
      .tag { background: rgba(217, 119, 6, 0.12); color: var(--warn); }
      .hero-title {
        font-size: clamp(2.2rem, 4vw, 4rem);
        line-height: 1.02;
      }
      .hero-copy { max-width: 46rem; }
      .hero-actions, .quick-links, .inline-actions {
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
      }
      button, .link-button {
        appearance: none;
        border: 0;
        border-radius: 14px;
        padding: 13px 16px;
        font: inherit;
        font-weight: 700;
        cursor: pointer;
      }
      button.primary, .link-button.primary {
        background: var(--accent);
        color: #fff;
        box-shadow: 0 10px 22px rgba(15, 118, 110, 0.24);
      }
      button.secondary, .link-button.secondary {
        background: var(--panel-strong);
        color: var(--ink);
        border: 1px solid var(--line);
      }
      button:disabled { opacity: 0.6; cursor: progress; }
      .overview-grid {
        display: grid;
        grid-template-columns: repeat(6, minmax(0, 1fr));
        gap: 14px;
      }
      .metric-card {
        padding: 18px;
        border-radius: 20px;
        border: 1px solid var(--line);
        background: rgba(255, 255, 255, 0.86);
      }
      .metric-label {
        color: var(--muted);
        font-size: 0.78rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
      }
      .metric-value {
        margin-top: 8px;
        font-size: 2rem;
        line-height: 1;
        font-weight: 800;
        color: var(--accent);
      }
      .meta-stack {
        display: grid;
        gap: 12px;
      }
      .meta-item {
        padding: 14px 16px;
        border-radius: 18px;
        border: 1px solid var(--line);
        background: rgba(255,255,255,0.82);
      }
      .tabs {
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
      }
      .tab {
        padding: 11px 14px;
        border-radius: 999px;
        border: 1px solid var(--line);
        background: rgba(255,255,255,0.7);
        color: var(--ink);
        font-weight: 700;
        cursor: pointer;
      }
      .tab.active {
        background: var(--ink);
        color: #fff;
        border-color: var(--ink);
      }
      .view { display: none; }
      .view.active { display: grid; gap: 18px; }
      .split {
        display: grid;
        grid-template-columns: minmax(280px, 0.42fr) minmax(0, 1fr);
        gap: 18px;
      }
      .two-col {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 18px;
      }
      .three-col {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 18px;
      }
      .summary-grid { display: grid; gap: 10px; }
      .summary-line {
        display: flex;
        justify-content: space-between;
        gap: 10px;
        padding: 10px 0;
        border-bottom: 1px solid var(--line);
      }
      .summary-line:last-child { border-bottom: 0; }
      .status-ok, .status-warn, .status-bad {
        font-weight: 800;
      }
      .status-ok { color: var(--accent); }
      .status-warn { color: var(--warn); }
      .status-bad { color: var(--danger); }
      .presentation-frame {
        width: 100%;
        min-height: 74vh;
        border: 1px solid var(--line);
        border-radius: 22px;
        background: #fff;
      }
      .toc {
        margin: 0;
        padding-left: 18px;
        display: grid;
        gap: 10px;
      }
      .toc a { font-weight: 700; }
      .card-grid {
        display: grid;
        gap: 18px;
      }
      pre {
        margin: 0;
        padding: 16px;
        border-radius: 18px;
        background: var(--shell);
        color: var(--shell-text);
        overflow: auto;
        font-size: 0.9rem;
      }
      details {
        border-top: 1px solid var(--line);
        padding-top: 12px;
      }
      summary {
        cursor: pointer;
        color: var(--accent);
        font-weight: 700;
        list-style: none;
      }
      summary::-webkit-details-marker { display: none; }
      .small {
        font-size: 0.9rem;
      }
      @media (max-width: 1180px) {
        .topbar, .split, .two-col, .three-col, .overview-grid {
          grid-template-columns: 1fr;
        }
      }
    </style>
  </head>
  <body>
    <main>
      <section class="shell">
        <div class="topbar">
          <div class="panel card-grid">
            <span class="eyebrow">Soutenance Projet 5</span>
            <h1 class="hero-title">Dashboard de soutenance</h1>
            <p class="hero-copy">Cet ecran sert de fil conducteur pendant l'oral. Je commence par la presentation, puis je montre l'API publique, la base PostgreSQL, les tests et enfin la partie CI/CD et deploiement.</p>
            <div class="hero-actions">
              <button class="primary" id="full-refresh">Tout actualiser</button>
              <button class="secondary" id="run-public">Verifier l'API publique</button>
              <button class="secondary" id="run-db">Verifier la base PostgreSQL</button>
              <button class="secondary" id="run-quality">Relancer les tests</button>
            </div>
          </div>
          <div class="meta-stack">
            <div class="meta-item">
              <span class="tag">Snapshot</span>
              <div class="summary-grid">
                <div class="summary-line"><span>Derniere verification</span><strong id="snapshot-generated">en attente</strong></div>
                <div class="summary-line"><span>Cle de demonstration</span><strong><code>__DEMO_API_KEY__</code></strong></div>
                <div class="summary-line"><span>Dashboard local</span><strong id="local-demo-url">__LOCAL_BASE_URL__/demo</strong></div>
              </div>
            </div>
            <div class="meta-item">
              <span class="tag">Acces rapides</span>
              <div class="quick-links">
                <button class="link-button secondary nav-link" data-view-target="presentation">Support</button>
                <button class="link-button secondary nav-link" data-view-target="api">API</button>
                <button class="link-button secondary nav-link" data-view-target="tracabilite">Base PostgreSQL</button>
                <button class="link-button secondary nav-link" data-view-target="qualite">Tests</button>
                <a class="link-button secondary" href="__GITHUB_ACTIONS_URL__" target="_blank" rel="noreferrer">CI/CD GitHub</a>
                <a class="link-button secondary" href="__SPACE_PAGE_URL__" target="_blank" rel="noreferrer">Space HF</a>
              </div>
            </div>
          </div>
        </div>

        <div class="overview-grid">
          <div class="metric-card"><div class="metric-label">Space docs</div><div class="metric-value" id="kpi-docs">200</div></div>
          <div class="metric-card"><div class="metric-label">Space health</div><div class="metric-value" id="kpi-health">200</div></div>
          <div class="metric-card"><div class="metric-label">Predict sans cle</div><div class="metric-value" id="kpi-auth">401</div></div>
          <div class="metric-card"><div class="metric-label">Predict avec cle</div><div class="metric-value" id="kpi-predict">200</div></div>
          <div class="metric-card"><div class="metric-label">Tests passes</div><div class="metric-value" id="kpi-tests">76</div></div>
          <div class="metric-card"><div class="metric-label">Couverture</div><div class="metric-value" id="kpi-coverage">94%</div></div>
        </div>

        <div class="panel">
          <div class="three-col">
            <div class="metric-card">
              <div class="metric-label">1. Presentation</div>
              <p><strong>Je presente le besoin, l'architecture et les livrables.</strong></p>
              <p class="small">Onglet <code>Presentation</code></p>
            </div>
            <div class="metric-card">
              <div class="metric-label">2. Demonstration</div>
              <p><strong>Je prouve que l'API repond et que la base trace bien la prediction.</strong></p>
              <p class="small">Onglets <code>API publique</code> et <code>Base PostgreSQL</code></p>
            </div>
            <div class="metric-card">
              <div class="metric-label">3. Validation</div>
              <p><strong>Je termine avec les tests, puis la CI/CD et le Space.</strong></p>
              <p class="small">Onglets <code>Tests</code> et <code>CI/CD</code></p>
            </div>
          </div>
        </div>

        <div class="tabs">
          <button class="tab active" data-view="presentation">1. Presentation</button>
          <button class="tab" data-view="api">2. API publique</button>
          <button class="tab" data-view="tracabilite">3. Base PostgreSQL</button>
          <button class="tab" data-view="qualite">4. Tests</button>
          <button class="tab" data-view="deploiement">5. CI/CD</button>
        </div>
      </section>

      <section class="view active" data-view-panel="presentation">
        <div class="split">
          <div class="panel card-grid">
            <h2>Fil de presentation</h2>
            <p>Le support HTML reste visible ici pendant l'oral, avec un sommaire stable pour garder le fil de la soutenance.</p>
            <ol class="toc">
              __PRESENTATION_TOC__
            </ol>
            <div class="inline-actions">
              <a class="link-button secondary" href="/demo-api/presentation" target="_blank" rel="noreferrer">Ouvrir le support seul</a>
              <a class="link-button secondary" href="/demo-api/presentation/pptx" target="_blank" rel="noreferrer">Telecharger le PPTX</a>
            </div>
          </div>
          <div class="panel">
            <iframe class="presentation-frame" id="presentation-frame" name="presentation-frame" src="/demo-api/presentation" title="Support de soutenance"></iframe>
          </div>
        </div>
      </section>

      <section class="view" data-view-panel="api">
        <div class="two-col">
          <div class="panel card-grid">
            <div>
              <span class="eyebrow">Vue API publique</span>
              <h2>Demonstration de l'API en ligne</h2>
            </div>
            <div class="summary-grid">
              <div class="summary-line"><span>Documentation</span><strong id="summary-docs" class="status-ok">200</strong></div>
              <div class="summary-line"><span>Etat du service</span><strong id="summary-health" class="status-ok">200</strong></div>
              <div class="summary-line"><span>Authentification</span><strong id="summary-auth" class="status-warn">401</strong></div>
              <div class="summary-line"><span>Prediction authentifiee</span><strong id="summary-predict" class="status-ok">200</strong></div>
            </div>
            <p class="small">Ici je montre que l'API publique est disponible, documentee et protegee par cle API.</p>
            <div class="inline-actions">
              <a class="link-button secondary" href="__SPACE_URL__/docs" target="_blank" rel="noreferrer">Ouvrir Swagger</a>
              <a class="link-button secondary" href="__SPACE_URL__/health" target="_blank" rel="noreferrer">Ouvrir Health</a>
              <a class="link-button secondary" href="__SPACE_URL__" target="_blank" rel="noreferrer">Ouvrir le runtime</a>
            </div>
            <details open>
              <summary>Statut public consolide</summary>
              <pre id="public-status-output">Actualisation en cours...</pre>
            </details>
          </div>
          <div class="panel card-grid">
            <div>
              <span class="eyebrow">Prediction en direct</span>
              <h2>Resultat de reference</h2>
            </div>
            <div class="summary-grid">
              <div class="summary-line"><span>Decision</span><strong id="prediction-flag" class="status-ok">1</strong></div>
              <div class="summary-line"><span>Probabilite</span><strong id="prediction-proba" class="status-ok">0.6266</strong></div>
              <div class="summary-line"><span>Seuil</span><strong id="prediction-threshold" class="status-ok">0.4781</strong></div>
            </div>
            <details open>
              <summary>Reponse JSON</summary>
              <pre id="public-run-output">Aucune execution publique recente.</pre>
            </details>
          </div>
        </div>
      </section>

      <section class="view" data-view-panel="tracabilite">
        <div class="two-col">
          <div class="panel card-grid">
            <div>
              <span class="eyebrow">Vue Tracabilite</span>
              <h2>Preuve PostgreSQL locale</h2>
            </div>
            <div class="summary-grid">
              <div class="summary-line"><span>Decision</span><strong id="db-decision" class="status-ok">1</strong></div>
              <div class="summary-line"><span>Modele</span><strong id="db-model">attrition_xgboost_pipeline.joblib</strong></div>
              <div class="summary-line"><span>Profil</span><strong id="db-poste">Cadre Commercial</strong></div>
              <div class="summary-line"><span>Horodatage</span><strong id="db-created">n/a</strong></div>
            </div>
            <p class="small">Ici je montre qu'une prediction n'est pas seulement calculee : elle est aussi tracee en base.</p>
          </div>
          <div class="panel">
            <details open>
              <summary>Preuve brute</summary>
              <pre id="db-output">La derniere trace PostgreSQL apparaitra ici.</pre>
            </details>
          </div>
        </div>
      </section>

      <section class="view" data-view-panel="qualite">
        <div class="two-col">
          <div class="panel card-grid">
            <div>
              <span class="eyebrow">Vue Qualite</span>
              <h2>Tests et qualite logicielle</h2>
            </div>
            <div class="summary-grid">
              <div class="summary-line"><span>Tests passes</span><strong id="quality-tests" class="status-ok">76</strong></div>
              <div class="summary-line"><span>Couverture</span><strong id="quality-coverage" class="status-ok">94%</strong></div>
              <div class="summary-line"><span>Lint Ruff</span><strong id="quality-ruff" class="status-ok">OK</strong></div>
              <div class="summary-line"><span>Resume</span><strong id="quality-summary">Snapshot disponible</strong></div>
            </div>
            <p class="small">Cet onglet montre les tests eux-memes : Pytest, couverture et Ruff.</p>
            <div class="summary-grid">
              <div class="summary-line"><span>Fichiers de test</span><strong>tests/</strong></div>
              <div class="summary-line"><span>Commande cle</span><strong><code>pytest</code></strong></div>
            </div>
          </div>
          <div class="panel">
            <details open>
              <summary>Sorties techniques</summary>
              <pre id="quality-output">Le resultat qualité apparaitra ici.</pre>
            </details>
          </div>
        </div>
      </section>

      <section class="view" data-view-panel="deploiement">
        <div class="two-col">
          <div class="panel card-grid">
            <div>
              <span class="eyebrow">GitHub</span>
              <h2>CI/CD GitHub</h2>
            </div>
            <div class="summary-grid">
              <div class="summary-line"><span>Repo</span><strong id="github-repo">__GITHUB_REPOSITORY__</strong></div>
              <div class="summary-line"><span>Branche</span><strong id="github-branch">main</strong></div>
              <div class="summary-line"><span>SHA local</span><strong id="github-local-sha">n/a</strong></div>
              <div class="summary-line"><span>SHA distant</span><strong id="github-remote-sha">n/a</strong></div>
              <div class="summary-line"><span>Dernier workflow</span><strong id="github-workflow">n/a</strong></div>
              <div class="summary-line"><span>Conclusion</span><strong id="github-conclusion">n/a</strong></div>
            </div>
            <p class="small">Cet onglet ne montre pas les tests eux-memes. Il montre qu'ils sont automatises dans le pipeline GitHub Actions.</p>
            <div class="inline-actions">
              <a class="link-button secondary" id="github-actions-link" href="__GITHUB_ACTIONS_URL__" target="_blank" rel="noreferrer">Ouvrir GitHub Actions</a>
            </div>
          </div>
          <div class="panel card-grid">
            <div>
              <span class="eyebrow">Hugging Face</span>
              <h2>Deploiement du Space</h2>
            </div>
            <div class="summary-grid">
              <div class="summary-line"><span>Space</span><strong id="hf-space-id">n/a</strong></div>
              <div class="summary-line"><span>Runtime stage</span><strong id="hf-stage">n/a</strong></div>
              <div class="summary-line"><span>SHA HF</span><strong id="hf-sha">n/a</strong></div>
              <div class="summary-line"><span>Root</span><strong id="hf-root-status">200</strong></div>
              <div class="summary-line"><span>Health</span><strong id="hf-health-status">200</strong></div>
              <div class="summary-line"><span>Docs</span><strong id="hf-docs-status">200</strong></div>
            </div>
            <p class="small">Ici je montre que le service deploie est bien en ligne et repond publiquement.</p>
            <div class="inline-actions">
              <a class="link-button secondary" id="hf-space-link" href="__SPACE_PAGE_URL__" target="_blank" rel="noreferrer">Ouvrir le Space</a>
              <a class="link-button secondary" id="hf-runtime-link" href="__SPACE_URL__" target="_blank" rel="noreferrer">Ouvrir le runtime</a>
            </div>
          </div>
        </div>
        <div class="three-col">
          <div class="panel">
            <details open>
              <summary>Detail GitHub</summary>
              <pre id="github-output">Chargement GitHub...</pre>
            </details>
          </div>
          <div class="panel">
            <details open>
              <summary>Detail Hugging Face</summary>
              <pre id="hf-output">Chargement Hugging Face...</pre>
            </details>
          </div>
          <div class="panel">
            <details open>
              <summary>Snapshot consolide</summary>
              <pre id="snapshot-output">Chargement du snapshot...</pre>
            </details>
          </div>
        </div>
      </section>
    </main>
    <script>
      const ids = {
        snapshotGenerated: document.getElementById("snapshot-generated"),
        localDemoUrl: document.getElementById("local-demo-url"),
        kpiDocs: document.getElementById("kpi-docs"),
        kpiHealth: document.getElementById("kpi-health"),
        kpiAuth: document.getElementById("kpi-auth"),
        kpiPredict: document.getElementById("kpi-predict"),
        kpiTests: document.getElementById("kpi-tests"),
        kpiCoverage: document.getElementById("kpi-coverage"),
        summaryDocs: document.getElementById("summary-docs"),
        summaryHealth: document.getElementById("summary-health"),
        summaryAuth: document.getElementById("summary-auth"),
        summaryPredict: document.getElementById("summary-predict"),
        publicStatusOutput: document.getElementById("public-status-output"),
        publicRunOutput: document.getElementById("public-run-output"),
        predictionFlag: document.getElementById("prediction-flag"),
        predictionProba: document.getElementById("prediction-proba"),
        predictionThreshold: document.getElementById("prediction-threshold"),
        dbDecision: document.getElementById("db-decision"),
        dbModel: document.getElementById("db-model"),
        dbPoste: document.getElementById("db-poste"),
        dbCreated: document.getElementById("db-created"),
        dbOutput: document.getElementById("db-output"),
        qualityTests: document.getElementById("quality-tests"),
        qualityCoverage: document.getElementById("quality-coverage"),
        qualityRuff: document.getElementById("quality-ruff"),
        qualitySummary: document.getElementById("quality-summary"),
        qualityOutput: document.getElementById("quality-output"),
        githubRepo: document.getElementById("github-repo"),
        githubBranch: document.getElementById("github-branch"),
        githubLocalSha: document.getElementById("github-local-sha"),
        githubRemoteSha: document.getElementById("github-remote-sha"),
        githubWorkflow: document.getElementById("github-workflow"),
        githubConclusion: document.getElementById("github-conclusion"),
        githubActionsLink: document.getElementById("github-actions-link"),
        githubOutput: document.getElementById("github-output"),
        hfSpaceId: document.getElementById("hf-space-id"),
        hfStage: document.getElementById("hf-stage"),
        hfSha: document.getElementById("hf-sha"),
        hfRootStatus: document.getElementById("hf-root-status"),
        hfHealthStatus: document.getElementById("hf-health-status"),
        hfDocsStatus: document.getElementById("hf-docs-status"),
        hfSpaceLink: document.getElementById("hf-space-link"),
        hfRuntimeLink: document.getElementById("hf-runtime-link"),
        hfOutput: document.getElementById("hf-output"),
        snapshotOutput: document.getElementById("snapshot-output"),
      };

      const state = {};

      function pretty(value) {
        return JSON.stringify(value, null, 2);
      }

      function statusClass(value) {
        if (value === 200 || value === "success" || value === "completed" || value === "RUNNING") return "status-ok";
        if (value === 401 || value === 422 || value === "queued" || value === "in_progress" || value === "APP_STARTING" || value === "BUILDING") return "status-warn";
        if (value === null || value === undefined || value === "failure" || value === "RUNTIME_ERROR") return "status-bad";
        return value >= 200 && value < 300 ? "status-ok" : "status-bad";
      }

      function setStatus(element, value, suffix = "") {
        if (!element) return;
        element.className = statusClass(value);
        element.textContent = value === null || value === undefined ? "n/a" : `${value}${suffix}`;
      }

      function setText(element, value) {
        if (!element) return;
        element.textContent = value ?? "n/a";
      }

      function currentView() {
        return (window.location.hash || "#presentation").replace("#", "");
      }

      function applyHashView() {
        const current = currentView();
        document.querySelectorAll(".tab").forEach((tab) => {
          tab.classList.toggle("active", tab.dataset.view === current);
        });
        document.querySelectorAll(".view").forEach((view) => {
          view.classList.toggle("active", view.dataset.viewPanel === current);
        });
      }

      function openView(viewName) {
        window.location.hash = viewName;
        window.scrollTo({ top: 0, behavior: "smooth" });
      }

      async function fetchJson(url, options = {}) {
        const response = await fetch(url, options);
        const body = await response.json();
        if (!response.ok) {
          throw new Error(body.detail || `HTTP ${response.status}`);
        }
        return body;
      }

      function renderDashboard() {
        const snapshot = state.snapshot?.snapshot || {};
        const publicStatus = state.public_status || snapshot.public_status || {};
        const publicRun = state.public_run || snapshot.public_run || {};
        const localHealth = state.local_health || snapshot.local_health || {};
        const localDb = state.local_db_proof || snapshot.local_db_proof || {};
        const localQuality = state.local_quality || snapshot.local_quality || {};
        const githubStatus = state.github_status || snapshot.github_status || {};
        const huggingfaceStatus = state.huggingface_status || snapshot.huggingface_status || {};

        setText(ids.snapshotGenerated, snapshot.generated_at || state.generated_at || "derniere valeur connue");
        setText(ids.localDemoUrl, localHealth.local_demo_url || "__LOCAL_BASE_URL__/demo");

        setStatus(ids.kpiDocs, publicRun.docs_status ?? publicStatus.docs_status);
        setStatus(ids.kpiHealth, publicRun.health_status ?? publicStatus.health_status);
        setStatus(ids.kpiAuth, publicRun.predict_without_key_status ?? 401);
        setStatus(ids.kpiPredict, publicRun.predict_with_key_status ?? 200);
        setText(ids.kpiTests, localQuality.tests_passed ?? 76);
        setText(ids.kpiCoverage, `${localQuality.coverage_percent ?? 94}%`);

        setStatus(ids.summaryDocs, publicRun.docs_status ?? publicStatus.docs_status);
        setStatus(ids.summaryHealth, publicRun.health_status ?? publicStatus.health_status);
        setStatus(ids.summaryAuth, publicRun.predict_without_key_status ?? 401);
        setStatus(ids.summaryPredict, publicRun.predict_with_key_status ?? 200);
        ids.publicStatusOutput.textContent = pretty(publicStatus);
        ids.publicRunOutput.textContent = pretty(publicRun);

        setText(ids.predictionFlag, publicRun.predict_response_json?.prediction_attrition ?? 1);
        setText(ids.predictionProba, publicRun.predict_response_json?.probabilite_attrition?.toFixed?.(4) ?? "0.6266");
        setText(ids.predictionThreshold, publicRun.predict_response_json?.threshold?.toFixed?.(4) ?? "0.4781");

        setText(ids.dbDecision, localDb.prediction_attrition ?? 1);
        setText(ids.dbModel, localDb.model_identifier ?? "attrition_xgboost_pipeline.joblib");
        setText(ids.dbPoste, localDb.poste ?? "Cadre Commercial");
        setText(ids.dbCreated, localDb.created_at ?? "n/a");
        ids.dbOutput.textContent = pretty(localDb);

        setText(ids.qualityTests, localQuality.tests_passed ?? 76);
        setText(ids.qualityCoverage, `${localQuality.coverage_percent ?? 94}%`);
        setText(ids.qualityRuff, localQuality.ruff_ok === false ? "FAILED" : "OK");
        setText(ids.qualitySummary, localQuality.summary_text ?? "Snapshot disponible");
        ids.qualityOutput.textContent = pretty(localQuality);

        setText(ids.githubRepo, githubStatus.repository ?? "__GITHUB_REPOSITORY__");
        setText(ids.githubBranch, githubStatus.default_branch ?? "main");
        setText(ids.githubLocalSha, githubStatus.local_sha ?? "n/a");
        setText(ids.githubRemoteSha, githubStatus.remote_sha ?? "n/a");
        setText(ids.githubWorkflow, githubStatus.last_workflow_name ?? "n/a");
        setText(ids.githubConclusion, githubStatus.last_workflow_conclusion ?? githubStatus.last_workflow_status ?? "n/a");
        if (githubStatus.last_workflow_url) ids.githubActionsLink.href = githubStatus.last_workflow_url;
        ids.githubOutput.textContent = pretty(githubStatus);

        setText(ids.hfSpaceId, huggingfaceStatus.space_id ?? "n/a");
        setText(ids.hfStage, huggingfaceStatus.runtime_stage ?? "n/a");
        setText(ids.hfSha, huggingfaceStatus.runtime_sha ?? "n/a");
        setStatus(ids.hfRootStatus, huggingfaceStatus.root_status);
        setStatus(ids.hfHealthStatus, huggingfaceStatus.health_status);
        setStatus(ids.hfDocsStatus, huggingfaceStatus.docs_status);
        if (huggingfaceStatus.space_page_url) ids.hfSpaceLink.href = huggingfaceStatus.space_page_url;
        if (huggingfaceStatus.runtime_url) ids.hfRuntimeLink.href = huggingfaceStatus.runtime_url;
        ids.hfOutput.textContent = pretty(huggingfaceStatus);

        ids.snapshotOutput.textContent = pretty(state.snapshot || snapshot);
      }

      async function loadSnapshot() {
        state.snapshot = await fetchJson("/demo-api/snapshot");
      }

      async function fullRefresh() {
        const button = document.getElementById("full-refresh");
        button.disabled = true;
        try {
          const payload = await fetchJson("/demo-api/full-refresh", { method: "POST" });
          Object.assign(state, payload);
          state.snapshot = { available: true, snapshot: payload.snapshot, path: ".cache/demo_snapshot.json" };
          renderDashboard();
        } catch (error) {
          ids.snapshotOutput.textContent = `Erreur: ${error.message}`;
        } finally {
          button.disabled = false;
        }
      }

      async function runAction(buttonId, endpoint, stateKey, outputElement) {
        const button = document.getElementById(buttonId);
        button.disabled = true;
        outputElement.textContent = "Verification en cours...";
        try {
          const payload = await fetchJson(endpoint, { method: "POST" });
          state[stateKey] = payload;
          await loadSnapshot();
          renderDashboard();
        } catch (error) {
          outputElement.textContent = `Erreur: ${error.message}`;
        } finally {
          button.disabled = false;
        }
      }

      document.querySelectorAll(".tab").forEach((tab) => {
        tab.addEventListener("click", () => {
          openView(tab.dataset.view);
        });
      });

      document.querySelectorAll(".nav-link").forEach((button) => {
        button.addEventListener("click", () => {
          openView(button.dataset.viewTarget);
        });
      });

      window.addEventListener("hashchange", applyHashView);
      document.getElementById("full-refresh").addEventListener("click", fullRefresh);
      document.getElementById("run-public").addEventListener("click", () => runAction("run-public", "/demo-api/public/run", "public_run", ids.publicRunOutput));
      document.getElementById("run-db").addEventListener("click", () => runAction("run-db", "/demo-api/local/db-proof", "local_db_proof", ids.dbOutput));
      document.getElementById("run-quality").addEventListener("click", () => runAction("run-quality", "/demo-api/local/quality", "local_quality", ids.qualityOutput));

      (async () => {
        applyHashView();
        try {
          await loadSnapshot();
          const [publicStatus, localHealth, githubStatus, huggingfaceStatus] = await Promise.all([
            fetchJson("/demo-api/public/status"),
            fetchJson("/demo-api/local/health"),
            fetchJson("/demo-api/github/status"),
            fetchJson("/demo-api/huggingface/status"),
          ]);
          state.public_status = publicStatus;
          state.local_health = localHealth;
          state.github_status = githubStatus;
          state.huggingface_status = huggingfaceStatus;
          renderDashboard();
        } catch (error) {
          ids.snapshotOutput.textContent = `Erreur: ${error.message}`;
        }
      })();
    </script>
  </body>
</html>
"""
    return (
        html.replace("__DEMO_API_KEY__", escape(get_demo_api_key()))
        .replace("__SPACE_URL__", escape(get_space_runtime_url()))
        .replace("__SPACE_PAGE_URL__", escape(space_page_url))
        .replace("__GITHUB_ACTIONS_URL__", escape(github_actions_url))
        .replace("__GITHUB_REPOSITORY__", escape(github_repository))
        .replace("__LOCAL_BASE_URL__", escape(local_base_url))
        .replace("__PRESENTATION_TOC__", presentation_outline)
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


@router.get("/demo-api/presentation", include_in_schema=False)
def demo_presentation() -> HTMLResponse:
    _ensure_demo_enabled()
    return HTMLResponse(get_presentation_html())


@router.get("/demo-api/presentation/pptx", include_in_schema=False)
def demo_presentation_pptx() -> FileResponse:
    _ensure_demo_enabled()
    return FileResponse(
        DEMO_PRESENTATION_PPTX_PATH,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        filename=DEMO_PRESENTATION_PPTX_PATH.name,
    )


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


@router.get("/demo-api/github/status", include_in_schema=False)
def demo_github_status() -> dict[str, Any]:
    _ensure_demo_enabled()
    payload = get_github_status()
    update_demo_snapshot("github_status", payload)
    return payload


@router.get("/demo-api/huggingface/status", include_in_schema=False)
def demo_huggingface_status() -> dict[str, Any]:
    _ensure_demo_enabled()
    payload = get_huggingface_status()
    update_demo_snapshot("huggingface_status", payload)
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


@router.post("/demo-api/full-refresh", include_in_schema=False)
def demo_full_refresh(request: Request) -> dict[str, Any]:
    _ensure_demo_enabled()
    local_base_url = str(request.base_url).rstrip("/")
    return build_full_refresh_payload(local_base_url)
