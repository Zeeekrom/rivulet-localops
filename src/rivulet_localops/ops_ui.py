from __future__ import annotations


def operations_support_html() -> str:
    return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Rivulet Operations &amp; Support</title>
  <style>
    :root{font-family:Inter,Segoe UI,sans-serif;color:#17212b;background:#eef3f6}body{margin:0}
    main{max-width:1120px;margin:auto;padding:28px}header{display:flex;justify-content:space-between;align-items:end;gap:20px}
    h1{margin:0;font-size:2rem}.muted{color:#5d6c79}.badge{padding:7px 12px;border-radius:999px;font-weight:700}
    .healthy{background:#d8f3e6;color:#12633f}.degraded{background:#fff0c2;color:#795a00}.unavailable{background:#ffd9dc;color:#8a1c27}
    .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:14px;margin:22px 0}
    section{background:white;border:1px solid #d7e0e5;border-radius:12px;padding:18px;box-shadow:0 3px 12px #18303f0d}
    h2{font-size:1rem;margin:0 0 12px}dl{display:grid;grid-template-columns:1fr auto;gap:8px;margin:0}dt{color:#5d6c79}dd{margin:0;font-weight:650}
    table{width:100%;border-collapse:collapse;font-size:.9rem}th,td{text-align:left;padding:9px;border-bottom:1px solid #e5ebef}
    a,button{color:#075e75}button{border:1px solid #aac4ce;background:#f6fbfc;border-radius:8px;padding:9px 12px;cursor:pointer}
    code{font-size:.82rem}.wide{grid-column:1/-1}ul{padding-left:20px}.error{color:#8a1c27}
  </style>
</head>
<body><main>
  <header><div><div class="muted">Internal application profile</div><h1>Operations &amp; Support</h1></div><span id="overall" class="badge">Loading…</span></header>
  <div class="grid">
    <section><h2>Release</h2><dl><dt>Application</dt><dd id="version">—</dd><dt>Release</dt><dd id="release">—</dd><dt>Last deployment</dt><dd id="deployed">—</dd><dt>Revision</dt><dd id="revision">—</dd></dl></section>
    <section><h2>Recovery posture</h2><dl><dt>Ledger integrity</dt><dd id="integrity">—</dd><dt>Rollback</dt><dd>Documented + smoke-gated</dd><dt>Support bundle</dt><dd><button id="bundle">Download JSON</button></dd></dl></section>
    <section class="wide"><h2>Component health</h2><table><thead><tr><th>Component</th><th>Status</th><th>Summary</th></tr></thead><tbody id="components"></tbody></table></section>
    <section><h2>Recent operational incidents</h2><ul id="incidents"></ul></section>
    <section><h2>Runbook entry points</h2><ul><li><a href="/ops/v1/runbooks">Runbook index (JSON)</a></li><li><a href="/ops/v1/ledger/integrity">Ledger integrity endpoint</a></li><li><a href="/ops/v1/operations/logs">Redacted operational logs</a></li></ul></section>
  </div>
  <p id="error" class="error"></p>
</main><script>
const text=(id,value)=>document.getElementById(id).textContent=value??'not recorded';
async function load(){try{
 const [healthResponse,bundleResponse]=await Promise.all([fetch('/ops/v1/health'),fetch('/ops/v1/support/bundle')]);
 const health=await healthResponse.json(), bundle=await bundleResponse.json();
 const overall=document.getElementById('overall');overall.textContent=health.status;overall.className='badge '+health.status;
 text('version',health.application_version);text('release',health.release);text('deployed',bundle.recent_deployment.deployed_at);text('revision',bundle.recent_deployment.revision);
 text('integrity',bundle.ledger_integrity.ok?'valid':'FAIL CLOSED');
 document.getElementById('components').innerHTML=health.components.map(c=>`<tr><td><code>${c.component}</code></td><td><span class="badge ${c.status}">${c.status}</span></td><td>${c.summary}</td></tr>`).join('');
 document.getElementById('incidents').innerHTML=bundle.recent_incidents.map(i=>`<li><strong>${i.incident_id}</strong> — ${i.title} (${i.status})</li>`).join('');
 document.getElementById('bundle').onclick=()=>{const blob=new Blob([JSON.stringify(bundle,null,2)],{type:'application/json'});const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download=`rivulet-support-${health.release}.json`;a.click();URL.revokeObjectURL(a.href)};
 }catch(error){text('error','Support data could not be loaded. Check the API and application logs.')}}load();
</script></body></html>"""
