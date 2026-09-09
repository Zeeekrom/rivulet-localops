import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from rivulet_localops.assets import AssetRepository  # noqa: E402
from rivulet_localops.models import DiagnoseRequest  # noqa: E402
from rivulet_localops.providers import RulesTriageProvider  # noqa: E402


def main() -> None:
    cases = json.loads((PROJECT_ROOT / "eval" / "cases.json").read_text(encoding="utf-8"))
    provider = RulesTriageProvider(AssetRepository(PROJECT_ROOT / "data" / "hobart_litter_bins.geojson"))
    category_hits = 0
    priority_hits = 0
    failures = []
    for case in cases:
        result = provider.diagnose(DiagnoseRequest(text=case["text"]))
        category_hits += result.category.code == case["category"]
        priority_hits += result.priority.code == case["priority"]
        if result.category.code != case["category"] or result.priority.code != case["priority"]:
            failures.append({
                "text": case["text"],
                "expected": [case["category"], case["priority"]],
                "actual": [result.category.code, result.priority.code],
            })

    count = len(cases)
    print(json.dumps({
        "cases": count,
        "category_accuracy": round(category_hits / count, 3),
        "priority_accuracy": round(priority_hits / count, 3),
        "failures": failures,
    }, indent=2))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
