$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $projectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $python)) {
    throw "Missing .venv. Run: py -3.12 -m venv .venv"
}

Push-Location $projectRoot
try {
    & $python scripts\profile_sources.py
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    & $python scripts\generate_synthetic_ledger.py
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    & $python scripts\build_analytics_mart.py
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    & $python scripts\build_powerbi_project.py --check
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    & $python scripts\validate_powerbi_project.py
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    & $python -m pytest -q
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    & $python scripts\run_eval.py
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    & $python scripts\run_agent_capability_review.py
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
finally {
    Pop-Location
}
