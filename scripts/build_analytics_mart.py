"""Build and validate the versioned SQLite/CSV analytics mart."""

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from rivulet_localops.analytics_mart import build_analytics_mart  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "data" / "mart" / "v1",
        help="Destination for SQLite, CSV tables and build report.",
    )
    args = parser.parse_args()
    output_dir = args.output_dir if args.output_dir.is_absolute() else PROJECT_ROOT / args.output_dir
    report = build_analytics_mart(PROJECT_ROOT, output_dir)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
