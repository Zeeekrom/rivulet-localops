"""Profile D1/D2 source snapshots and persist an inspectable quality report."""

import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from rivulet_localops.source_quality import profile_sources  # noqa: E402


def main() -> None:
    report = profile_sources(PROJECT_ROOT)
    output_path = PROJECT_ROOT / "data" / "quality" / "source_quality.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": report["status"],
        "check_counts": report["check_counts"],
        "source_summaries": report["source_summaries"],
        "output": output_path.relative_to(PROJECT_ROOT).as_posix(),
    }, indent=2))
    if report["check_counts"]["blocking"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
