from __future__ import annotations

import argparse
import json
import platform
import sqlite3
import sys
import tempfile
from contextlib import closing
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from rivulet_localops import __version__  # noqa: E402
from rivulet_localops.ledger import SQLiteEventLedger  # noqa: E402
from rivulet_localops.main import create_app  # noqa: E402
from scripts.verify_public_deployment import evaluate_health_payload  # noqa: E402


SUBMISSION = {
    "request": {
        "text": "Overflowing bin and dumped rubbish beside the public litter bin.",
        "coordinates": {"latitude": -42.8867512572958, "longitude": 147.319119003722},
    },
    "proposed_action": "create_draft_work_order",
    "accountable_owner_id": "owner.synthetic-experiment",
    "correlation_id": "cor-support-experiment-001",
}


def environment(**overrides: str) -> dict[str, str]:
    values = {
        "RIVULET_RELEASE": f"v{__version__}",
        "RIVULET_ENVIRONMENT": "synthetic-recovery-experiment",
        "RIVULET_DEPLOYMENT_ID": "local-support-experiment",
        "RIVULET_DEPLOYMENT_SOURCE": "local-script",
    }
    values.update(overrides)
    return values


def run_app_001(root: Path) -> dict[str, Any]:
    ledger_path = root / "app-001.sqlite3"
    degraded = TestClient(
        create_app(
            ledger_path=ledger_path,
            environment=environment(),
            health_overrides={"api": "degraded"},
        )
    )
    detected = degraded.get("/ops/v1/health")
    recovered = TestClient(create_app(ledger_path=ledger_path, environment=environment()))
    recovery_health = recovered.get("/ops/v1/health")
    smoke = recovered.post("/api/v1/diagnose", json={"text": "A parking meter has stopped working"})
    return {
        "incident_id": "APP-001",
        "truth_class": "synthetic_recovery_experiment",
        "injection": "create_app health override set API component to degraded",
        "detected_status": detected.json()["status"],
        "recovered_status": recovery_health.json()["status"],
        "smoke_http_status": smoke.status_code,
        "passed": detected.json()["status"] == "degraded"
        and recovery_health.json()["status"] == "healthy"
        and smoke.status_code == 200,
    }


def run_app_002() -> dict[str, Any]:
    candidate = {
        "status": "ok",
        "profile": "public_demo",
        "release": "v0.7.2",
        "ledger_integrity_ok": True,
    }
    recovered = {**candidate, "release": f"v{__version__}"}
    detected = evaluate_health_payload(candidate, f"v{__version__}")
    recovery_check = evaluate_health_payload(recovered, f"v{__version__}")
    return {
        "incident_id": "APP-002",
        "truth_class": "synthetic_control_experiment",
        "scope": "local release-verification control; Azure revision rollback requires a hosted workflow drill",
        "injection": "candidate health reports a release that differs from the expected immutable tag",
        "detected_failures": detected,
        "recovery_check": recovery_check,
        "passed": bool(detected) and not recovery_check,
        "hosted_rollback_verified": False,
    }


def run_app_003(root: Path) -> dict[str, Any]:
    ledger_path = root / "app-003.sqlite3"
    backup_path = root / "backups" / "app-003.sqlite3"
    client = TestClient(create_app(ledger_path=ledger_path, environment=environment()))
    created = client.post("/api/v1/submit", json=SUBMISSION)
    ledger = SQLiteEventLedger(ledger_path)
    backup = ledger.backup_to(backup_path)
    with closing(sqlite3.connect(ledger_path)) as connection:
        connection.execute("UPDATE ledger_events SET payload_json = '{}' WHERE sequence = 1")
        connection.commit()
    detected = ledger.verify_integrity()
    blocked = client.post("/api/v1/submit", json=SUBMISSION)
    restored = SQLiteEventLedger.restore_from_backup(backup_path, ledger_path)
    recovered = TestClient(create_app(ledger_path=ledger_path, environment=environment()))
    smoke = recovered.get("/ops/v1/health")
    return {
        "incident_id": "APP-003",
        "truth_class": "synthetic_recovery_experiment",
        "injection": "tampered payload_json in an isolated SQLite copy",
        "initial_write_http_status": created.status_code,
        "backup_integrity_ok": backup.ok,
        "tamper_detected": not detected.ok,
        "first_invalid_sequence": detected.first_invalid_sequence,
        "blocked_write_http_status": blocked.status_code,
        "restored_integrity_ok": restored.ok,
        "recovery_health_status": smoke.json()["status"],
        "passed": created.status_code == 200
        and backup.ok
        and not detected.ok
        and blocked.status_code == 503
        and restored.ok
        and smoke.status_code == 200,
    }


def run_app_004(root: Path) -> dict[str, Any]:
    invalid = TestClient(
        create_app(
            ledger_path=root / "app-004.sqlite3",
            environment=environment(RIVULET_RELEASE="untrusted release/value"),
        )
    )
    detected = invalid.get("/ops/v1/health")
    fixed = TestClient(
        create_app(
            ledger_path=root / "app-004-fixed.sqlite3",
            environment=environment(),
        )
    ).get("/ops/v1/health")
    config = next(item for item in detected.json()["components"] if item["component"] == "configuration")
    return {
        "incident_id": "APP-004",
        "truth_class": "synthetic_recovery_experiment",
        "injection": "invalid release-label environment value",
        "detected_http_status": detected.status_code,
        "configuration_status": config["status"],
        "fixed_status": fixed.json()["status"],
        "passed": detected.status_code == 503
        and config["status"] == "unavailable"
        and fixed.json()["status"] == "healthy",
    }


def run_app_005(root: Path) -> dict[str, Any]:
    client = TestClient(create_app(ledger_path=root / "app-005.sqlite3", environment=environment()))
    disabled = client.post(
        "/ops/v1/providers/deterministic-rules/kill-switch",
        json={
            "disabled": True,
            "operator_id": "operator.synthetic-experiment",
            "reason": "Synthetic provider-outage exercise",
        },
    )
    before = client.get("/ops/v1/ledger/integrity").json()["event_count"]
    fallback = client.post("/api/v1/submit", json=SUBMISSION)
    after = client.get("/ops/v1/ledger/integrity").json()
    enabled = client.post(
        "/ops/v1/providers/deterministic-rules/kill-switch",
        json={
            "disabled": False,
            "operator_id": "operator.synthetic-experiment",
            "reason": "Synthetic provider recovery completed",
        },
    )
    recovered = client.post("/api/v1/submit", json=SUBMISSION)
    return {
        "incident_id": "APP-005",
        "truth_class": "synthetic_recovery_experiment",
        "injection": "provider kill switch enabled",
        "kill_switch_http_status": disabled.status_code,
        "fallback_http_status": fallback.status_code,
        "fallback_reason": fallback.json().get("detail", {}).get("status"),
        "audit_event_added": after["event_count"] == before + 1,
        "ledger_integrity_ok": after["ok"],
        "reenable_http_status": enabled.status_code,
        "recovery_http_status": recovered.status_code,
        "passed": disabled.status_code == 200
        and fallback.status_code == 503
        and after["event_count"] == before + 1
        and after["ok"]
        and enabled.status_code == 200
        and recovered.status_code == 200,
    }


def write_evidence(output_root: Path, incident: dict[str, Any], run_date: str) -> None:
    directory = output_root / incident["incident_id"] / run_date
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "result.json").write_text(
        json.dumps(incident, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (directory / "commands.txt").write_text(
        f".venv/Scripts/python scripts/run_application_support_experiments.py --date {run_date}\n",
        encoding="utf-8",
    )
    (directory / "versions.txt").write_text(
        f"rivulet-localops={__version__}\npython={platform.python_version()}\nsqlite={sqlite3.sqlite_version}\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run isolated Rivulet application-support recovery experiments.")
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--output-root", type=Path, default=ROOT / "evidence")
    args = parser.parse_args()

    with tempfile.TemporaryDirectory(prefix="rivulet-application-support-") as temporary_directory:
        temporary_root = Path(temporary_directory)
        incidents = [
            run_app_001(temporary_root),
            run_app_002(),
            run_app_003(temporary_root),
            run_app_004(temporary_root),
            run_app_005(temporary_root),
        ]

    for incident in incidents:
        write_evidence(args.output_root, incident, args.date)
    summary = {
        "schema_version": "1.0",
        "truth_class": "synthetic_application_support_experiments",
        "executed_at": datetime.now(UTC).isoformat(),
        "run_date": args.date,
        "passed": all(incident["passed"] for incident in incidents),
        "incidents": incidents,
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
