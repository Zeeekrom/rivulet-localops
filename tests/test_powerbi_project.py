from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from scripts.build_powerbi_project import MODEL_DIR, build_files, canonical_csv_bytes


ROOT = Path(__file__).resolve().parents[1]


def test_powerbi_project_is_current_and_structurally_valid() -> None:
    build = subprocess.run(
        [sys.executable, "scripts/build_powerbi_project.py", "--check"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert build.returncode == 0, build.stdout + build.stderr

    validation = subprocess.run(
        [sys.executable, "scripts/validate_powerbi_project.py"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert validation.returncode == 0, validation.stdout + validation.stderr


def test_powerbi_local_state_is_excluded_but_portable_editor_state_is_generated() -> None:
    generated = set(build_files())
    assert MODEL_DIR / ".pbi" / "editorSettings.json" in generated
    assert MODEL_DIR / ".pbi" / "localSettings.json" not in generated
    assert MODEL_DIR / ".pbi" / "cache.abf" not in generated

    ignore_text = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "**/.pbi/localSettings.json" in ignore_text
    assert "**/.pbi/cache.abf" in ignore_text


def test_embedded_csv_bytes_are_platform_independent(tmp_path: Path) -> None:
    lf_csv = tmp_path / "lf.csv"
    crlf_csv = tmp_path / "crlf.csv"
    lf_csv.write_bytes(b"key,value\n1,alpha\n2,beta\n")
    crlf_csv.write_bytes(b"key,value\r\n1,alpha\r\n2,beta\r\n")

    assert canonical_csv_bytes(lf_csv) == canonical_csv_bytes(crlf_csv)
