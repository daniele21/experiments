import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

from redact_bench import cloud_suite
from redact_bench.cli import app
from redact_bench.cloud_provider import OpenAICloudRedactProvider
from redact_bench.datasets import load_dataset


ROOT = Path(__file__).resolve().parents[1]


def test_only_frozen_synthetic_datasets_accepted():
    for dataset, expected in (("healthcare", 48), ("ambiguous", 48), ("challenge", 46)):
        p = cloud_suite.prepare_cloud_reference(
            experiment_root=ROOT, dataset=dataset, model="gpt-6-luna", max_cases=None
        )
        assert len(p["cases"]) == expected
        assert p["scope"] == "full"
        assert p["dataset_id"]
        assert all(c.human_reviewed is False for c in p["cases"])
    with pytest.raises(ValueError, match="only accepts bundled synthetic"):
        cloud_suite.prepare_cloud_reference(
            experiment_root=ROOT, dataset="realistic", model="gpt-6-luna", max_cases=None
        )
    with pytest.raises(ValueError):
        cloud_suite.prepare_cloud_reference(
            experiment_root=ROOT, dataset="../../private", model="gpt-6-luna", max_cases=None
        )


def test_explicit_consent_is_required_before_network_or_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(ValueError, match="confirm-cloud"):
        cloud_suite.run_cloud_reference(
            experiment_root=ROOT, dataset="healthcare", model="gpt-6-luna"
        )
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        cloud_suite.run_cloud_reference(
            experiment_root=ROOT, dataset="ambiguous", model="gpt-6-luna",
            confirm_cloud=True,
        )


def test_check_only_requires_no_key_and_sends_no_request(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    result = CliRunner().invoke(
        app,
        ["cloud-reference", "--dataset", "healthcare", "--check-only", "--max-cases", "4"],
    )
    assert result.exit_code == 0, result.output
    assert "4/48 synthetic cases" in result.output
    assert "No network requests" in result.output


def test_cloud_provider_is_same_prompt_and_postprocessing_but_no_korgis_fields(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-not-an-actual-secret")
    p = OpenAICloudRedactProvider(
        "gpt-6-luna", str(ROOT / "config/profiles.yaml"), max_output_tokens=2048
    )
    case = load_dataset(ROOT / "data/healthcare/cases.jsonl")[0]
    segment = SimpleNamespace(text=case.text)
    body = p._completion_kwargs(case, segment)
    assert body["model"] == "gpt-6-luna"
    assert body["messages"][1]["content"] == case.text
    assert "pii_fields" in body["messages"][0]["content"]
    assert body["response_format"] == {"type": "json_object"}
    assert body["max_completion_tokens"] == 2048
    assert body["reasoning_effort"] == "none"
    assert body["store"] is False
    assert "extra_body" not in body and body["temperature"] == 0
    assert "max_tokens" not in body
    assert "test-not-an-actual-secret" not in repr(p.execution_settings)


def test_smoke_selection_is_versioned_but_not_full_dataset():
    x = cloud_suite.prepare_cloud_reference(
        experiment_root=ROOT, dataset="ambiguous", model="gpt-6-luna", max_cases=3
    )
    assert x["scope"] == "smoke"
    assert len(x["cases"]) == 3


def test_cloud_runner_writes_discoverable_quality_suite_without_korgis(tmp_path, monkeypatch):
    source_root = ROOT
    monkeypatch.setenv("OPENAI_API_KEY", "not-a-real-key")
    # Isolate all result artifacts: only the input files are read from source.
    fake_root = tmp_path / "experiment"
    (fake_root / "data" / "ambiguous").mkdir(parents=True)
    (fake_root / "config").mkdir()
    (fake_root / "data" / "ambiguous" / "cases.jsonl").write_bytes(
        (source_root / "data/ambiguous/cases.jsonl").read_bytes()
    )
    (fake_root / "config" / "profiles.yaml").write_bytes(
        (source_root / "config/profiles.yaml").read_bytes()
    )

    called = []

    def fake_compare(**kwargs):
        assert kwargs["backend"] == "openai_api"
        assert kwargs["warmups"] == 0
        assert kwargs["preflight"] is True
        assert kwargs["models"] == ["gpt-6-luna"]
        assert len(kwargs["case_ids"]) == 2
        called.append(kwargs)
        out = Path(kwargs["results_dir"]) / "run"
        out.mkdir(parents=True)
        (out / "manifest.json").write_text(json.dumps({
            "models": ["gpt-6-luna"], "evaluation_schema": "redactguard-evaluation-v3"
        }))
        (out / "metrics.json").write_text('{"gpt-6-luna": {}}')
        (out / "gpt-6-luna.jsonl").write_text(json.dumps({
            "result": {"input_tokens": 200, "output_tokens": 40}
        }) + "\n")
        return out

    monkeypatch.setattr(cloud_suite, "run_compare", fake_compare)
    result = cloud_suite.run_cloud_reference(
        experiment_root=fake_root, dataset="ambiguous", max_cases=2,
        model="gpt-6-luna", confirm_cloud=True,
    )
    status = json.loads((result / "suite.json").read_text())
    assert status["status"] == "completed"
    assert status["benchmark_scope"] == "smoke"
    assert status["backend"] == "openai_api"
    assert status["usage_estimate"]["input_tokens_observed"] == 200
    assert (result / "quality" / "manifest.json").exists()
    assert called
