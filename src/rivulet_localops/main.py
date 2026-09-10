import os
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from .assets import AssetRepository
from .gate import DeterministicPolicyGate
from .ledger import LedgerIntegrityError, SQLiteEventLedger
from .models import (
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


DEFAULT_ASSET_PATH = Path(__file__).resolve().parents[2] / "data" / "hobart_litter_bins.geojson"
DEFAULT_POLICY_PATH = Path(__file__).resolve().parents[2] / "data" / "policies" / "waste_litter_demo_v0.1.0.json"
DEFAULT_LEDGER_PATH = Path(__file__).resolve().parents[2] / "data" / "runtime" / "rivulet_localops.sqlite3"
PROVIDER_ID = "deterministic-rules"


def create_app(
    asset_path: Path | None = None,
    policy_path: Path | None = None,
    ledger_path: Path | None = None,
) -> FastAPI:
    resolved_path = asset_path or Path(os.getenv("RIVULET_ASSET_PATH", DEFAULT_ASSET_PATH))
    resolved_policy_path = policy_path or Path(os.getenv("RIVULET_POLICY_PATH", DEFAULT_POLICY_PATH))
    resolved_ledger_path = ledger_path or Path(os.getenv("RIVULET_LEDGER_PATH", DEFAULT_LEDGER_PATH))
    policy = load_policy_pack(resolved_policy_path)
    assets = AssetRepository(resolved_path)
    provider = RulesTriageProvider(assets, policy.evidence.max_asset_distance_metres)
    gate = DeterministicPolicyGate(policy)
    ledger = SQLiteEventLedger(resolved_ledger_path)

    application = FastAPI(
        title="Rivulet LocalOps",
        version="0.4.1",
        description="Explainable and accountable service-request decision support for small Tasmanian councils.",
    )
    application.state.ledger = ledger

    @application.exception_handler(LedgerIntegrityError)
    async def ledger_integrity_failure(_: Request, error: LedgerIntegrityError) -> JSONResponse:
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
        integrity = ledger.verify_integrity()
        provider_status = _provider_status() if integrity.ok else None
        return {
            "status": "ok" if integrity.ok else "degraded",
            "engine": PROVIDER_ID,
            "provider_disabled": provider_status.disabled if provider_status else True,
            "asset_count": assets.count,
            "policy_id": policy.policy_id,
            "policy_version": policy.version,
            "policy_is_synthetic": policy.is_synthetic,
            "ledger_event_count": integrity.event_count,
            "ledger_integrity_ok": integrity.ok,
        }

    @application.post("/api/v1/diagnose", response_model=DiagnoseResponse)
    def diagnose(request: DiagnoseRequest) -> DiagnoseResponse:
        _require_ledger_integrity()
        if _provider_status().disabled:
            raise HTTPException(
                status_code=503,
                detail={
                    "status": "manual_fallback",
                    "provider_id": PROVIDER_ID,
                    "message": "Provider is disabled by kill switch; route the request to manual handling.",
                },
            )
        return provider.diagnose(request)

    @application.post("/api/v1/submit", response_model=DecisionRecord)
    def submit(submission: DecisionSubmissionRequest) -> DecisionRecord:
        _require_ledger_integrity()
        if _provider_status().disabled:
            fallback_event = ledger.record_manual_fallback(submission, PROVIDER_ID)
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
        return ledger.record_decision(submission, gate_decision)

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
