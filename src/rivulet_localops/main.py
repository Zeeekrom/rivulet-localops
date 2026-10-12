import os
from pathlib import Path
from typing import Literal, Mapping

from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse

from . import __version__
from .agent_runtime import AgentInvocationDenied, CaseAgentRunner
from .assets import AssetRepository
from .capabilities import load_capability_registry
from .gate import DeterministicPolicyGate
from .ledger import LedgerIntegrityError, SQLiteEventLedger
from .models import (
    AgentCapabilityProfile,
    AgentInvocationListResponse,
    AgentInvocationRequest,
    AgentInvocationResponse,
    DecisionListResponse,
    DecisionRecord,
    DecisionSubmissionRequest,
    DiagnoseRequest,
    DiagnoseResponse,
    IntegrityReport,
    ProviderControlRequest,
    ProviderStatus,
    ReplayRequest,
    ReplayResult,
    ReviewRequest,
)
from .policy import load_policy_pack
from .providers import RulesTriageProvider
from .operations import (
    ApplicationOperations,
    ComponentStatus,
    InternalHealthReport,
    OperationalLogBuffer,
    OperationalLogRecord,
    SupportBundle,
    elapsed_ms,
    error_category,
    operation_timer,
    safe_identifier,
)
from .ops_ui import operations_support_html


DEFAULT_ASSET_PATH = Path(__file__).resolve().parents[2] / "data" / "hobart_litter_bins.geojson"
DEFAULT_POLICY_PATH = Path(__file__).resolve().parents[2] / "data" / "policies" / "waste_litter_demo_v0.1.0.json"
DEFAULT_CAPABILITY_PATH = Path(__file__).resolve().parents[2] / "data" / "agents" / "case_agent_v0.1.0.json"
DEFAULT_LEDGER_PATH = Path(__file__).resolve().parents[2] / "data" / "runtime" / "rivulet_localops.sqlite3"
PROVIDER_ID = "deterministic-rules"


def create_app(
    asset_path: Path | None = None,
    policy_path: Path | None = None,
    ledger_path: Path | None = None,
    capability_path: Path | None = None,
    operational_log: OperationalLogBuffer | None = None,
    environment: Mapping[str, str] | None = None,
    health_overrides: Mapping[str, ComponentStatus] | None = None,
) -> FastAPI:
    resolved_path = asset_path or Path(os.getenv("RIVULET_ASSET_PATH", DEFAULT_ASSET_PATH))
    resolved_policy_path = policy_path or Path(os.getenv("RIVULET_POLICY_PATH", DEFAULT_POLICY_PATH))
    resolved_capability_path = capability_path or Path(os.getenv("RIVULET_CAPABILITY_PATH", DEFAULT_CAPABILITY_PATH))
    resolved_ledger_path = ledger_path or Path(os.getenv("RIVULET_LEDGER_PATH", DEFAULT_LEDGER_PATH))
    policy = load_policy_pack(resolved_policy_path)
    capability_registry = load_capability_registry(resolved_capability_path)
    assets = AssetRepository(resolved_path)
    provider = RulesTriageProvider(assets, policy.evidence.max_asset_distance_metres)
    gate = DeterministicPolicyGate(policy)
    ledger = SQLiteEventLedger(resolved_ledger_path)
    case_agent = CaseAgentRunner(capability_registry, provider, ledger, policy.version)
    runtime_environment = dict(environment if environment is not None else os.environ)
    log_buffer = operational_log or OperationalLogBuffer()
    operations = ApplicationOperations(
        ledger=ledger,
        policy_version=policy.version,
        provider_reference=provider.reference,
        operational_log=log_buffer,
        asset_count=assets.count,
        environment=runtime_environment,
        health_overrides=health_overrides,
    )

    application = FastAPI(
        title="Rivulet LocalOps",
        version=__version__,
        description="Explainable and accountable service-request decision support for small Tasmanian councils.",
    )
    application.state.ledger = ledger
    application.state.case_agent = case_agent
    application.state.operations = operations
    application.state.operational_log = log_buffer

    @application.middleware("http")
    async def operational_logging(request: Request, call_next):
        started_at = operation_timer()
        correlation_id = safe_identifier(request.headers.get("x-correlation-id"), "cor")
        request_id = safe_identifier(request.headers.get("x-request-id"), "req")
        request.state.correlation_id = correlation_id
        request.state.request_id = request_id
        request.state.operation_context = {}
        try:
            response = await call_next(request)
        except Exception as error:
            route = getattr(request.scope.get("route"), "path", "unmatched")
            log_buffer.append(
                level="error",
                event_name="http_request_failed",
                component_name="api",
                correlation_id=correlation_id,
                request_id=request_id,
                route=route,
                method=request.method,
                status_code=500,
                elapsed_ms=elapsed_ms(started_at),
                policy_version=policy.version,
                provider=provider.reference.provider,
                provider_version=provider.reference.version,
                error_category=error_category(error),
            )
            raise

        context = request.state.operation_context
        route = getattr(request.scope.get("route"), "path", "unmatched")
        response.headers["X-Correlation-ID"] = correlation_id
        response.headers["X-Request-ID"] = request_id
        log_buffer.append(
            level="error" if response.status_code >= 500 else "warning" if response.status_code >= 400 else "info",
            event_name=context.get("event_name", "http_request_completed"),
            component_name=context.get("component_name", "api"),
            correlation_id=context.get("correlation_id", correlation_id),
            request_id=context.get("request_id", request_id),
            route=route,
            method=request.method,
            status_code=response.status_code,
            elapsed_ms=elapsed_ms(started_at),
            policy_version=context.get("policy_version", policy.version),
            provider=context.get("provider", provider.reference.provider),
            provider_version=context.get("provider_version", provider.reference.version),
            gate_result=context.get("gate_result"),
            ledger_event_id=context.get("ledger_event_id"),
            error_category=context.get("error_category") or ("http_5xx" if response.status_code >= 500 else None),
        )
        return response

    def _mark_operation(request: Request, **fields: str | None) -> None:
        request.state.operation_context.update({key: value for key, value in fields.items() if value is not None})

    @application.exception_handler(LedgerIntegrityError)
    async def ledger_integrity_failure(request: Request, error: LedgerIntegrityError) -> JSONResponse:
        _mark_operation(
            request,
            event_name="ledger_integrity_failure",
            component_name="database_ledger",
            error_category="ledger_integrity",
        )
        return JSONResponse(
            status_code=503,
            content={
                "detail": {
                    "status": "manual_fallback",
                    "reason": "ledger_integrity_failure",
                    "message": str(error),
                }
            },
        )

    def _provider_status(provider_id: str = PROVIDER_ID) -> ProviderStatus:
        if provider_id != PROVIDER_ID:
            raise HTTPException(status_code=404, detail="Unknown provider")
        return ledger.get_provider_status(provider_id)

    def _require_ledger_integrity() -> None:
        integrity = ledger.verify_integrity()
        if not integrity.ok:
            raise LedgerIntegrityError(integrity.message)

    @application.get("/health")
    def health() -> dict[str, str | int | bool]:
        report = operations.health()
        integrity = next(item for item in report.components if item.component == "database_ledger")
        provider_component = next(item for item in report.components if item.component == "provider")
        return {
            "status": report.status,
            "engine": PROVIDER_ID,
            "provider_disabled": bool(provider_component.details.get("manual_fallback", True)),
            "asset_count": assets.count,
            "policy_id": policy.policy_id,
            "policy_version": policy.version,
            "policy_is_synthetic": policy.is_synthetic,
            "ledger_event_count": int(integrity.details.get("event_count", 0)),
            "ledger_integrity_ok": bool(integrity.details.get("integrity_ok", False)),
        }

    @application.get("/ops/v1/health", response_model=InternalHealthReport)
    def internal_health(response: Response) -> InternalHealthReport:
        report = operations.health()
        if report.status == "unavailable":
            response.status_code = 503
        return report

    @application.get("/ops/v1/support/bundle", response_model=SupportBundle)
    def support_bundle(request: Request) -> SupportBundle:
        _mark_operation(request, event_name="support_bundle_exported", component_name="operations_support")
        return operations.support_bundle()

    @application.get("/ops/v1/operations/logs", response_model=list[OperationalLogRecord])
    def operational_logs(limit: int = Query(default=100, ge=1, le=200)) -> list[OperationalLogRecord]:
        return log_buffer.recent(limit)

    @application.get("/ops/v1/runbooks")
    def runbooks() -> dict[str, list[dict[str, str]]]:
        return {
            "items": [
                {
                    "incident_id": incident.incident_id,
                    "title": incident.title,
                    "document": f"docs/application-support/runbooks/{incident.incident_id.lower()}.md",
                }
                for incident in operations.incidents()
            ]
        }

    @application.get("/ops/support", response_class=HTMLResponse)
    def operations_support_page() -> str:
        return operations_support_html()

    @application.post("/api/v1/diagnose", response_model=DiagnoseResponse)
    def diagnose(payload: DiagnoseRequest, request: Request) -> DiagnoseResponse:
        _require_ledger_integrity()
        if _provider_status().disabled:
            _mark_operation(
                request,
                event_name="diagnosis_manual_fallback",
                component_name="provider",
                gate_result="manual_fallback",
                error_category="provider_disabled",
            )
            raise HTTPException(
                status_code=503,
                detail={
                    "status": "manual_fallback",
                    "provider_id": PROVIDER_ID,
                    "message": "Provider is disabled by kill switch; route the request to manual handling.",
                },
            )
        result = provider.diagnose(payload)
        _mark_operation(request, event_name="diagnosis_completed", component_name="provider")
        return result

    @application.post("/api/v1/submit", response_model=DecisionRecord)
    def submit(submission: DecisionSubmissionRequest, request: Request) -> DecisionRecord:
        _require_ledger_integrity()
        if _provider_status().disabled:
            fallback_event = ledger.record_manual_fallback(submission, PROVIDER_ID)
            _mark_operation(
                request,
                event_name="decision_manual_fallback",
                component_name="provider",
                correlation_id=submission.correlation_id,
                gate_result="manual_fallback",
                ledger_event_id=fallback_event["event_id"],
                error_category="provider_disabled",
            )
            raise HTTPException(
                status_code=503,
                detail={
                    "status": "manual_fallback",
                    "provider_id": PROVIDER_ID,
                    "correlation_id": submission.correlation_id,
                    "ledger_event_id": fallback_event["event_id"],
                    "message": "Provider is disabled; no automated diagnosis ran and the request must be handled manually.",
                },
            )
        diagnosis = provider.diagnose(submission.request)
        gate_decision = gate.evaluate(submission, diagnosis)
        record = ledger.record_decision(submission, gate_decision)
        _mark_operation(
            request,
            event_name="decision_recorded",
            component_name="policy_gate",
            correlation_id=submission.correlation_id,
            gate_result=gate_decision.status,
            ledger_event_id=record.ledger_event_id,
        )
        return record

    @application.get("/ops/v1/agents/{agent_id}/capabilities", response_model=AgentCapabilityProfile)
    def get_agent_capabilities(agent_id: str) -> AgentCapabilityProfile:
        _require_ledger_integrity()
        if agent_id != case_agent.agent_id:
            raise HTTPException(status_code=404, detail="Unknown agent identity")
        return case_agent.profile

    @application.post("/api/v1/agents/case-agent/invoke", response_model=AgentInvocationResponse)
    def invoke_case_agent(invocation: AgentInvocationRequest, request: Request) -> AgentInvocationResponse:
        _require_ledger_integrity()
        try:
            result = case_agent.invoke(invocation, provider_disabled=_provider_status().disabled)
            _mark_operation(
                request,
                event_name="agent_invocation_completed",
                component_name="case_agent",
                correlation_id=invocation.correlation_id,
                request_id=invocation.request_id,
                gate_result=result.audit.gate_result,
                ledger_event_id=result.audit.ledger_event_id,
            )
            return result
        except AgentInvocationDenied as error:
            _mark_operation(
                request,
                event_name="agent_invocation_denied",
                component_name="case_agent",
                correlation_id=invocation.correlation_id,
                request_id=invocation.request_id,
                gate_result=error.audit.status,
                ledger_event_id=error.audit.ledger_event_id,
                error_category="capability_denied" if error.status_code == 403 else "provider_disabled",
            )
            raise HTTPException(
                status_code=error.status_code,
                detail={
                    "status": "capability_denied" if error.status_code == 403 else "manual_fallback",
                    "audit": error.audit.model_dump(mode="json"),
                },
            ) from error

    @application.get("/ops/v1/agents/invocations", response_model=AgentInvocationListResponse)
    def list_agent_invocations(
        limit: int = Query(default=50, ge=1, le=200),
        status: Literal["completed", "denied", "failed"] | None = None,
    ) -> AgentInvocationListResponse:
        _require_ledger_integrity()
        return ledger.list_agent_invocations(limit=limit, status=status)

    @application.get("/api/v1/decisions", response_model=DecisionListResponse)
    def list_decisions(
        limit: int = Query(default=50, ge=1, le=200),
        review_state: Literal["pending", "reviewed"] | None = None,
    ) -> DecisionListResponse:
        _require_ledger_integrity()
        return ledger.list_decisions(limit=limit, review_state=review_state)

    @application.get("/api/v1/decisions/{decision_id}", response_model=DecisionRecord)
    def get_decision(decision_id: str) -> DecisionRecord:
        _require_ledger_integrity()
        record = ledger.get_decision(decision_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Decision not found")
        return record

    @application.post("/api/v1/decisions/{decision_id}/reviews", response_model=DecisionRecord)
    def review_decision(decision_id: str, review: ReviewRequest) -> DecisionRecord:
        _require_ledger_integrity()
        record = ledger.get_decision(decision_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Decision not found")
        if review.reviewer_id == record.accountable_owner_id:
            raise HTTPException(status_code=409, detail="The accountable owner cannot independently review the same decision.")
        if review.action == "accept" and record.gate_decision.status != "pass":
            raise HTTPException(
                status_code=409,
                detail="A rejected or escalated Gate decision cannot be accepted; use override or escalate with a reason.",
            )
        return ledger.record_review(decision_id, review)

    @application.post("/api/v1/decisions/{decision_id}/replay", response_model=ReplayResult)
    def replay_decision(decision_id: str, replay: ReplayRequest) -> ReplayResult:
        _require_ledger_integrity()
        record = ledger.get_decision(decision_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Decision not found")
        if _provider_status().disabled:
            raise HTTPException(status_code=409, detail="Provider is disabled; replay is unavailable in manual mode.")

        replay_submission = DecisionSubmissionRequest(
            request=record.request,
            proposed_action=record.proposed_action,
            accountable_owner_id=record.accountable_owner_id,
            correlation_id=record.correlation_id,
            data_truth_class=record.data_truth_class,
            source=record.source,
            environment=record.environment,
        )
        replay_diagnosis = provider.diagnose(record.request)
        replay_gate = gate.evaluate(replay_submission, replay_diagnosis)
        original_rules = [
            (rule.rule_id, rule.outcome, rule.effect)
            for rule in record.gate_decision.rule_results
        ]
        replay_rules = [(rule.rule_id, rule.outcome, rule.effect) for rule in replay_gate.rule_results]
        comparison = {
            "policy_version_match": record.policy.version == replay_gate.policy.version,
            "policy_hash_match": record.policy.content_hash == replay_gate.policy.content_hash,
            "provider_version_match": record.provider.version == replay_gate.diagnosis.engine.version,
            "gate_status_match": record.gate_decision.status == replay_gate.status,
            "category_match": record.gate_decision.diagnosis.category.code == replay_gate.diagnosis.category.code,
            "priority_match": record.gate_decision.diagnosis.priority.code == replay_gate.diagnosis.priority.code,
            "rule_outcomes_match": original_rules == replay_rules,
        }
        comparison["reproducible"] = all(comparison.values())
        return ledger.record_replay(
            decision_id=decision_id,
            operator_id=replay.operator_id,
            correlation_id=record.correlation_id,
            comparison=comparison,
        )

    @application.get("/ops/v1/providers/{provider_id}", response_model=ProviderStatus)
    def get_provider_status(provider_id: str) -> ProviderStatus:
        _require_ledger_integrity()
        return _provider_status(provider_id)

    @application.post("/ops/v1/providers/{provider_id}/kill-switch", response_model=ProviderStatus)
    def set_provider_status(provider_id: str, control: ProviderControlRequest) -> ProviderStatus:
        _require_ledger_integrity()
        _provider_status(provider_id)
        return ledger.set_provider_status(provider_id, control)

    @application.get("/ops/v1/ledger/integrity", response_model=IntegrityReport)
    def ledger_integrity() -> IntegrityReport:
        return ledger.verify_integrity()

    return application


app = create_app()
