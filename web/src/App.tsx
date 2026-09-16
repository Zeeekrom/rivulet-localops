import { useEffect, useMemo, useState } from "react";
import { fetchBootstrap, runScenario } from "./api";
import type { Bootstrap, DemoRun, Outcome, Scenario, TruthClass } from "./types";

const truthLabels: Record<TruthClass, string> = {
  real_public_reference: "Real public reference",
  synthetic_operational: "Synthetic operations",
  synthetic_case: "Synthetic case",
  runtime_observation: "Runtime observation"
};

const outcomeLabels: Record<Outcome, string> = {
  pass: "Gate passed",
  reject: "Gate rejected",
  escalate: "Human escalation",
  deny: "Capability denied",
  failed: "Runtime failed"
};

function shortHash(hash: string | null): string {
  if (!hash) return "Not produced";
  return `${hash.slice(0, 10)}…${hash.slice(-8)}`;
}

function TruthBadge({ value }: { value: TruthClass }) {
  return <span className={`truth-badge truth-${value}`}>{truthLabels[value]}</span>;
}

function StatusIcon({ outcome }: { outcome: Outcome }) {
  const glyph = outcome === "pass" ? "✓" : outcome === "reject" || outcome === "deny" ? "×" : "!";
  return <span className={`status-icon status-${outcome}`} aria-hidden="true">{glyph}</span>;
}

function MetricGrid({ data }: { data: Bootstrap }) {
  return (
    <div className="metric-grid" aria-label="Evidence summary">
      {data.metrics.map((metric) => (
        <article className="metric-card" key={metric.metric_id}>
          <div className="metric-topline">
            <span>{metric.label}</span>
            <TruthBadge value={metric.truth_class} />
          </div>
          <strong>{metric.display_value}</strong>
          <p>{metric.context}</p>
        </article>
      ))}
    </div>
  );
}

function ScenarioPicker({
  scenarios,
  selectedId,
  isRunning,
  onSelect,
  onRun
}: {
  scenarios: Scenario[];
  selectedId: string;
  isRunning: boolean;
  onSelect: (scenarioId: string) => void;
  onRun: () => void;
}) {
  const selected = scenarios.find((item) => item.scenario_id === selectedId) ?? scenarios[0];
  return (
    <section className="panel workbench" id="workbench" aria-labelledby="workbench-title">
      <div className="panel-heading">
        <div>
          <span className="eyebrow">Interactive evidence</span>
          <h2 id="workbench-title">Case workbench</h2>
        </div>
        <span className="sequence-pill">01 · Select fixture</span>
      </div>
      <p className="section-intro">
        Choose a server-owned test case. No visitor text, files or identifiers are accepted.
      </p>
      <div className="scenario-list" role="radiogroup" aria-label="Synthetic demonstration scenarios">
        {scenarios.map((scenario) => (
          <button
            type="button"
            role="radio"
            aria-checked={scenario.scenario_id === selectedId}
            className={`scenario-option ${scenario.scenario_id === selectedId ? "is-selected" : ""}`}
            key={scenario.scenario_id}
            onClick={() => onSelect(scenario.scenario_id)}
          >
            <span className={`outcome-dot outcome-${scenario.expected_outcome}`} />
            <span>
              <strong>{scenario.title}</strong>
              <small>{scenario.description}</small>
            </span>
            <span className="expected">Expected: {scenario.expected_outcome}</span>
          </button>
        ))}
      </div>
      <div className="selected-summary">
        <TruthBadge value="synthetic_case" />
        <p>{selected.learning_point}</p>
      </div>
      <button className="run-button" type="button" disabled={isRunning} onClick={onRun}>
        <span>{isRunning ? "Running controlled path…" : "Run controlled path"}</span>
        <span aria-hidden="true">→</span>
      </button>
    </section>
  );
}

function CapabilityPanel({ data }: { data: Bootstrap }) {
  const capability = data.capability;
  return (
    <aside className="panel capability-panel" aria-labelledby="capability-title">
      <div className="panel-heading compact">
        <div>
          <span className="eyebrow">Execution boundary</span>
          <h2 id="capability-title">Agent capability</h2>
        </div>
        <span className="live-chip"><span /> Enforced</span>
      </div>
      <div className="identity-block">
        <div className="agent-mark" aria-hidden="true">R</div>
        <div>
          <strong>{capability.agent_id}</strong>
          <span>{capability.automation_level.replaceAll("_", " ")}</span>
        </div>
      </div>
      <dl className="control-list">
        <div><dt>Identity owner</dt><dd>{capability.identity_owner}</dd></div>
        <div><dt>Grant lifetime</dt><dd>{capability.grant_ttl_seconds} seconds</dd></div>
        <div><dt>Tool-call budget</dt><dd>{capability.max_tool_calls} maximum</dd></div>
        <div><dt>Model credential</dt><dd>{capability.credential_mode}</dd></div>
      </dl>
      <div className="tool-boundary">
        <span className="mini-label">Allowed tools</span>
        <div className="token-row">
          {capability.allowed_tools.map((tool) => <code className="allow-token" key={tool}>{tool}</code>)}
        </div>
      </div>
      <div className="tool-boundary">
        <span className="mini-label">Examples denied before execution</span>
        <div className="token-row">
          {capability.explicitly_denied_tools.slice(0, 4).map((tool) => <code className="deny-token" key={tool}>{tool}</code>)}
        </div>
      </div>
      <div className="boundary-statement">
        <span className="shield" aria-hidden="true">◇</span>
        <p><strong>Deny by default.</strong> The agent can read one synthetic case and an approved public asset source. It cannot submit a decision.</p>
      </div>
    </aside>
  );
}

function EmptyResult() {
  return (
    <div className="empty-result">
      <div className="empty-orbit" aria-hidden="true"><span /><span /><span /></div>
      <h3>Run a controlled path</h3>
      <p>The result will expose agent receipts, every policy rule and the append-only audit hash.</p>
    </div>
  );
}

function RunResult({ result }: { result: DemoRun }) {
  const gateRules = result.gate?.rule_results ?? [];
  return (
    <div className="result-content">
      <div className="result-hero">
        <StatusIcon outcome={result.observed_outcome} />
        <div>
          <span className="eyebrow">Observed outcome</span>
          <h3>{outcomeLabels[result.observed_outcome]}</h3>
          <p>{result.scenario.learning_point}</p>
        </div>
        <span className={`match-chip ${result.outcome_matches_fixture ? "matched" : "mismatch"}`}>
          {result.outcome_matches_fixture ? "Fixture matched" : "Unexpected result"}
        </span>
      </div>

      <div className="pipeline" aria-label="Controlled decision path">
        <div className="pipeline-step complete"><span>1</span><div><strong>Case agent</strong><small>{result.audit.status}</small></div></div>
        <i />
        <div className={`pipeline-step ${result.gate ? "complete" : "stopped"}`}><span>2</span><div><strong>Policy Gate</strong><small>{result.gate?.status ?? "not run"}</small></div></div>
        <i />
        <div className="pipeline-step pending"><span>3</span><div><strong>Human decision</strong><small>pending</small></div></div>
      </div>

      <div className="result-columns">
        <div className="result-section">
          <div className="subheading"><h4>Agent receipts</h4><span>{result.audit.tool_receipts.length} checks</span></div>
          <div className="receipt-list">
            {result.audit.tool_receipts.map((receipt, index) => (
              <div className="receipt" key={`${receipt.tool_name}-${index}`}>
                <span className={`receipt-mark ${receipt.decision}`} aria-hidden="true">{receipt.decision === "allow" ? "✓" : "×"}</span>
                <div><code>{receipt.tool_name}</code><small>{receipt.resource} · {receipt.data_class}</small></div>
                <span className={`receipt-status ${receipt.decision}`}>{receipt.executed ? "executed" : receipt.decision}</span>
              </div>
            ))}
          </div>
          <div className="hash-grid">
            <div><span>Input hash</span><code>{shortHash(result.audit.input_hash)}</code></div>
            <div><span>Output hash</span><code>{shortHash(result.audit.output_hash)}</code></div>
            <div><span>Ledger event</span><code>{shortHash(result.audit.event_hash)}</code></div>
            <div><span>Raw input stored</span><strong>{result.audit.raw_input_stored ? "yes" : "no"}</strong></div>
          </div>
        </div>

        <div className="result-section">
          <div className="subheading"><h4>Policy evaluation</h4><span>{gateRules.length || "—"} rules</span></div>
          {result.diagnosis ? (
            <div className="diagnosis-strip">
              <div><span>Category</span><strong>{result.diagnosis.category.label}</strong></div>
              <div><span>Priority</span><strong>{result.diagnosis.priority.code}</strong></div>
              <div><span>Confidence</span><strong>{Math.round(result.diagnosis.category.confidence * 100)}%</strong></div>
              <div><span>Asset</span><strong>{result.diagnosis.asset_match ? `${result.diagnosis.asset_match.distance_metres.toFixed(1)} m` : "None"}</strong></div>
            </div>
          ) : (
            <p className="not-run">Diagnosis did not run because capability control stopped execution first.</p>
          )}
          <div className="rule-list">
            {gateRules.map((rule) => (
              <div className="rule" key={rule.rule_id}>
                <span className={`rule-mark rule-${rule.outcome}`} aria-hidden="true" />
                <div><code>{rule.rule_id}</code><p>{rule.message}</p></div>
                <span className={`rule-outcome rule-${rule.outcome}`}>{rule.outcome.replace("_", " ")}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
      <div className="integrity-line">
        <span className="integrity-dot" />
        Hash-chain integrity verified across {result.ledger_event_count} ephemeral runtime event{result.ledger_event_count === 1 ? "" : "s"}.
        <span>{result.audit.latency_ms.toFixed(1)} ms</span>
      </div>
    </div>
  );
}

function AssurancePanel({ result, isRunning, error }: { result: DemoRun | null; isRunning: boolean; error: string | null }) {
  return (
    <section className="panel assurance-panel" aria-labelledby="assurance-title" aria-live="polite">
      <div className="panel-heading">
        <div><span className="eyebrow">Decision trace</span><h2 id="assurance-title">Assurance record</h2></div>
        <span className="sequence-pill">02 · Inspect controls</span>
      </div>
      {isRunning && <div className="loading-result"><span /><p>Authorising tools and evaluating policy…</p></div>}
      {!isRunning && error && <div className="error-result"><strong>Run unavailable</strong><p>{error}</p></div>}
      {!isRunning && !error && (result ? <RunResult result={result} /> : <EmptyResult />)}
    </section>
  );
}

function AnalyticsSection({ data }: { data: Bootstrap }) {
  const mix = Object.entries(data.gate_mix) as ["pass" | "reject" | "escalate", number][];
  return (
    <section className="evidence-section" id="evidence" aria-labelledby="evidence-title">
      <div className="section-heading-row">
        <div><span className="eyebrow">Measured with boundaries</span><h2 id="evidence-title">Evidence &amp; provenance</h2></div>
        <p>Every number carries its source class. Operational rates below are designed regression coverage, not council performance.</p>
      </div>
      <div className="evidence-grid">
        <article className="panel gate-chart">
          <div className="chart-heading"><div><span className="mini-label">D6 fixture</span><h3>Synthetic Gate mix</h3></div><TruthBadge value="synthetic_operational" /></div>
          <div className="stacked-bar" role="img" aria-label={`Gate pass ${mix[0][1] * 100} percent, reject ${mix[1][1] * 100} percent, escalate ${mix[2][1] * 100} percent`}>
            {mix.map(([key, value]) => <span className={`bar-${key}`} key={key} style={{ width: `${value * 100}%` }} />)}
          </div>
          <div className="legend-list">
            {mix.map(([key, value]) => (
              <div key={key}><span className={`legend-dot bar-${key}`} /><strong>{key}</strong><span>{Math.round(value * 100)}%</span></div>
            ))}
          </div>
          <p className="chart-note">The fixture intentionally over-samples non-pass paths so regressions are visible.</p>
        </article>

        <article className="panel source-register">
          <div className="chart-heading"><div><span className="mini-label">Source contract</span><h3>Data source register</h3></div></div>
          <div className="source-list">
            {data.sources.map((source) => (
              <div className="source-row" key={source.source_id}>
                <span className="source-id">{source.source_id}</span>
                <div><strong>{source.label}</strong><p>{source.use}</p><small>{source.limitation}</small></div>
                <div className="source-count"><strong>{source.row_count.toLocaleString("en-AU")}</strong><TruthBadge value={source.truth_class} /></div>
              </div>
            ))}
          </div>
        </article>
      </div>
      <div className="claim-boundary"><span>!</span><p><strong>Claim boundary</strong>{data.claim_boundary}</p></div>
    </section>
  );
}

function ArchitectureSection() {
  const items = [
    ["01", "React console", "Same-origin, no visitor payload"],
    ["02", "Public API profile", "Only predefined demo routes"],
    ["03", "Capability harness", "Identity, scope, budget, receipts"],
    ["04", "Deterministic Gate", "Versioned policy checks"],
    ["05", "Audit ledger", "Append-only SHA-256 chain"]
  ];
  return (
    <section className="architecture" id="architecture" aria-labelledby="architecture-title">
      <div className="section-heading-row">
        <div><span className="eyebrow">One bounded path</span><h2 id="architecture-title">How the demo is separated</h2></div>
        <p>The public container never loads internal review, provider-control, arbitrary diagnosis or operational endpoints.</p>
      </div>
      <div className="architecture-flow">
        {items.map(([number, title, copy], index) => (
          <div className="architecture-node" key={number}>
            <span>{number}</span><strong>{title}</strong><small>{copy}</small>
            {index < items.length - 1 && <i aria-hidden="true">→</i>}
          </div>
        ))}
      </div>
    </section>
  );
}

function App() {
  const [data, setData] = useState<Bootstrap | null>(null);
  const [selectedId, setSelectedId] = useState("");
  const [result, setResult] = useState<DemoRun | null>(null);
  const [isRunning, setIsRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    fetchBootstrap(controller.signal)
      .then((bootstrap) => {
        setData(bootstrap);
        setSelectedId(bootstrap.scenarios[0]?.scenario_id ?? "");
      })
      .catch((reason: unknown) => {
        if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : "Dashboard failed to load.");
      });
    return () => controller.abort();
  }, []);

  const selectedScenario = useMemo(
    () => data?.scenarios.find((scenario) => scenario.scenario_id === selectedId),
    [data, selectedId]
  );

  async function handleRun() {
    if (!selectedScenario || isRunning) return;
    setIsRunning(true);
    setError(null);
    try {
      setResult(await runScenario(selectedScenario.scenario_id));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Controlled path failed.");
    } finally {
      setIsRunning(false);
    }
  }

  if (!data) {
    return (
      <main className="boot-screen">
        <div className="brand-mark" aria-hidden="true"><span>R</span></div>
        <p>{error ?? "Loading assurance evidence…"}</p>
      </main>
    );
  }

  return (
    <div className="app-shell">
      <header className="site-header">
        <a className="brand" href="#top" aria-label="Rivulet LocalOps home">
          <span className="brand-mark" aria-hidden="true"><span>R</span></span>
          <span><strong>Rivulet</strong><small>LocalOps</small></span>
        </a>
        <nav aria-label="Page navigation">
          <a href="#workbench">Workbench</a>
          <a href="#evidence">Evidence</a>
          <a href="#architecture">Architecture</a>
        </nav>
        <div className="environment-chip"><span /> Public sandbox · {data.release}</div>
      </header>

      <main id="top">
        <section className="hero">
          <div className="hero-copy">
            <div className="hero-kicker"><span>Accountable automation</span><i /> <span>Local government</span></div>
            <h1>AI assistance that can<br /><em>show its working.</em></h1>
            <p>
              A public, bounded demonstration of service-request triage where capability checks happen before tools,
              policy checks happen before action, and every runtime event leaves a verifiable receipt.
            </p>
            <div className="hero-actions">
              <a className="primary-link" href="#workbench">Open workbench <span>↓</span></a>
              <div><span className="pulse-dot" /><small>Deterministic L0 agent<br />No model credential</small></div>
            </div>
          </div>
          <div className="hero-system" aria-label="System control flow">
            <div className="system-grid" />
            <div className="system-node node-case"><span>01</span><strong>Case</strong><small>Synthetic fixture</small></div>
            <div className="system-line line-one"><i /></div>
            <div className="system-node node-agent"><span>02</span><strong>Agent</strong><small>Scoped read only</small></div>
            <div className="system-line line-two"><i /></div>
            <div className="system-node node-gate"><span>03</span><strong>Gate</strong><small>Policy enforced</small></div>
            <div className="system-audit"><span>SHA-256</span><strong>Evidence retained</strong><small>Input · output · policy · receipt</small></div>
          </div>
        </section>

        <MetricGrid data={data} />

        <div className="workspace-grid">
          <ScenarioPicker
            scenarios={data.scenarios}
            selectedId={selectedId}
            isRunning={isRunning}
            onSelect={(id) => { setSelectedId(id); setResult(null); setError(null); }}
            onRun={handleRun}
          />
          <CapabilityPanel data={data} />
          <AssurancePanel result={result} isRunning={isRunning} error={error} />
        </div>

        <AnalyticsSection data={data} />
        <ArchitectureSection />
      </main>

      <footer>
        <div className="brand footer-brand"><span className="brand-mark" aria-hidden="true"><span>R</span></span><span><strong>Rivulet</strong><small>LocalOps</small></span></div>
        <p>Portfolio demonstration · Decision support only · A human remains accountable.</p>
        <span>{data.environment_note}</span>
      </footer>
    </div>
  );
}

export default App;
