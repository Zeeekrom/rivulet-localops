from typing import Literal

from pydantic import BaseModel, Field

from .models import AgentInvocationAuditRecord, DiagnoseResponse, GateDecision


TruthClass = Literal[
    "real_public_reference",
    "synthetic_operational",
    "synthetic_case",
    "runtime_observation",
]


class DemoMetric(BaseModel):
    metric_id: str
    label: str
    value: float
    display_value: str
    truth_class: TruthClass
    context: str


class DemoSource(BaseModel):
    source_id: str
    label: str
    row_count: int = Field(ge=0)
    truth_class: TruthClass
    use: str
    limitation: str


class DemoScenarioSummary(BaseModel):
    scenario_id: str
    title: str
    description: str
    expected_outcome: Literal["pass", "reject", "escalate", "deny"]
    learning_point: str
    truth_class: Literal["synthetic_case"] = "synthetic_case"


class DemoCapabilitySummary(BaseModel):
    agent_id: str
    automation_level: Literal["L0_shadow_read_only"]
    identity_owner: str
    grant_ttl_seconds: int
    max_tool_calls: int
    allowed_tools: list[str]
    explicitly_denied_tools: list[str]
    default_policy_deny: Literal[True]
    credential_mode: Literal["none"]


class DemoBootstrap(BaseModel):
    product: str
    release: str
    profile: Literal["public_demo"]
    environment_note: str
    metrics: list[DemoMetric]
    sources: list[DemoSource]
    gate_mix: dict[Literal["pass", "reject", "escalate"], float]
    scenarios: list[DemoScenarioSummary]
    capability: DemoCapabilitySummary
    claim_boundary: str


class DemoRunResponse(BaseModel):
    scenario: DemoScenarioSummary
    observed_outcome: Literal["pass", "reject", "escalate", "deny", "failed"]
    outcome_matches_fixture: bool
    diagnosis: DiagnoseResponse | None
    gate: GateDecision | None
    audit: AgentInvocationAuditRecord
    ledger_integrity_ok: bool
    ledger_event_count: int = Field(ge=0)
    reset_notice: str
