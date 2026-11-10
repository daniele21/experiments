from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "scripts" / "run_mac_pilot.sh"


def test_owned_benchmark_script_has_valid_bash_syntax() -> None:
    assert SCRIPT.is_file()
    if shutil.which("bash") is None:
        pytest.skip("Bash is not available on this test platform")
    checked = subprocess.run(
        ["bash", "-n", str(SCRIPT)],
        text=True,
        capture_output=True,
        check=False,
    )
    assert checked.returncode == 0, checked.stderr


def test_mac_benchmark_logic_lives_in_experiments() -> None:
    source = SCRIPT.read_text()
    assert 'EXPERIMENTS_ROOT="$(cd "$(dirname' in source
    assert 'uv run --frozen python scripts/run_benchmark.py' in source
    assert '--profile "$BENCHMARK_PROFILE"' in source
    assert 'canary) EXPECTED_IMAGES=1' in source
    assert 'pilot) EXPECTED_IMAGES=4' in source
    assert 'BENCHMARK_MODE:-preflight' in source
    assert '--no-download' in source
    assert 'BENCHMARK_OUTPUT_DIR' in source
    assert "evidence.csv" in source
    assert "summary.json" in source
    assert "OPENAI_API_KEY=" in source
    assert "GEMINI_API_KEY=" in source
    assert 'KORGIS_SOURCE_SHA' in source
    assert 'EXPERIMENTS_SOURCE_SHA' in source
