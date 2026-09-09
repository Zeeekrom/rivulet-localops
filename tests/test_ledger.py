import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

from rivulet_localops.main import create_app


def _asset_file(tmp_path: Path) -> Path:
    path = tmp_path / "assets.geojson"
    path.write_text(
        """{
          "type": "FeatureCollection",
          "features": [{
            "type": "Feature",
            "id": 1,
            "geometry": {"type": "Point", "coordinates": [147.319119, -42.886751]},
            "properties": {"OBJECTID": 1, "Description": "25lt Drop Plastic"}
          }]
        }""",
        encoding="utf-8",
    )
    return path


def _client(tmp_path: Path) -> tuple[TestClient, Path]:
    ledger_path = tmp_path / "ledger.sqlite3"
    app = create_app(_asset_file(tmp_path), ledger_path=ledger_path)
    return TestClient(app), ledger_path


def _submit(client: TestClient, *, with_coordinates: bool = True):
    request: dict[str, object] = {"text": "The public bin is overflowing beside the footpath"}
    if with_coordinates:
        request["coordinates"] = {"latitude": -42.88675, "longitude": 147.31912}
    return client.post("/api/v1/submit", json={
        "request": request,
        "proposed_action": "create_draft_work_order",
        "accountable_owner_id": "owner.alex",
        "correlation_id": "demo-correlation-001",
    })


def test_submission_creates_queryable_hash_chained_record(tmp_path: Path) -> None:
    client, _ = _client(tmp_path)
    response = _submit(client)

    assert response.status_code == 200
    record = response.json()
    assert record["accountable_owner_id"] == "owner.alex"
    assert record["gate_decision"]["status"] == "pass"
    assert len(record["request_hash"]) == 64
    assert len(record["event_hash"]) == 64
    assert record["previous_event_hash"] is None
    assert record["current_review"] is None

    fetched = client.get(f"/api/v1/decisions/{record['decision_id']}")
    queue = client.get("/api/v1/decisions", params={"review_state": "pending"})
    integrity = client.get("/ops/v1/ledger/integrity")
    assert fetched.json()["event_hash"] == record["event_hash"]
    assert queue.json()["count"] == 1
    assert integrity.json() == {
        "ok": True,
        "event_count": 1,
        "head_hash": record["event_hash"],
        "first_invalid_sequence": None,
        "message": "Ledger hash chain is valid.",
    }


def test_review_is_appended_without_overwriting_original_decision(tmp_path: Path) -> None:
    client, _ = _client(tmp_path)
    original = _submit(client).json()
    response = client.post(
        f"/api/v1/decisions/{original['decision_id']}/reviews",
        json={
            "reviewer_id": "reviewer.morgan",
            "action": "override",
            "reason": "Route this demonstration case to a different internal queue.",
            "replacement_action": "route_to_cleanup_team",
        },
    )

    assert response.status_code == 200
    reviewed = response.json()
    assert reviewed["event_hash"] == original["event_hash"]
    assert reviewed["gate_decision"] == original["gate_decision"]
    assert reviewed["current_review"]["action"] == "override"
    assert reviewed["current_review"]["reviewer_id"] == "reviewer.morgan"
    assert reviewed["current_review"]["previous_event_hash"] == original["event_hash"]
    assert len(reviewed["review_history"]) == 1


def test_rejected_gate_decision_cannot_be_accepted(tmp_path: Path) -> None:
    client, _ = _client(tmp_path)
    rejected = _submit(client, with_coordinates=False).json()
    response = client.post(
        f"/api/v1/decisions/{rejected['decision_id']}/reviews",
        json={
            "reviewer_id": "reviewer.morgan",
            "action": "accept",
            "reason": "Accept despite missing required evidence.",
        },
    )

    assert rejected["gate_decision"]["status"] == "reject"
    assert response.status_code == 409
    assert client.get("/ops/v1/ledger/integrity").json()["event_count"] == 1


def test_accountable_owner_cannot_self_review(tmp_path: Path) -> None:
    client, _ = _client(tmp_path)
    decision = _submit(client).json()
    response = client.post(
        f"/api/v1/decisions/{decision['decision_id']}/reviews",
        json={
            "reviewer_id": "owner.alex",
            "action": "accept",
            "reason": "Attempt to approve my own automated decision.",
        },
    )

    assert response.status_code == 409
    assert "cannot independently review" in response.json()["detail"]
    assert client.get("/ops/v1/ledger/integrity").json()["event_count"] == 1


def test_replay_records_reproducible_decision_evidence(tmp_path: Path) -> None:
    client, _ = _client(tmp_path)
    decision = _submit(client).json()
    response = client.post(
        f"/api/v1/decisions/{decision['decision_id']}/replay",
        json={"operator_id": "auditor.riley"},
    )

    assert response.status_code == 200
    result = response.json()
    assert result["reproducible"] is True
    assert all(result[field] is True for field in (
        "policy_version_match",
        "policy_hash_match",
        "provider_version_match",
        "gate_status_match",
        "category_match",
        "priority_match",
        "rule_outcomes_match",
    ))
    assert client.get("/ops/v1/ledger/integrity").json()["event_count"] == 2


def test_kill_switch_forces_manual_fallback_and_persists(tmp_path: Path) -> None:
    client, ledger_path = _client(tmp_path)
    disabled = client.post(
        "/ops/v1/providers/deterministic-rules/kill-switch",
        json={
            "disabled": True,
            "operator_id": "operator.casey",
            "reason": "Provider paused for a portfolio incident drill.",
        },
    )
    fallback = _submit(client)
    blocked_diagnosis = client.post("/api/v1/diagnose", json={"text": "The bin is overflowing"})

    assert disabled.status_code == 200
    assert disabled.json()["disabled"] is True
    assert fallback.status_code == 503
    assert fallback.json()["detail"]["status"] == "manual_fallback"
    assert fallback.json()["detail"]["ledger_event_id"]
    assert blocked_diagnosis.status_code == 503

    disabled_restart = TestClient(create_app(_asset_file(tmp_path), ledger_path=ledger_path))
    assert disabled_restart.get("/health").json()["provider_disabled"] is True

    enabled = disabled_restart.post(
        "/ops/v1/providers/deterministic-rules/kill-switch",
        json={
            "disabled": False,
            "operator_id": "operator.casey",
            "reason": "Incident drill complete and manual verification passed.",
        },
    )
    assert enabled.json()["disabled"] is False
    assert _submit(client).status_code == 200

    restarted = TestClient(create_app(_asset_file(tmp_path), ledger_path=ledger_path))
    assert restarted.get("/health").json()["provider_disabled"] is False
    assert restarted.get("/health").json()["ledger_event_count"] == 4


def test_tamper_is_detected_and_new_writes_fail_closed(tmp_path: Path) -> None:
    client, ledger_path = _client(tmp_path)
    _submit(client)
    with sqlite3.connect(ledger_path) as connection:
        connection.execute("UPDATE ledger_events SET payload_json = '{}' WHERE sequence = 1")

    integrity = client.get("/ops/v1/ledger/integrity")
    blocked = _submit(client)
    blocked_diagnosis = client.post("/api/v1/diagnose", json={"text": "The bin is overflowing"})
    health = client.get("/health")

    assert integrity.json()["ok"] is False
    assert integrity.json()["first_invalid_sequence"] == 1
    assert blocked.status_code == 503
    assert blocked.json()["detail"]["reason"] == "ledger_integrity_failure"
    assert blocked_diagnosis.status_code == 503
    assert health.json()["status"] == "degraded"
    assert health.json()["ledger_integrity_ok"] is False
    assert health.json()["provider_disabled"] is True
