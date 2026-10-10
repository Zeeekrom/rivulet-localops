import { useEffect, useMemo, useState } from "react";
import { fetchBootstrap, runScenario } from "./api";
import type { Bootstrap, DemoRun, Outcome, Scenario, TruthClass } from "./types";

const truthLabels: Record<TruthClass, string> = {
  real_public_reference: "Real public data",
  synthetic_operational: "Synthetic test data",
  synthetic_case: "Synthetic case",
  runtime_observation: "Runtime observation"
};

const outcomeLabels: Record<Outcome, string> = {
  pass: "Passed the policy check",
  reject: "Blocked by the policy check",
  escalate: "Sent to a person",
  deny: "Stopped: the agent was not allowed to do this",
  failed: "The run failed"
};

const expectedLabels: Record<Exclude<Outcome, "failed">, string> = {
  pass: "passes",
  reject: "is blocked",
  escalate: "goes to a person",
  deny: "is stopped"
};

type GateKey = "pass" | "escalate" | "reject";
const gateOrder: GateKey[] = ["pass", "escalate", "reject"];
const gateLabels: Record<GateKey, string> = {
  pass: "Passed",
  escalate: "Sent to a person",
  reject: "Blocked"
};

function shortHash(hash: string | null): string {
  if (!hash) return "Not produced";
  return `${hash.slice(0, 10)}…${hash.slice(-8)}`;
}

function TruthTag({ value }: { value: TruthClass }) {
  return <span className={`truth truth-${value}`}>{truthLabels[value]}</span>;
}

function Overview({ data }: { data: Bootstrap }) {
  return (
    <div className="kpis" aria-label="Summary figures">
      {data.metrics.map((metric) => (
        <article className="card kpi" key={metric.metric_id}>
          <div className="kpi-label">{metric.label}</div>
          <div className="kpi-value">{metric.display_value}</div>
          <p className="kpi-context">{metric.context}</p>
          <TruthTag value={metric.truth_class} />
        </article>
      ))}
    </div>
  );
}

function Flow() {
  const steps = [
    ["Request received", "A prepared synthetic case. Visitors cannot type their own."],
    ["Facts gathered", "A read-only agent reads the case and looks up public assets, within a fixed allowance."],
    ["Checked against policy", "A versioned policy decides: pass, block, or send to a person."],
    ["Written to the record", "Each step is added to a tamper-evident chain of hashes."],
    ["A person decides", "Nothing is final until a named person accepts or changes it."]
  ];
  return (
    <section className="card" aria-labelledby="flow-title">
      <h2 id="flow-title">What happens to every request</h2>
      <ol className="flow">
        {steps.map(([title, copy], index) => (
          <li className="step" key={title}>
            <span className="step-number">{index + 1}</span>
            <strong>{title}</strong>
            <p>{copy}</p>
          </li>
        ))}
      </ol>
    </section>
  );
}

function GateMix({ data }: { data: Bootstrap }) {
  const label = gateOrder.map((key) => `${gateLabels[key]} ${Math.round(data.gate_mix[key] * 100)} percent`).join(", ");
  return (
    <article className="card" aria-labelledby="mix-title">
      <div className="card-head">
        <h2 id="mix-title">Result of the policy check</h2>
        <TruthTag value="synthetic_operational" />
      </div>
      <div className="stack" role="img" aria-label={label}>
        {gateOrder.map((key) => (
          <span className={`seg seg-${key}`} key={key} style={{ flexGrow: data.gate_mix[key] }} title={`${gateLabels[key]}: ${Math.round(data.gate_mix[key] * 100)}%`} />
        ))}
      </div>
      <ul className="legend">
        {gateOrder.map((key) => (
          <li key={key}>
            <span className={`swatch seg-${key}`} />
            <span className="legend-name">{gateLabels[key]}</span>
            <strong>{Math.round(data.gate_mix[key] * 100)}%</strong>
          </li>
        ))}
      </ul>
      <p className="note">A fixed test set. It contains extra blocked and escalated cases on purpose, so these shares are not council performance.</p>
    </article>
  );
}

function Sources({ data }: { data: Bootstrap }) {
  return (
    <article className="card" aria-labelledby="sources-title">
      <div className="card-head"><h2 id="sources-title">Where the data comes from</h2></div>
      <ul className="sources">
        {data.sources.map((source) => (
          <li key={source.source_id}>
            <div>
              <strong>{source.label}</strong>
              <p>{source.use}</p>
              <p className="muted">{source.limitation}</p>
            </div>
            <div className="source-side">
              <strong>{source.row_count.toLocaleString("en-AU")}</strong>
              <TruthTag value={source.truth_class} />
            </div>
          </li>
        ))}
      </ul>
    </article>
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
  return (
    <div className="card picker">
      <h3>1. Choose a prepared request</h3>
      <p className="muted">These five cases are stored on the server. No text, files or personal details are accepted from visitors.</p>
      <div className="options" role="radiogroup" aria-label="Prepared synthetic requests">
        {scenarios.map((scenario) => (
          <button
            type="button"
            role="radio"
            aria-checked={scenario.scenario_id === selectedId}
            className={`option ${scenario.scenario_id === selectedId ? "is-selected" : ""}`}
            key={scenario.scenario_id}
            onClick={() => onSelect(scenario.scenario_id)}
          >
            <span className={`dot dot-${scenario.expected_outcome}`} aria-hidden="true" />
            <span className="option-text">
              <strong>{scenario.title}</strong>
              <small>{scenario.description}</small>
            </span>
            <span className="expected">Expected: {expectedLabels[scenario.expected_outcome]}</span>
          </button>
        ))}
      </div>
      <button className="run" type="button" disabled={isRunning} onClick={onRun}>
        {isRunning ? "Running…" : "Run this request"}
      </button>
    </div>
  );
}

function Result({ result }: { result: DemoRun }) {
  const rules = result.gate?.rule_results ?? [];
  const decisive = rules.filter((rule) => rule.outcome === "fail");
  const denied = result.audit.tool_receipts.filter((receipt) => receipt.decision === "deny");
  return (
    <div className="result">
      <div className={`verdict verdict-${result.observed_outcome}`}>
        <span className={`dot dot-${result.observed_outcome}`} aria-hidden="true" />
        <div>
          <strong>{outcomeLabels[result.observed_outcome]}</strong>
          <p>{result.scenario.learning_point}</p>
        </div>
      </div>

      {result.diagnosis ? (
        <dl className="facts">
          <div><dt>Type</dt><dd>{result.diagnosis.category.label}</dd></div>
          <div><dt>Priority</dt><dd>{result.diagnosis.priority.code} · {result.diagnosis.priority.label}</dd></div>
          <div><dt>Confidence</dt><dd>{Math.round(result.diagnosis.category.confidence * 100)}%</dd></div>
          <div><dt>Nearest public bin</dt><dd>{result.diagnosis.asset_match ? `${result.diagnosis.asset_match.distance_metres.toFixed(1)} m away` : "No location given"}</dd></div>
        </dl>
      ) : (
        <p className="muted">The request was not sorted, because the agent was stopped before it could run.</p>
      )}

      {decisive.length > 0 && (
        <div className="why">
          <h4>Why</h4>
          <ul>{decisive.map((rule) => <li key={rule.rule_id}>{rule.message}</li>)}</ul>
        </div>
      )}
      {denied.length > 0 && (
        <div className="why">
          <h4>Why</h4>
          <ul>{denied.map((receipt, index) => <li key={`${receipt.tool_name}-${index}`}>{receipt.reason}</li>)}</ul>
        </div>
      )}

      <p className="status-line">
        <span className="dot dot-pass" aria-hidden="true" />
        Recorded. The chain of {result.ledger_event_count} runtime event{result.ledger_event_count === 1 ? "" : "s"} is {result.ledger_integrity_ok ? "intact" : "not intact"}. A person's decision is still {result.audit.human_decision}.
      </p>

      {rules.length > 0 && (
        <details>
          <summary>All {rules.length} policy checks</summary>
          <table className="rules">
            <thead><tr><th>Rule</th><th>Result</th><th>Reason</th></tr></thead>
            <tbody>
              {rules.map((rule) => (
                <tr key={rule.rule_id}>
                  <td><code>{rule.rule_id}</code></td>
                  <td className={`rule-${rule.outcome}`}>{rule.outcome.replace("_", " ")}</td>
                  <td>{rule.message}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </details>
      )}
      <details>
        <summary>Agent receipts and record hashes</summary>
        <table className="rules">
          <thead><tr><th>Tool</th><th>Resource</th><th>Decision</th></tr></thead>
          <tbody>
            {result.audit.tool_receipts.map((receipt, index) => (
              <tr key={`${receipt.tool_name}-${index}`}>
                <td><code>{receipt.tool_name}</code></td>
                <td>{receipt.resource} · {receipt.data_class}</td>
                <td className={receipt.decision === "allow" ? "rule-pass" : "rule-fail"}>{receipt.executed ? "executed" : receipt.decision}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <dl className="hashes">
          <div><dt>Input hash</dt><dd><code>{shortHash(result.audit.input_hash)}</code></dd></div>
          <div><dt>Output hash</dt><dd><code>{shortHash(result.audit.output_hash)}</code></dd></div>
          <div><dt>Record entry</dt><dd><code>{shortHash(result.audit.event_hash)}</code></dd></div>
          <div><dt>Raw input stored</dt><dd>{result.audit.raw_input_stored ? "yes" : "no"}</dd></div>
          <div><dt>Time taken</dt><dd>{result.audit.latency_ms.toFixed(1)} ms</dd></div>
        </dl>
      </details>
    </div>
  );
}

function ResultPanel({ result, isRunning, error }: { result: DemoRun | null; isRunning: boolean; error: string | null }) {
  return (
    <div className="card" aria-live="polite">
      <h3>2. See what the system did</h3>
      {isRunning && <p className="muted">Checking what the agent may do, then checking the policy…</p>}
      {!isRunning && error && <p className="error"><strong>The run is unavailable.</strong> {error}</p>}
      {!isRunning && !error && (result ? <Result result={result} /> : <p className="muted">Choose a request and run it. The outcome, the reason and the record entry will appear here.</p>)}
    </div>
  );
}

function AgentLimits({ data }: { data: Bootstrap }) {
  const capability = data.capability;
  return (
    <section className="card" aria-labelledby="limits-title">
      <div className="card-head"><h2 id="limits-title">What the automated agent may do</h2></div>
      <div className="limits">
        <div>
          <h4>Allowed</h4>
          <ul className="tokens">{capability.allowed_tools.map((tool) => <li className="allow" key={tool}><code>{tool}</code></li>)}</ul>
        </div>
        <div>
          <h4>Always refused</h4>
          <ul className="tokens">{capability.explicitly_denied_tools.slice(0, 4).map((tool) => <li className="deny" key={tool}><code>{tool}</code></li>)}</ul>
        </div>
        <dl className="limit-facts">
          <div><dt>Agent</dt><dd>{capability.agent_id} · {capability.automation_level.replaceAll("_", " ")}</dd></div>
          <div><dt>Allowance</dt><dd>{capability.max_tool_calls} tool calls, valid for {capability.grant_ttl_seconds} seconds</dd></div>
          <div><dt>Model credential</dt><dd>{capability.credential_mode}</dd></div>
          <div><dt>Owner</dt><dd>{capability.identity_owner}</dd></div>
        </dl>
      </div>
      <p className="note">Anything not on the allowed list is refused. The agent cannot submit a decision.</p>
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
        if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : "The overview failed to load.");
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
      setError(reason instanceof Error ? reason.message : "The run failed.");
    } finally {
      setIsRunning(false);
    }
  }

  if (!data) {
    return <main className="boot"><p>{error ?? "Loading the overview…"}</p></main>;
  }

  return (
    <div className="shell">
      <header className="bar">
        <a className="name" href="#top">Rivulet LocalOps</a>
        <nav aria-label="Page navigation">
          <a href="#top">Overview</a>
          <a href="#try">Try a request</a>
          <a href="#controls">Controls and data</a>
        </nav>
        <span className="env">Public demo · {data.release} · synthetic requests only</span>
      </header>

      <main id="top" className="page">
        <h1>Service requests overview</h1>
        <p className="sub">Every request is checked against an approved policy, recorded, and left for a person to decide.</p>

        <Overview data={data} />
        <Flow />

        <div className="two">
          <GateMix data={data} />
          <Sources data={data} />
        </div>

        <section id="try" aria-labelledby="try-title">
          <h2 className="section-title" id="try-title">Try a request</h2>
          <div className="two try">
            <ScenarioPicker
              scenarios={data.scenarios}
              selectedId={selectedId}
              isRunning={isRunning}
              onSelect={(id) => { setSelectedId(id); setResult(null); setError(null); }}
              onRun={handleRun}
            />
            <ResultPanel result={result} isRunning={isRunning} error={error} />
          </div>
        </section>

        <section id="controls">
          <AgentLimits data={data} />
          <p className="boundary"><strong>What these figures can and cannot show.</strong> {data.claim_boundary}</p>
        </section>
      </main>

      <footer className="foot">
        <span>Portfolio demonstration. Decision support only. A person remains accountable.</span>
        <span>{data.environment_note}</span>
      </footer>
    </div>
  );
}

export default App;
