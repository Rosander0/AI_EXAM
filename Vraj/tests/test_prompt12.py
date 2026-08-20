"""Integration and final verification tests for SANKET Prompt 12."""

from pathlib import Path
import pytest


def test_final_artifacts_exist():
    """Verify all final deliverables exist and are populated."""
    assert Path("FIGURES.md").is_file()
    assert Path("README.md").is_file()
    assert Path("run_demo.sh").is_file()
    assert Path("run_demo.ps1").is_file()
    assert Path("config.yaml").is_file()
    assert Path("DATA_CONTRACT.md").is_file()


def test_source_code_terminology_invariants():
    """
    Invariant Check: The word 'cheating' must never appear in any source code,
    UI template, or report generator.
    """
    repo_root = Path(".")
    py_files = list(repo_root.glob("sanket/**/*.py")) + list(repo_root.glob("server/**/*.py")) + list(repo_root.glob("web/**/*.js")) + list(repo_root.glob("web/**/*.html"))

    for p in py_files:
        content = p.read_text(encoding="utf-8").lower()
        assert "cheating" not in content, f"Forbidden word 'cheating' found in {p}"
