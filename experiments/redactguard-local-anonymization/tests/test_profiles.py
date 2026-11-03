from pathlib import Path

from redact_bench.profiles import build_system_prompt


def test_prompt_keeps_redactguard_examples_and_json_contract():
    root = Path(__file__).resolve().parents[1]
    prompt = build_system_prompt("healthcare", root / "config/profiles.yaml")
    assert "metformina 500mg" in prompt
    assert '"health_condition"' in prompt
    assert "Return ONLY valid JSON" in prompt


def test_clinical_ner_prompt_uses_specialized_biomedical_instructions():
    root = Path(__file__).resolve().parents[1]
    prompt = build_system_prompt("spaccc_clinical_ner", root / "config/profiles-medical-gold.yaml")
    assert "expert Clinical and Biomedical Named Entity Recognition" in prompt
    assert "Extract EVERY medical entity comprehensively" in prompt
    assert "Do NOT include information that is clearly public or non-personal" not in prompt
    assert "diabetes mellitus" in prompt


def test_asq_phi_prompt_includes_contrastive_examples():
    root = Path(__file__).resolve().parents[1]
    prompt = build_system_prompt("asq_phi", root / "config/profiles-medical-gold.yaml")
    assert "PII (Personally Identifiable Information) detection assistant" in prompt
    assert "BC-654321" in prompt
    assert "MRN-10293" in prompt
    assert "DO NOT classify as generic account_number" in prompt
