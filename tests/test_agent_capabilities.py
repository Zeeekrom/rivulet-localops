import json
import sqlite3
from contextlib import closing
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from rivulet_localops.main import DEFAULT_CAPABILITY_PATH, create_app
from rivulet_localops.models import ProviderReference


def _asset_file(tmp_path: Path) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    path = tmp_path / "assets.geojson"
    path.write_text(
        json.dumps({
            "type": "FeatureCollection",
            "features": [{
                "type": "Feature",
                "id": 1,
                "geometry": {"type": "Point", "coordinates": [147.319119, -42.886751]},
                "properties": {"OBJECTID": 1, "Description": "25lt Drop Plastic"},
            }],
        }),
        encoding="utf-8",
    )
    return path


def _client(tmp_path: Path, *, capability_path: Path | None = None) -> tuple[TestClient, Path]:
    ledger_path = tmp_path / "ledger.sqlite3"
    app = create_app(
        _asset_file(tmp_path),
        ledger_path=ledger_path,
        capability_path=capability_path,
    )
    return TestClient(app), ledger_path


def _invocation(*, requested_tool_calls: list[dict[str, str]] | None = None) -> dict[str, object]:
    return {
        "request_id": "case-demo-001",
        "correlation_id": "agent-correlation-001",
        "request": {
            "text": "The public bin is overflowing beside the footpath",
            "coordinates": {"latitude": -42.88675, "longitude": 147.31912},
        },
        "requested_tool_calls": requested_tool_calls or [],
    }


def test_case_agent_profile_is_read_only_deny_by_default(tmp_path: Path) -> None:
    client, _ = _client(tmp_path)
    response = client.get("/ops/v1/agents/case-agent/capabilities")

    assert response.status_code == 200
    profile = response.json()
    assert profile["automation_level"] == "L0_shadow_read_only"
    assert profile["credential_mode"] == "none"
    assert profile["default_policy_deny"] is True
    assert {item["tool_name"] for item in profile["allowed_tools"]} == {"case.read", "asset.lookup"}
    assert "shell.exec" in profile["explicitly_denied_tools"]
    assert "connector.write" in profile["explicitly_denied_tools"]
    assert profile["grant_ttl_seconds"] == 300
    assert len(profile["registry_hash"]) == 64
    assert client.get("/ops/v1/agents/unknown-agent/capabilities").status_code == 404


def test_allowed_invocation_is_read_only_hashed_and_audited(tmp_path: Path) -> None:
    client, ledger_path = _client(tmp_path)
    response = client.post("/api/v1/agents/case-agent/invoke", json=_invocation())

    assert response.status_code == 200
    result = response.json()
    audit = result["audit"]
    assert result["diagnosis"]["category"]["code"] == "waste_litter"
    assert audit["status"] == "completed"
    assert audit["gate_result"] == "not_run_read_only"
    assert audit["human_decision"] == "pending"
    assert audit["raw_input_stored"] is False
    assert audit["estimated_provider_cost"] == 0
    assert len(audit["input_hash"]) == 64
    assert len(audit["output_hash"]) == 64
    assert audit["grant_expires_at"] > audit["grant_issued_at"]
    receipts = {item["tool_name"]: item for item in audit["tool_receipts"]}
    assert receipts["case.read"]["decision"] == "allow"
    assert receipts["case.read"]["executed"] is True
    assert receipts["asset.lookup"]["decision"] == "allow"
    assert receipts["asset.lookup"]["executed"] is True

    listed = client.get("/ops/v1/agents/invocations", params={"status": "completed"}).json()
    assert listed["count"] == 1
    assert listed["items"][0]["event_hash"] == audit["event_hash"]

    with closing(sqlite3.connect(ledger_path)) as connection:
        payload = connection.execute(
            "SELECT payload_json FROM ledger_events WHERE event_type = 'agent.invocation.completed'"
        ).fetchone()[0]
    assert "The public bin is overflowing" not in payload
    assert '"raw_input_stored":false' in payload


def test_tool_data_and_cross_case_requests_are_denied_and_audited(tmp_path: Path) -> None:
    client, _ = _client(tmp_path)
    shell = client.post(
        "/api/v1/agents/case-agent/invoke",
        json=_invocation(requested_tool_calls=[{
            "tool_name": "shell.exec",
            "resource": "host:local",
            "data_class": "system_control",
        }]),
    )
    cross_case = client.post(
        "/api/v1/agents/case-agent/invoke",
        json=_invocation(requested_tool_calls=[{
            "tool_name": "case.read",
            "resource": "case:another-case",
            "data_class": "synthetic_case",
        }]),
    )
    restricted_data = client.post(
        "/api/v1/agents/case-agent/invoke",
        json=_invocation(requested_tool_calls=[{
            "tool_name": "asset.lookup",
            "resource": "public_asset:hobart_litter_bins",
            "data_class": "restricted_operational",
        }]),
    )

    assert shell.status_code == 403
    assert shell.json()["detail"]["audit"]["termination_reason"] == "tool_explicitly_denied:shell.exec"
    assert shell.json()["detail"]["audit"]["output_hash"] is None
    assert cross_case.status_code == 403
    assert cross_case.json()["detail"]["audit"]["termination_reason"] == "resource_out_of_scope:case.read"
    assert restricted_data.status_code == 403
    assert restricted_data.json()["detail"]["audit"]["termination_reason"] == (
        "data_class_not_allowlisted:asset.lookup"
    )
    denied = client.get("/ops/v1/agents/invocations", params={"status": "denied"}).json()
    assert denied["count"] == 3
    assert client.get("/ops/v1/ledger/integrity").json()["ok"] is True


def test_tool_call_budget_is_enforced_before_provider_execution(tmp_path: Path) -> None:
    client, _ = _client(tmp_path)
    proposed = [
        {
            "tool_name": "shell.exec",
            "resource": f"host:{index}",
            "data_class": "system_control",
        }
        for index in range(4)
    ]
    response = client.post(
        "/api/v1/agents/case-agent/invoke",
        json=_invocation(requested_tool_calls=proposed),
    )

    assert response.status_code == 403
    audit = response.json()["detail"]["audit"]
    assert audit["status"] == "denied"
    assert audit["output_hash"] is None
    assert "tool_call_budget_exceeded" in audit["termination_reason"]


def test_disabled_identity_and_provider_kill_switch_fail_closed(tmp_path: Path) -> None:
    registry_data = json.loads(DEFAULT_CAPABILITY_PATH.read_text(encoding="utf-8"))
    registry_data["agents"][0]["enabled"] = False
    disabled_path = tmp_path / "disabled-agent.json"
    disabled_path.write_text(json.dumps(registry_data), encoding="utf-8")
    disabled_client, _ = _client(tmp_path / "disabled", capability_path=disabled_path)

    disabled = disabled_client.post("/api/v1/agents/case-agent/invoke", json=_invocation())
    assert disabled.status_code == 403
    assert disabled.json()["detail"]["audit"]["termination_reason"] == "identity_disabled"

    enabled_client, _ = _client(tmp_path / "provider-disabled")
    control = enabled_client.post(
        "/ops/v1/providers/deterministic-rules/kill-switch",
        json={
            "disabled": True,
            "operator_id": "operator.casey",
            "reason": "Exercise the agent provider fail-closed path.",
        },
    )
    blocked = enabled_client.post("/api/v1/agents/case-agent/invoke", json=_invocation())

    assert control.status_code == 200
    assert blocked.status_code == 503
    assert blocked.json()["detail"]["status"] == "manual_fallback"
    assert blocked.json()["detail"]["audit"]["termination_reason"] == "provider_disabled_manual_fallback"


def test_provider_identity_mismatch_fails_before_provider_execution(tmp_path: Path) -> None:
    client, _ = _client(tmp_path)

    class MismatchedProvider:
        reference = ProviderReference(provider="unexpected-provider", version="9.9.9", mode="test")

        def diagnose(self, _request: object) -> object:
            raise AssertionError("a mismatched provider must not execute")

    client.app.state.case_agent.provider = MismatchedProvider()
    response = client.post("/api/v1/agents/case-agent/invoke", json=_invocation())

    assert response.status_code == 503
    audit = response.json()["detail"]["audit"]
    assert audit["status"] == "failed"
    assert audit["termination_reason"] == "provider_identity_mismatch"
    assert audit["tool_receipts"] == []
    assert audit["output_hash"] is None


def test_expired_invocation_grant_is_denied_before_provider_execution(tmp_path: Path) -> None:
    client, _ = _client(tmp_path)
    started = datetime(2026, 9, 12, 4, 0, tzinfo=UTC)
    times = iter((started, started + timedelta(seconds=301)))
    client.app.state.case_agent._clock = lambda: next(times)

    response = client.post("/api/v1/agents/case-agent/invoke", json=_invocation())

    assert response.status_code == 403
    audit = response.json()["detail"]["audit"]
    assert audit["termination_reason"] == "grant_expired"
    assert audit["output_hash"] is None
    assert all(receipt["executed"] is False for receipt in audit["tool_receipts"])
