from pathlib import Path

from redact_bench.profiles import build_system_prompt


def test_prompt_keeps_redactguard_examples_and_json_contract():
    root = Path(__file__).resolve().parents[1]
    prompt = build_system_prompt("healthcare", root / "config/profiles.yaml")
    assert "metformina 500mg" in prompt
    assert '"health_condition"' in prompt
    assert "Return ONLY valid JSON" in prompt
