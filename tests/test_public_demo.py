from pathlib import Path

from fastapi.testclient import TestClient

from rivulet_localops.public_demo import create_public_demo_app


def _client(tmp_path: Path, *, rate_limit: int = 30) -> TestClient:
    app = create_public_demo_app(
        ledger_path=tmp_path / "demo.sqlite3",
        static_path=None,
        rate_limit=rate_limit,
    )
    return TestClient(app)


def test_bootstrap_keeps_public_and_synthetic_truth_classes_separate(tmp_path: Path) -> None:
    response = _client(tmp_path).get("/demo/v1/bootstrap")

    assert response.status_code == 200
    body = response.json()
    assert body["profile"] == "public_demo"
    assert body["release"] == "v0.7.1"
    assert {source["truth_class"] for source in body["sources"]} == {
        "real_public_reference",
        "synthetic_operational",
    }
    assert "cannot support claims" in body["claim_boundary"]
    assert body["capability"]["credential_mode"] == "none"
    assert body["capability"]["default_policy_deny"] is True


def test_predefined_scenarios_cover_gate_and_capability_outcomes(tmp_path: Path) -> None:
    client = _client(tmp_path)
    expected = {
        "bin-near-asset": "pass",
        "bin-missing-location": "reject",
        "safety-escalation": "escalate",
        "blocked-shell": "deny",
        "cross-case-read": "deny",
    }

    for scenario_id, outcome in expected.items():
        response = client.post(f"/demo/v1/scenarios/{scenario_id}/run")
        assert response.status_code == 200
        body = response.json()
        assert body["observed_outcome"] == outcome
        assert body["outcome_matches_fixture"] is True
        assert body["ledger_integrity_ok"] is True

    shell_receipt = client.post("/demo/v1/scenarios/blocked-shell/run").json()["audit"]["tool_receipts"][-1]
    assert shell_receipt == {
        "tool_name": "shell.exec",
        "resource": "host:public-demo",
        "data_class": "system_control",
        "decision": "deny",
        "executed": False,
        "reason": "tool_explicitly_denied",
    }


def test_public_profile_does_not_load_internal_api_or_documentation(tmp_path: Path) -> None:
    client = _client(tmp_path)

    for path in (
        "/docs",
        "/openapi.json",
        "/health",
        "/api/v1/diagnose",
        "/api/v1/submit",
        "/api/v1/agents/case-agent/invoke",
        "/api/v1/decisions",
        "/ops/v1/ledger/integrity",
        "/ops/v1/providers/deterministic-rules/kill-switch",
    ):
        assert client.get(path).status_code == 404


def test_public_profile_sets_browser_security_headers_and_limits_body(tmp_path: Path) -> None:
    client = _client(tmp_path)
    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]

    oversized = client.post(
        "/demo/v1/scenarios/bin-near-asset/run",
        content="x" * 1025,
        headers={"content-type": "text/plain"},
    )
    assert oversized.status_code == 413
    assert oversized.headers["x-content-type-options"] == "nosniff"
    assert oversized.headers["x-frame-options"] == "DENY"


def test_public_profile_rate_limits_scenario_execution(tmp_path: Path) -> None:
    client = _client(tmp_path, rate_limit=1)

    assert client.post("/demo/v1/scenarios/bin-near-asset/run").status_code == 200
    assert client.post("/demo/v1/scenarios/bin-near-asset/run").status_code == 429
