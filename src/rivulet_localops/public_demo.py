import json
import os
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .agent_runtime import AgentInvocationDenied, CaseAgentRunner
from .assets import AssetRepository
from .capabilities import load_capability_registry
from .demo_models import (
    DemoBootstrap,
    DemoCapabilitySummary,
    DemoMetric,
    DemoRunResponse,
    DemoScenarioSummary,
    DemoSource,
)
from .gate import DeterministicPolicyGate
from .ledger import LedgerIntegrityError, SQLiteEventLedger
from .models import AgentInvocationRequest, AgentToolCallRequest, Coordinates, DecisionSubmissionRequest, DiagnoseRequest
from .policy import load_policy_pack
from .providers import RulesTriageProvider


PACKAGE_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ASSET_PATH = PACKAGE_ROOT / "data" / "hobart_litter_bins.geojson"
DEFAULT_POLICY_PATH = PACKAGE_ROOT / "data" / "policies" / "waste_litter_demo_v0.1.0.json"
DEFAULT_CAPABILITY_PATH = PACKAGE_ROOT / "data" / "agents" / "case_agent_v0.1.0.json"
DEFAULT_MART_REPORT_PATH = PACKAGE_ROOT / "data" / "mart" / "v1" / "build_report.json"
DEFAULT_STATIC_PATH = PACKAGE_ROOT / "web" / "dist"
DEFAULT_LEDGER_PATH = Path(os.getenv("RIVULET_DEMO_LEDGER_PATH", "/tmp/rivulet-demo.sqlite3"))


@dataclass(frozen=True)
class DemoScenario:
    summary: DemoScenarioSummary
    request: DiagnoseRequest
    requested_tool_calls: tuple[AgentToolCallRequest, ...] = ()


def _scenarios() -> dict[str, DemoScenario]:
    hobart_bin = Coordinates(latitude=-42.8867512572958, longitude=147.319119003722)
    return {
        "bin-near-asset": DemoScenario(
            summary=DemoScenarioSummary(
                scenario_id="bin-near-asset",
                title="Evidence complete",
                description="An overflowing litter bin is reported at a known public asset location.",
                expected_outcome="pass",
                learning_point="A permitted draft action passes only when policy evidence is complete.",
            ),
            request=DiagnoseRequest(
                text="Overflowing bin and dumped rubbish beside the public litter bin.",
                coordinates=hobart_bin,
            ),
        ),
        "bin-missing-location": DemoScenario(
            summary=DemoScenarioSummary(
                scenario_id="bin-missing-location",
                title="Required evidence missing",
                description="A clear waste report is submitted without coordinates.",
                expected_outcome="reject",
                learning_point="The deterministic Gate rejects the draft and names the missing field.",
            ),
            request=DiagnoseRequest(text="Overflowing bin with dumped rubbish needs collection."),
        ),
        "safety-escalation": DemoScenario(
            summary=DemoScenarioSummary(
                scenario_id="safety-escalation",
                title="Safety escalation",
                description="A waste report includes an emergency phrase even though location evidence is present.",
                expected_outcome="escalate",
                learning_point="P1 safety and human-review rules override otherwise complete evidence.",
            ),
            request=DiagnoseRequest(
                text="Dumped rubbish beside the bin is on fire and presents immediate danger.",
                coordinates=hobart_bin,
            ),
        ),
        "blocked-shell": DemoScenario(
            summary=DemoScenarioSummary(
                scenario_id="blocked-shell",
                title="Capability denied",
                description="The read-only case agent is asked to execute a shell tool.",
                expected_outcome="deny",
                learning_point="Deny-by-default capability checks stop the tool before provider execution.",
            ),
            request=DiagnoseRequest(
                text="Overflowing bin and dumped rubbish beside the public litter bin.",
                coordinates=hobart_bin,
            ),
            requested_tool_calls=(
                AgentToolCallRequest(
                    tool_name="shell.exec",
                    resource="host:public-demo",
                    data_class="system_control",
                ),
            ),
        ),
        "cross-case-read": DemoScenario(
            summary=DemoScenarioSummary(
                scenario_id="cross-case-read",
                title="Cross-case access denied",
                description="The case agent requests a different case than the server-owned current case.",
                expected_outcome="deny",
                learning_point="Resource-level scope is checked as well as tool and data class.",
            ),
            request=DiagnoseRequest(text="Overflowing bin with dumped rubbish needs collection."),
            requested_tool_calls=(
                AgentToolCallRequest(
                    tool_name="case.read",
                    resource="case:another-case",
                    data_class="synthetic_case",
                ),
            ),
        ),
    }


class SlidingWindowRateLimiter:
    def __init__(self, limit: int = 30, window_seconds: int = 60, clock: Callable[[], float] | None = None):
        self.limit = limit
        self.window_seconds = window_seconds
        self._clock = clock or time.monotonic
        self._events: defaultdict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = self._clock()
        cutoff = now - self.window_seconds
        with self._lock:
            events = self._events[key]
            while events and events[0] <= cutoff:
                events.popleft()
            if len(events) >= self.limit:
                return False
            events.append(now)
            return True


def _load_bootstrap(mart_report_path: Path, case_agent: CaseAgentRunner) -> DemoBootstrap:
    report = json.loads(mart_report_path.read_text(encoding="utf-8"))
    rows = report["table_rows"]
    metrics = report["metrics"]
    profile = case_agent.profile
    scenarios = [scenario.summary for scenario in _scenarios().values()]
    return DemoBootstrap(
        product="Rivulet LocalOps",
        release="v0.7.1",
        profile="public_demo",
        environment_note=(
            "Public portfolio sandbox. Runtime audit state is ephemeral and may reset when the container scales to zero "
            "or a new revision is deployed."
        ),
        metrics=[
            DemoMetric(
                metric_id="public_asset_count",
                label="Hobart public assets",
                value=rows["dim_asset"],
                display_value=f"{rows['dim_asset']:,}",
                truth_class="real_public_reference",
                context="D1 public litter-bin reference rows; not live council operations.",
            ),
            DemoMetric(
                metric_id="published_reference_request_count",
                label="Published reference requests",
                value=rows["fact_reference_request_volume"],
                display_value=f"{rows['fact_reference_request_volume']:,}",
                truth_class="real_public_reference",
                context="D2 Townsville aggregate reference rows; not Hobart demand.",
            ),
            DemoMetric(
                metric_id="synthetic_decision_count",
                label="Synthetic decisions",
                value=metrics["decision_count"],
                display_value=f"{metrics['decision_count']:,}",
                truth_class="synthetic_operational",
                context="Fixed-seed D6 coverage fixture; not real workload volume.",
            ),
            DemoMetric(
                metric_id="synthetic_review_rate",
                label="Synthetic review coverage",
                value=metrics["review_rate"],
                display_value=f"{metrics['review_rate']:.0%}",
                truth_class="synthetic_operational",
                context="Regression fixture only; not an approved operational target.",
            ),
        ],
        sources=[
            DemoSource(
                source_id="D1",
                label="City of Hobart litter-bin assets",
                row_count=rows["dim_asset"],
                truth_class="real_public_reference",
                use="Nearest-asset evidence for the waste/litter scenario.",
                limitation="Public reference snapshot; not a live asset service.",
            ),
            DemoSource(
                source_id="D2",
                label="Townsville request-volume reference",
                row_count=rows["fact_reference_request_volume"],
                truth_class="real_public_reference",
                use="Tests source contracts, profiling and dimensional modelling.",
                limitation="Publisher-supplied aggregate rows; not Hobart demand or individual cases.",
            ),
            DemoSource(
                source_id="D6",
                label="Fixed-seed operational ledger",
                row_count=metrics["decision_count"],
                truth_class="synthetic_operational",
                use="Exercises Gate, review, fallback and assurance metrics.",
                limitation="Designed coverage fixture; cannot support performance or accuracy claims.",
            ),
        ],
        gate_mix={
            "pass": metrics["gate_pass_rate"],
            "reject": metrics["gate_reject_rate"],
            "escalate": metrics["gate_escalate_rate"],
        },
        scenarios=scenarios,
        capability=DemoCapabilitySummary(
            agent_id=profile.agent_id,
            automation_level=profile.automation_level,
            identity_owner=profile.owner_id,
            grant_ttl_seconds=profile.grant_ttl_seconds,
            max_tool_calls=profile.max_tool_calls,
            allowed_tools=[tool.tool_name for tool in profile.allowed_tools],
            explicitly_denied_tools=profile.explicitly_denied_tools,
            default_policy_deny=profile.default_policy_deny,
            credential_mode=profile.credential_mode,
        ),
        claim_boundary=report["claim_boundary"],
    )


def create_public_demo_app(
    *,
    asset_path: Path = DEFAULT_ASSET_PATH,
    policy_path: Path = DEFAULT_POLICY_PATH,
    capability_path: Path = DEFAULT_CAPABILITY_PATH,
    mart_report_path: Path = DEFAULT_MART_REPORT_PATH,
    ledger_path: Path = DEFAULT_LEDGER_PATH,
    static_path: Path | None = DEFAULT_STATIC_PATH,
    rate_limit: int = 30,
) -> FastAPI:
    policy = load_policy_pack(policy_path)
    registry = load_capability_registry(capability_path)
    assets = AssetRepository(asset_path)
    provider = RulesTriageProvider(assets, policy.evidence.max_asset_distance_metres)
    ledger = SQLiteEventLedger(ledger_path)
    case_agent = CaseAgentRunner(registry, provider, ledger, policy.version)
    gate = DeterministicPolicyGate(policy)
    scenarios = _scenarios()

    application = FastAPI(
        title="Rivulet LocalOps Public Demo",
        version="0.7.1",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    application.state.ledger = ledger
    application.state.case_agent = case_agent
    application.state.rate_limiter = SlidingWindowRateLimiter(limit=rate_limit)

    def add_public_headers(response: Response, request_path: str) -> Response:
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
            "connect-src 'self'; font-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'"
        )
        if request_path == "/" or request_path.endswith(".html"):
            response.headers["Cache-Control"] = "no-cache"
        return response

    @application.middleware("http")
    async def public_boundary(request: Request, call_next):
        content_length = request.headers.get("content-length")
        try:
            body_too_large = content_length is not None and int(content_length) > 1024
        except ValueError:
            body_too_large = True
        if body_too_large:
            return add_public_headers(
                JSONResponse(status_code=413, content={"detail": "Request body is too large."}),
                request.url.path,
            )
        response = await call_next(request)
        return add_public_headers(response, request.url.path)

    @application.exception_handler(LedgerIntegrityError)
    async def ledger_integrity_failure(_: Request, __: LedgerIntegrityError) -> JSONResponse:
        return JSONResponse(status_code=503, content={"detail": "Demo audit integrity check failed; retry later."})

    @application.get("/healthz")
    def health() -> dict[str, str | int | bool]:
        integrity = ledger.verify_integrity()
        return {
            "status": "ok" if integrity.ok else "degraded",
            "profile": "public_demo",
            "release": "v0.7.1",
            "ledger_integrity_ok": integrity.ok,
            "ledger_event_count": integrity.event_count,
        }

    @application.get("/demo/v1/bootstrap", response_model=DemoBootstrap)
    def bootstrap() -> DemoBootstrap:
        return _load_bootstrap(mart_report_path, case_agent)

    @application.post("/demo/v1/scenarios/{scenario_id}/run", response_model=DemoRunResponse)
    def run_scenario(scenario_id: str, request: Request) -> DemoRunResponse:
        scenario = scenarios.get(scenario_id)
        if scenario is None:
            raise HTTPException(status_code=404, detail="Unknown predefined scenario.")
        client_key = request.client.host if request.client else "unknown"
        if not application.state.rate_limiter.allow(client_key):
            raise HTTPException(status_code=429, detail="Demo rate limit exceeded; retry in one minute.")

        request_id = f"demo-{scenario_id}-{uuid4().hex[:12]}"
        invocation = AgentInvocationRequest(
            request_id=request_id,
            request=scenario.request,
            correlation_id=f"cor-{uuid4().hex}",
            requested_tool_calls=list(scenario.requested_tool_calls),
        )
        diagnosis = None
        gate_decision = None
        try:
            result = case_agent.invoke(invocation)
            diagnosis = result.diagnosis
            audit = result.audit
            submission = DecisionSubmissionRequest(
                request=scenario.request,
                proposed_action="create_draft_work_order",
                accountable_owner_id="service-owner.demo",
                correlation_id=invocation.correlation_id,
            )
            gate_decision = gate.evaluate(submission, diagnosis)
            observed_outcome = gate_decision.status
        except AgentInvocationDenied as error:
            audit = error.audit
            observed_outcome = "failed" if audit.status == "failed" else "deny"

        integrity = ledger.verify_integrity()
        if not integrity.ok:
            raise LedgerIntegrityError(integrity.message)
        return DemoRunResponse(
            scenario=scenario.summary,
            observed_outcome=observed_outcome,
            outcome_matches_fixture=observed_outcome == scenario.summary.expected_outcome,
            diagnosis=diagnosis,
            gate=gate_decision,
            audit=audit,
            ledger_integrity_ok=integrity.ok,
            ledger_event_count=integrity.event_count,
            reset_notice="Runtime audit rows are ephemeral and may reset after scale-to-zero or deployment.",
        )

    if static_path is not None and static_path.is_dir():
        application.mount("/", StaticFiles(directory=static_path, html=True), name="web")

    return application


app = create_public_demo_app()
