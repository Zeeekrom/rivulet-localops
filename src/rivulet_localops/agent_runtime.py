import hashlib
import json
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import uuid4

from .capabilities import CapabilityRegistry
from .ledger import SQLiteEventLedger
from .models import (
    AgentCapabilityProfile,
    AgentInvocationAuditRecord,
    AgentInvocationRequest,
    AgentInvocationResponse,
    AgentInvocationTrace,
    AgentToolCallRequest,
    AgentToolReceipt,
    DiagnoseResponse,
)
from .providers.base import TriageProvider


def _content_hash(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class AgentInvocationDenied(RuntimeError):
    def __init__(self, audit: AgentInvocationAuditRecord, status_code: int = 403):
        super().__init__(audit.termination_reason)
        self.audit = audit
        self.status_code = status_code


class CaseAgentRunner:
    """Deny-by-default L0 agent harness using the current deterministic provider."""

    agent_id = "case-agent"

    def __init__(
        self,
        registry: CapabilityRegistry,
        provider: TriageProvider,
        ledger: SQLiteEventLedger,
        policy_pack_version: str,
        id_factory: Callable[[], str] | None = None,
        clock: Callable[[], datetime] | None = None,
        monotonic: Callable[[], float] | None = None,
    ):
        self.registry = registry
        self.provider = provider
        self.ledger = ledger
        self.policy_pack_version = policy_pack_version
        self._id_factory = id_factory or (lambda: str(uuid4()))
        self._clock = clock or (lambda: datetime.now(UTC))
        self._monotonic = monotonic or time.perf_counter

    @property
    def profile(self) -> AgentCapabilityProfile:
        profile = self.registry.profile(self.agent_id)
        if profile is None:
            raise RuntimeError("case-agent is missing from the capability registry")
        return profile

    @staticmethod
    def _required_calls(invocation: AgentInvocationRequest) -> list[AgentToolCallRequest]:
        calls = [
            AgentToolCallRequest(
                tool_name="case.read",
                resource=f"case:{invocation.request_id}",
                data_class="synthetic_case",
            )
        ]
        if invocation.request.coordinates is not None:
            calls.append(
                AgentToolCallRequest(
                    tool_name="asset.lookup",
                    resource="public_asset:hobart_litter_bins",
                    data_class="real_public_reference",
                )
            )
        return calls

    def _authorize_tool(self, call: AgentToolCallRequest, request_id: str) -> AgentToolReceipt:
        if call.tool_name in self.profile.explicitly_denied_tools:
            return AgentToolReceipt(
                **call.model_dump(), decision="deny", executed=False, reason="tool_explicitly_denied"
            )
        permission = next((item for item in self.profile.allowed_tools if item.tool_name == call.tool_name), None)
        if permission is None:
            return AgentToolReceipt(
                **call.model_dump(), decision="deny", executed=False, reason="tool_not_allowlisted"
            )
        if call.data_class not in permission.allowed_data_classes:
            return AgentToolReceipt(
                **call.model_dump(), decision="deny", executed=False, reason="data_class_not_allowlisted"
            )
        allowed_resources = {template.format(request_id=request_id) for template in permission.resource_templates}
        if call.resource not in allowed_resources:
            return AgentToolReceipt(
                **call.model_dump(), decision="deny", executed=False, reason="resource_out_of_scope"
            )
        return AgentToolReceipt(**call.model_dump(), decision="allow", executed=False, reason="capability_allowlist")

    def _record(
        self,
        *,
        invocation: AgentInvocationRequest,
        invocation_id: str,
        grant_id: str,
        issued_at: datetime,
        expires_at: datetime,
        input_hash: str,
        receipts: list[AgentToolReceipt],
        status: Literal["completed", "denied", "failed"],
        termination_reason: str,
        output: DiagnoseResponse | None,
        started: float,
    ) -> AgentInvocationAuditRecord:
        profile = self.profile
        output_hash = _content_hash(output.model_dump(mode="json")) if output is not None else None
        trace = AgentInvocationTrace(
            invocation_id=invocation_id,
            agent_id=profile.agent_id,
            agent_version=profile.agent_version,
            owner_id=profile.owner_id,
            purpose=invocation.purpose,
            request_id=invocation.request_id,
            correlation_id=invocation.correlation_id,
            data_truth_class=invocation.data_truth_class,
            automation_level=profile.automation_level,
            registry_id=profile.registry_id,
            registry_version=profile.registry_version,
            registry_hash=profile.registry_hash,
            grant_id=grant_id,
            grant_issued_at=issued_at,
            grant_expires_at=expires_at,
            policy_pack_version=self.policy_pack_version,
            provider=profile.provider,
            credential_mode=profile.credential_mode,
            allowed_tools=[item.tool_name for item in profile.allowed_tools],
            allowed_data_classes=profile.allowed_data_classes,
            tool_receipts=receipts,
            input_hash=input_hash,
            output_hash=output_hash,
            status=status,
            latency_ms=max(0.0, round((self._monotonic() - started) * 1000, 3)),
            termination_reason=termination_reason,
        )
        return self.ledger.record_agent_invocation(trace)

    def invoke(self, invocation: AgentInvocationRequest, *, provider_disabled: bool = False) -> AgentInvocationResponse:
        started = self._monotonic()
        issued_at = self._clock()
        profile = self.profile
        expires_at = issued_at + timedelta(seconds=profile.grant_ttl_seconds)
        invocation_id = self._id_factory()
        grant_id = self._id_factory()
        input_hash = _content_hash(invocation.model_dump(mode="json"))

        if not profile.enabled:
            audit = self._record(
                invocation=invocation,
                invocation_id=invocation_id,
                grant_id=grant_id,
                issued_at=issued_at,
                expires_at=expires_at,
                input_hash=input_hash,
                receipts=[],
                status="denied",
                termination_reason="identity_disabled",
                output=None,
                started=started,
            )
            raise AgentInvocationDenied(audit)

        if provider_disabled:
            audit = self._record(
                invocation=invocation,
                invocation_id=invocation_id,
                grant_id=grant_id,
                issued_at=issued_at,
                expires_at=expires_at,
                input_hash=input_hash,
                receipts=[],
                status="denied",
                termination_reason="provider_disabled_manual_fallback",
                output=None,
                started=started,
            )
            raise AgentInvocationDenied(audit, status_code=503)

        if self.provider.reference != profile.provider:
            audit = self._record(
                invocation=invocation,
                invocation_id=invocation_id,
                grant_id=grant_id,
                issued_at=issued_at,
                expires_at=expires_at,
                input_hash=input_hash,
                receipts=[],
                status="failed",
                termination_reason="provider_identity_mismatch",
                output=None,
                started=started,
            )
            raise AgentInvocationDenied(audit, status_code=503)

        calls = self._required_calls(invocation) + invocation.requested_tool_calls
        if len(calls) > profile.max_tool_calls:
            receipts = [
                AgentToolReceipt(
                    **call.model_dump(),
                    decision="deny",
                    executed=False,
                    reason="tool_call_budget_exceeded",
                )
                for call in calls
            ]
        else:
            receipts = [self._authorize_tool(call, invocation.request_id) for call in calls]

        denied = [receipt for receipt in receipts if receipt.decision == "deny"]
        if denied:
            reason = ";".join(f"{item.reason}:{item.tool_name}" for item in denied)
            audit = self._record(
                invocation=invocation,
                invocation_id=invocation_id,
                grant_id=grant_id,
                issued_at=issued_at,
                expires_at=expires_at,
                input_hash=input_hash,
                receipts=receipts,
                status="denied",
                termination_reason=reason,
                output=None,
                started=started,
            )
            raise AgentInvocationDenied(audit)

        if self._clock() >= expires_at:
            expired_receipts = [receipt.model_copy(update={"executed": False}) for receipt in receipts]
            audit = self._record(
                invocation=invocation,
                invocation_id=invocation_id,
                grant_id=grant_id,
                issued_at=issued_at,
                expires_at=expires_at,
                input_hash=input_hash,
                receipts=expired_receipts,
                status="denied",
                termination_reason="grant_expired",
                output=None,
                started=started,
            )
            raise AgentInvocationDenied(audit)

        diagnosis = self.provider.diagnose(invocation.request)
        used_asset_lookup = diagnosis.category.code == "waste_litter" and invocation.request.coordinates is not None
        executed_receipts = [
            receipt.model_copy(
                update={
                    "executed": receipt.tool_name == "case.read"
                    or (receipt.tool_name == "asset.lookup" and used_asset_lookup)
                }
            )
            for receipt in receipts
        ]
        if diagnosis.engine.model_dump(mode="json") != profile.provider.model_dump(mode="json"):
            audit = self._record(
                invocation=invocation,
                invocation_id=invocation_id,
                grant_id=grant_id,
                issued_at=issued_at,
                expires_at=expires_at,
                input_hash=input_hash,
                receipts=executed_receipts,
                status="failed",
                termination_reason="provider_identity_mismatch",
                output=diagnosis,
                started=started,
            )
            raise AgentInvocationDenied(audit, status_code=503)

        audit = self._record(
            invocation=invocation,
            invocation_id=invocation_id,
            grant_id=grant_id,
            issued_at=issued_at,
            expires_at=expires_at,
            input_hash=input_hash,
            receipts=executed_receipts,
            status="completed",
            termination_reason="completed_read_only",
            output=diagnosis,
            started=started,
        )
        return AgentInvocationResponse(diagnosis=diagnosis, audit=audit)
