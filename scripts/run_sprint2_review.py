"""Run the Sprint 2 review story against disposable local ledgers."""

import json
import sqlite3
import sys
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from rivulet_localops.main import create_app  # noqa: E402


VALID_SUBMISSION = {
    "request": {
        "text": "The public bin is overflowing beside the footpath on Elizabeth Street",
        "coordinates": {"latitude": -42.88675, "longitude": 147.31912},
    },
    "proposed_action": "create_draft_work_order",
    "accountable_owner_id": "owner.demo",
    "correlation_id": "sprint2-review-main",
}


def _client(ledger_path: Path) -> TestClient:
    return TestClient(create_app(ledger_path=ledger_path))


def _review_main_path(root: Path) -> dict[str, object]:
    ledger_path = root / "review.sqlite3"
    client = _client(ledger_path)
    try:
        submitted = client.post("/api/v1/submit", json=VALID_SUBMISSION)
        submitted.raise_for_status()
        original = submitted.json()

        fetched = client.get(f"/api/v1/decisions/{original['decision_id']}")
        fetched.raise_for_status()

        reviewed = client.post(
            f"/api/v1/decisions/{original['decision_id']}/reviews",
            json={
                "reviewer_id": "reviewer.demo",
                "action": "override",
                "reason": "Demonstrate an independent queue-routing correction.",
                "replacement_action": "route_to_cleanup_team",
            },
        )
        reviewed.raise_for_status()

        replayed = client.post(
            f"/api/v1/decisions/{original['decision_id']}/replay",
            json={"operator_id": "auditor.demo"},
        )
        replayed.raise_for_status()

        disabled = client.post(
            "/ops/v1/providers/deterministic-rules/kill-switch",
            json={
                "disabled": True,
                "operator_id": "operator.demo",
                "reason": "Sprint 2 manual-fallback review drill.",
            },
        )
        disabled.raise_for_status()
        fallback = client.post(
            "/api/v1/submit",
            json={**VALID_SUBMISSION, "correlation_id": "sprint2-review-fallback"},
        )
        enabled = client.post(
            "/ops/v1/providers/deterministic-rules/kill-switch",
            json={
                "disabled": False,
                "operator_id": "operator.demo",
                "reason": "Review drill completed and provider re-enabled.",
            },
        )
        enabled.raise_for_status()
        integrity = client.get("/ops/v1/ledger/integrity")
        integrity.raise_for_status()

        reviewed_record = reviewed.json()
        replay = replayed.json()
        fallback_detail = fallback.json()["detail"]
        checks = {
            "decision_queryable": fetched.json()["event_hash"] == original["event_hash"],
            "review_is_append_only": (
                reviewed_record["event_hash"] == original["event_hash"]
                and reviewed_record["gate_decision"] == original["gate_decision"]
            ),
            "independent_override_recorded": reviewed_record["current_review"]["action"] == "override",
            "replay_reproducible": replay["reproducible"] is True,
            "kill_switch_disabled_provider": disabled.json()["disabled"] is True,
            "manual_fallback_recorded": fallback.status_code == 503 and fallback_detail["status"] == "manual_fallback",
            "provider_reenabled": enabled.json()["disabled"] is False,
            "main_ledger_integrity": integrity.json()["ok"] is True,
        }
        if not all(checks.values()):
            raise RuntimeError(f"Sprint 2 main-path review failed: {checks}")

        return {
            "checks": checks,
            "event_count": integrity.json()["event_count"],
            "gate_status": original["gate_decision"]["status"],
            "review_action": reviewed_record["current_review"]["action"],
            "fallback_http_status": fallback.status_code,
        }
    finally:
        client.close()


def _review_tamper_path(root: Path) -> dict[str, object]:
    ledger_path = root / "tamper.sqlite3"
    client = _client(ledger_path)
    try:
        response = client.post(
            "/api/v1/submit",
            json={**VALID_SUBMISSION, "correlation_id": "sprint2-review-tamper"},
        )
        response.raise_for_status()

        with closing(sqlite3.connect(ledger_path)) as connection:
            connection.execute("UPDATE ledger_events SET payload_json = '{}' WHERE sequence = 1")
            connection.commit()

        integrity = client.get("/ops/v1/ledger/integrity")
        blocked = client.post(
            "/api/v1/submit",
            json={**VALID_SUBMISSION, "correlation_id": "sprint2-review-blocked"},
        )
        checks = {
            "tamper_detected": integrity.json()["ok"] is False,
            "first_invalid_sequence_identified": integrity.json()["first_invalid_sequence"] == 1,
            "new_write_failed_closed": (
                blocked.status_code == 503
                and blocked.json()["detail"]["reason"] == "ledger_integrity_failure"
            ),
        }
        if not all(checks.values()):
            raise RuntimeError(f"Sprint 2 tamper-path review failed: {checks}")
        return {"checks": checks, "blocked_http_status": blocked.status_code}
    finally:
        client.close()


def main() -> None:
    with TemporaryDirectory(prefix="rivulet-sprint2-review-") as directory:
        root = Path(directory)
        result = {
            "review": "Sprint 2 accountable decision ledger",
            "status": "pass",
            "main_path": _review_main_path(root),
            "tamper_path": _review_tamper_path(root),
            "claim_boundary": {
                "identity": "asserted demo identifiers; not authenticated RBAC",
                "ledger": "local tamper-evident SQLite; not WORM or externally signed",
                "action": "draft-only; no real council connector",
                "data": "synthetic request records only",
            },
        }
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
