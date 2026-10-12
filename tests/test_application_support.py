import hashlib
import json
import sqlite3
from contextlib import closing
from pathlib import Path

from fastapi.testclient import TestClient

from rivulet_localops.ledger import SQLiteEventLedger
from rivulet_localops.main import create_app


def _client(tmp_path: Path, **kwargs) -> TestClient:
    environment = {
        "RIVULET_RELEASE": "v0.8.0",
        "RIVULET_ENVIRONMENT": "test",
        "RIVULET_DEPLOYMENT_ID": "deploy-test-001",
        "RIVULET_REVISION": "revision-test-001",
        "RIVULET_DEPLOYED_AT": "2026-10-12T00:00:00Z",
        "RIVULET_DEPLOYMENT_SOURCE": "pytest",
        "RIVULET_VERIFIED_INCIDENTS": "APP-001,APP-003,APP-005",
    }
    return TestClient(
        create_app(
            ledger_path=tmp_path / "ledger.sqlite3",
            environment=environment,
            **kwargs,
        )
    )


def _submission() -> dict:
    return {
        "request": {
            "text": "Overflowing bin reported by resident@example.test with secret=do-not-log",
            "coordinates": {"latitude": -42.8867512572958, "longitude": 147.319119003722},
        },
        "proposed_action": "create_draft_work_order",
        "accountable_owner_id": "owner.test",
        "correlation_id": "cor-body-12345",
    }


def test_structured_log_has_required_fields_without_request_body_or_headers(tmp_path: Path) -> None:
    client = _client(tmp_path)

    response = client.post(
        "/api/v1/submit",
        json=_submission(),
        headers={
            "X-Correlation-ID": "cor-header-12345",
            "X-Request-ID": "req-header-12345",
            "Authorization": "Bearer never-store-this-token",
        },
    )
    logs = client.get("/ops/v1/operations/logs").json()
    decision_log = next(record for record in logs if record["event_name"] == "decision_recorded")
    serialised = json.dumps(logs)

    assert response.status_code == 200
    assert response.headers["x-correlation-id"] == "cor-header-12345"
    assert response.headers["x-request-id"] == "req-header-12345"
    assert decision_log["correlation_id"] == "cor-body-12345"
    assert decision_log["request_id"] == "req-header-12345"
    assert decision_log["policy_version"] == "0.1.0"
    assert decision_log["provider"] == "deterministic-rules"
    assert decision_log["provider_version"] == "0.1.0"
    assert decision_log["gate_result"] in {"pass", "reject", "escalate"}
    assert decision_log["ledger_event_id"] == response.json()["ledger_event_id"]
    assert decision_log["elapsed_ms"] >= 0
    assert "resident@example.test" not in serialised
    assert "do-not-log" not in serialised
    assert "never-store-this-token" not in serialised


def test_internal_health_reports_components_and_provider_degradation(tmp_path: Path) -> None:
    client = _client(tmp_path)
    healthy = client.get("/ops/v1/health")
    control = client.post(
        "/ops/v1/providers/deterministic-rules/kill-switch",
        json={"disabled": True, "operator_id": "operator.test", "reason": "Synthetic APP-005 exercise"},
    )
    degraded = client.get("/ops/v1/health")

    assert healthy.status_code == 200
    assert healthy.json()["status"] == "healthy"
    assert {item["component"] for item in healthy.json()["components"]} == {
        "api",
        "database_ledger",
        "policy_pack",
        "provider",
        "configuration",
        "dependencies",
        "build_version",
    }
    assert control.status_code == 200
    assert degraded.status_code == 200
    assert degraded.json()["status"] == "degraded"
    provider = next(item for item in degraded.json()["components"] if item["component"] == "provider")
    assert provider["details"]["manual_fallback"] is True


def test_unavailable_health_returns_503_and_ledger_writes_fail_closed(tmp_path: Path) -> None:
    client = _client(tmp_path)
    assert client.post("/api/v1/submit", json=_submission()).status_code == 200
    with closing(sqlite3.connect(tmp_path / "ledger.sqlite3")) as connection:
        connection.execute("UPDATE ledger_events SET payload_json = '{}' WHERE sequence = 1")
        connection.commit()

    health = client.get("/ops/v1/health")
    blocked = client.post("/api/v1/submit", json=_submission())

    assert health.status_code == 503
    assert health.json()["status"] == "unavailable"
    ledger_component = next(
        item for item in health.json()["components"] if item["component"] == "database_ledger"
    )
    assert ledger_component["details"]["integrity_ok"] is False
    assert blocked.status_code == 503
    assert blocked.json()["detail"]["reason"] == "ledger_integrity_failure"


def test_support_bundle_is_allowlisted_and_checksum_verifiable(tmp_path: Path) -> None:
    client = _client(tmp_path)
    client.post("/api/v1/submit", json=_submission())

    response = client.get("/ops/v1/support/bundle")
    bundle = response.json()
    checksum = bundle.pop("checksum")
    canonical = json.dumps(bundle, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    serialised = json.dumps(bundle)

    assert response.status_code == 200
    assert checksum == hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    assert bundle["application_version"] == "0.8.0"
    assert bundle["recent_deployment"]["revision"] == "revision-test-001"
    assert bundle["configuration_summary"]["secrets_in_support_bundle"] is False
    assert bundle["ledger_integrity"]["ok"] is True
    assert "resident@example.test" not in serialised
    assert "do-not-log" not in serialised
    assert str(tmp_path) not in serialised


def test_internal_operations_page_exposes_support_entry_points(tmp_path: Path) -> None:
    response = _client(tmp_path).get("/ops/support")

    assert response.status_code == 200
    assert "Operations &amp; Support" in response.text
    assert "/ops/v1/support/bundle" in response.text
    assert "/ops/v1/runbooks" in response.text


def test_ledger_backup_restore_recovers_a_tampered_test_copy(tmp_path: Path) -> None:
    ledger_path = tmp_path / "ledger.sqlite3"
    backup_path = tmp_path / "backups" / "ledger.sqlite3"
    client = _client(tmp_path)
    assert client.post("/api/v1/submit", json=_submission()).status_code == 200
    ledger = SQLiteEventLedger(ledger_path)
    original = ledger.backup_to(backup_path)

    with closing(sqlite3.connect(ledger_path)) as connection:
        connection.execute("UPDATE ledger_events SET payload_json = '{}' WHERE sequence = 1")
        connection.commit()
    assert ledger.verify_integrity().ok is False

    restored = SQLiteEventLedger.restore_from_backup(backup_path, ledger_path)

    assert original.ok is True
    assert restored.ok is True
    assert restored.event_count == original.event_count


def test_health_override_supports_safe_app_001_exercise(tmp_path: Path) -> None:
    client = _client(tmp_path, health_overrides={"api": "degraded"})

    health = client.get("/ops/v1/health")

    assert health.status_code == 200
    assert health.json()["status"] == "degraded"
    api = next(item for item in health.json()["components"] if item["component"] == "api")
    assert api["summary"] == "Synthetic health override is active."
