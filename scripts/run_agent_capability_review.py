from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
from contextlib import closing
from pathlib import Path

from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from rivulet_localops.main import create_app  # noqa: E402
from rivulet_localops.models import ProviderReference  # noqa: E402


def invocation(tool_calls: list[dict[str, str]] | None = None) -> dict[str, object]:
    return {
        "request_id": "review-case-001",
        "correlation_id": "review-correlation-001",
        "request": {
            "text": "The public bin is overflowing beside the footpath",
            "coordinates": {"latitude": -42.88675, "longitude": 147.31912},
        },
        "requested_tool_calls": tool_calls or [],
    }


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="rivulet-f18-") as temporary_directory:
        ledger_path = Path(temporary_directory) / "capability-review.sqlite3"
        client = TestClient(create_app(ledger_path=ledger_path))

        profile_response = client.get("/ops/v1/agents/case-agent/capabilities")
        allowed_response = client.post("/api/v1/agents/case-agent/invoke", json=invocation())
        shell_response = client.post(
            "/api/v1/agents/case-agent/invoke",
            json=invocation([{
                "tool_name": "shell.exec",
                "resource": "host:local",
                "data_class": "system_control",
            }]),
        )
        cross_case_response = client.post(
            "/api/v1/agents/case-agent/invoke",
            json=invocation([{
                "tool_name": "case.read",
                "resource": "case:another-case",
                "data_class": "synthetic_case",
            }]),
        )
        restricted_data_response = client.post(
            "/api/v1/agents/case-agent/invoke",
            json=invocation([{
                "tool_name": "asset.lookup",
                "resource": "public_asset:hobart_litter_bins",
                "data_class": "restricted_operational",
            }]),
        )
        budget_response = client.post(
            "/api/v1/agents/case-agent/invoke",
            json=invocation([
                {
                    "tool_name": "shell.exec",
                    "resource": f"host:{index}",
                    "data_class": "system_control",
                }
                for index in range(4)
            ]),
        )
        configured_provider = client.app.state.case_agent.provider

        class MismatchedProvider:
            reference = ProviderReference(provider="unexpected-provider", version="9.9.9", mode="review")

            def diagnose(self, _request: object) -> object:
                raise AssertionError("a mismatched provider must not execute")

        client.app.state.case_agent.provider = MismatchedProvider()
        provider_mismatch_response = client.post(
            "/api/v1/agents/case-agent/invoke",
            json=invocation(),
        )
        client.app.state.case_agent.provider = configured_provider
        control_response = client.post(
            "/ops/v1/providers/deterministic-rules/kill-switch",
            json={
                "disabled": True,
                "operator_id": "review.operator",
                "reason": "F18 provider-disabled capability review.",
            },
        )
        provider_disabled_response = client.post(
            "/api/v1/agents/case-agent/invoke",
            json=invocation(),
        )

        audits_response = client.get("/ops/v1/agents/invocations")
        integrity_response = client.get("/ops/v1/ledger/integrity")
        profile = profile_response.json()
        allowed = allowed_response.json()
        shell = shell_response.json()["detail"]["audit"]
        cross_case = cross_case_response.json()["detail"]["audit"]
        restricted_data = restricted_data_response.json()["detail"]["audit"]
        budget = budget_response.json()["detail"]["audit"]
        provider_mismatch = provider_mismatch_response.json()["detail"]["audit"]
        provider_disabled = provider_disabled_response.json()["detail"]["audit"]
        audits = audits_response.json()

        with closing(sqlite3.connect(ledger_path)) as connection:
            stored_agent_payloads = "\n".join(
                row[0]
                for row in connection.execute(
                    "SELECT payload_json FROM ledger_events WHERE event_type LIKE 'agent.invocation.%'"
                ).fetchall()
            )

        checks = {
            "profile_is_server_owned_read_only": (
                profile_response.status_code == 200
                and profile["automation_level"] == "L0_shadow_read_only"
                and profile["credential_mode"] == "none"
                and profile["default_policy_deny"] is True
            ),
            "allowed_tools_are_minimal": (
                {item["tool_name"] for item in profile["allowed_tools"]} == {"case.read", "asset.lookup"}
            ),
            "allowed_invocation_completed": (
                allowed_response.status_code == 200
                and allowed["audit"]["status"] == "completed"
                and allowed["audit"]["gate_result"] == "not_run_read_only"
                and allowed["audit"]["human_decision"] == "pending"
            ),
            "shell_denied_and_audited": (
                shell_response.status_code == 403
                and shell["termination_reason"] == "tool_explicitly_denied:shell.exec"
                and shell["output_hash"] is None
            ),
            "cross_case_denied_and_audited": (
                cross_case_response.status_code == 403
                and cross_case["termination_reason"] == "resource_out_of_scope:case.read"
            ),
            "restricted_data_class_denied_and_audited": (
                restricted_data_response.status_code == 403
                and restricted_data["termination_reason"] == "data_class_not_allowlisted:asset.lookup"
            ),
            "tool_budget_denied_before_execution": (
                budget_response.status_code == 403
                and "tool_call_budget_exceeded" in budget["termination_reason"]
                and budget["output_hash"] is None
            ),
            "provider_identity_mismatch_failed_before_execution": (
                provider_mismatch_response.status_code == 503
                and provider_mismatch["status"] == "failed"
                and provider_mismatch["termination_reason"] == "provider_identity_mismatch"
                and provider_mismatch["tool_receipts"] == []
                and provider_mismatch["output_hash"] is None
            ),
            "provider_kill_switch_denied_and_audited": (
                control_response.status_code == 200
                and provider_disabled_response.status_code == 503
                and provider_disabled["termination_reason"] == "provider_disabled_manual_fallback"
            ),
            "raw_request_text_not_stored_in_agent_audit": (
                "The public bin is overflowing" not in stored_agent_payloads
            ),
            "seven_agent_invocations_queryable": audits_response.status_code == 200 and audits["count"] == 7,
            "ledger_integrity_preserved": integrity_response.json()["ok"] is True,
        }
        status = "pass" if all(checks.values()) else "fail"
        result = {
            "experiment_id": "F18",
            "experiment_date_local": "2026-09-12",
            "status": status,
            "scope": "Sprint 3 read-only case-agent identity, capability, data and tool enforcement",
            "checks": checks,
            "summary": {
                "checks_total": len(checks),
                "checks_passed": sum(checks.values()),
                "agent_invocations": audits["count"],
                "completed": sum(item["status"] == "completed" for item in audits["items"]),
                "denied": sum(item["status"] == "denied" for item in audits["items"]),
                "failed": sum(item["status"] == "failed" for item in audits["items"]),
                "ledger_event_count": integrity_response.json()["event_count"],
            },
            "claim_boundary": (
                "This is a local L0 control harness using the deterministic-rules baseline and synthetic requests. "
                "It does not use a generative model, authenticate callers, prove object-level authorization against "
                "a real case store, execute connectors, or establish production security."
            ),
        }
        print(json.dumps(result, indent=2))
        return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
