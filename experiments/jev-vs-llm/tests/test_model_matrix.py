from jev_bench.cli import DEFAULT_OPENAI_MODELS, _model_matrix


def test_default_model_matrix_contains_three_gpt_tiers(monkeypatch):
    monkeypatch.delenv("OPENAI_MODELS", raising=False)
    assert _model_matrix() == DEFAULT_OPENAI_MODELS
    assert DEFAULT_OPENAI_MODELS == [
        "gpt-5.6-luna",
        "gpt-5.6-terra",
        "gpt-5.6-sol",
    ]


def test_model_matrix_deduplicates_preserving_order():
    assert _model_matrix("gpt-5.6-sol,gpt-5.6-luna,gpt-5.6-sol") == [
        "gpt-5.6-sol",
        "gpt-5.6-luna",
    ]
