from __future__ import annotations

import json
from typing import Any

import typer

from openclassrooms_projet5.api.demo import (
    get_demo_api_key,
    get_local_db_proof,
    get_local_demo_health,
    get_public_status,
    get_space_runtime_url,
    run_local_quality,
    run_public_demo,
    save_demo_snapshot,
)

app = typer.Typer(add_completion=False, pretty_exceptions_enable=False)


def _capture(label: str, operation) -> dict[str, Any]:
    try:
        payload = operation()
    except Exception as exc:  # noqa: BLE001 - snapshot should keep going.
        return {"label": label, "ok": False, "error": str(exc)}

    return {"label": label, "ok": True, "payload": payload}


@app.command()
def main(skip_quality: bool = typer.Option(False, help="Do not run pytest and Ruff.")) -> None:
    snapshot = {
        "generated_at": None,
        "space_url": get_space_runtime_url(),
        "demo_api_key": get_demo_api_key(),
        "public_status": _capture("public_status", get_public_status),
        "public_run": _capture("public_run", run_public_demo),
        "local_health": _capture("local_health", get_local_demo_health),
        "local_db_proof": _capture("local_db_proof", get_local_db_proof),
        "local_quality": (
            {"label": "local_quality", "ok": True, "payload": {"skipped": True}}
            if skip_quality
            else _capture("local_quality", run_local_quality)
        ),
    }

    snapshot["generated_at"] = snapshot["public_status"].get("payload", {}).get(
        "timestamp"
    ) or snapshot["local_health"].get("payload", {}).get("timestamp")
    snapshot_path = save_demo_snapshot(snapshot)

    typer.echo(
        json.dumps(
            {
                "snapshot_path": str(snapshot_path),
                "space_url": snapshot["space_url"],
                "quality_skipped": skip_quality,
            },
            indent=2,
            ensure_ascii=True,
        )
    )


if __name__ == "__main__":
    app()
