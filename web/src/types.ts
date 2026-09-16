export type TruthClass =
  | "real_public_reference"
  | "synthetic_operational"
  | "synthetic_case"
  | "runtime_observation";

export type Outcome = "pass" | "reject" | "escalate" | "deny" | "failed";

export interface DemoMetric {
  metric_id: string;
  label: string;
  value: number;
  display_value: string;
  truth_class: TruthClass;
  context: string;
}

export interface DemoSource {
  source_id: string;
  label: string;
  row_count: number;
  truth_class: TruthClass;
  use: string;
  limitation: string;
}

export interface Scenario {
  scenario_id: string;
  title: string;
  description: string;
  expected_outcome: Exclude<Outcome, "failed">;
  learning_point: string;
  truth_class: "synthetic_case";
}

export interface Capability {
  agent_id: string;
  automation_level: "L0_shadow_read_only";
  identity_owner: string;
  grant_ttl_seconds: number;
  max_tool_calls: number;
  allowed_tools: string[];
  explicitly_denied_tools: string[];
  default_policy_deny: true;
  credential_mode: "none";
}

export interface Bootstrap {
  product: string;
  release: string;
  profile: "public_demo";
  environment_note: string;
  metrics: DemoMetric[];
  sources: DemoSource[];
  gate_mix: Record<"pass" | "reject" | "escalate", number>;
  scenarios: Scenario[];
  capability: Capability;
  claim_boundary: string;
}

interface ToolReceipt {
  tool_name: string;
  resource: string;
  data_class: string;
  decision: "allow" | "deny";
  executed: boolean;
  reason: string;
}

interface Audit {
  invocation_id: string;
  agent_id: string;
  automation_level: string;
  registry_version: string;
  grant_expires_at: string;
  allowed_tools: string[];
  tool_receipts: ToolReceipt[];
  status: "completed" | "denied" | "failed";
  latency_ms: number;
  termination_reason: string;
  input_hash: string;
  output_hash: string | null;
  event_hash: string;
  previous_event_hash: string | null;
  raw_input_stored: false;
  human_decision: "pending";
  credential_mode: "none";
}

interface Diagnosis {
  category: { code: string; label: string; confidence: number; matched_terms: string[] };
  priority: { code: string; label: string; target_hours: number; policy_rule: string };
  asset_match: null | { description: string | null; distance_metres: number; source: string };
  explanation: string[];
  missing_information: string[];
  human_review_required: boolean;
  disclaimer: string;
}

interface GateRule {
  rule_id: string;
  outcome: "pass" | "fail" | "not_applicable";
  effect: "allow" | "reject" | "escalate";
  message: string;
}

interface Gate {
  status: "pass" | "reject" | "escalate";
  can_execute: boolean;
  missing_information: string[];
  rejection_reasons: string[];
  escalation_reasons: string[];
  rule_results: GateRule[];
  policy: { policy_id: string; version: string; title: string; is_synthetic: boolean; content_hash: string };
}

export interface DemoRun {
  scenario: Scenario;
  observed_outcome: Outcome;
  outcome_matches_fixture: boolean;
  diagnosis: Diagnosis | null;
  gate: Gate | null;
  audit: Audit;
  ledger_integrity_ok: boolean;
  ledger_event_count: number;
  reset_notice: string;
}
