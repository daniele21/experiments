import json
from pathlib import Path

import pytest

from redact_bench.history import append_history, load_history
from redact_bench.history_dashboard import write_history_dashboard
from redact_bench.korgis_process import prepare_korgis_models, resolve_korgis_repo
from redact_bench.suite import load_suite_config
from redact_bench.suite_artifacts import combine_model_runs


def test_resolve_korgis_repo_explicit(tmp_path: Path):
    repo = tmp_path / "korgis"
    (repo / "src/local_llm_server").mkdir(parents=True)
    (repo / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")

    assert resolve_korgis_repo(repo) == repo.resolve()


def test_resolve_korgis_repo_finds_sibling(tmp_path: Path, monkeypatch):
    personal = tmp_path / "Personal"
    experiment = personal / "experiments" / "experiments" / "redactguard-local-anonymization"
    experiment.mkdir(parents=True)
    repo = personal / "korgis"
    (repo / "src/local_llm_server").mkdir(parents=True)
    (repo / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    monkeypatch.chdir(experiment)

    assert resolve_korgis_repo(experiment_root=experiment) == repo.resolve()


def test_load_suite_config_resolves_paths(tmp_path: Path):
    config = tmp_path / "suite.yaml"
    config.write_text(
        """
suite:
  dataset: data/realistic
  profiles: config/profiles.yaml
  results_dir: results
  korgis_base_url: http://127.0.0.1:12435/v1
  models: [a, b]
  download_missing_models: false
  quality_warmups: 1
  latency:
    case_ids: [x]
    warmups: 2
    repeats: 3
""",
        encoding="utf-8",
    )

    loaded = load_suite_config(config, root=tmp_path)
    assert loaded.models == ("a", "b")
    assert loaded.dataset == (tmp_path / "data/realistic").resolve()
    assert loaded.latency_repeats == 3
    assert loaded.korgis_base_url == "http://127.0.0.1:12435/v1"
    assert loaded.download_missing_models is False


def test_history_is_append_only_and_dashboard_uses_latest(tmp_path: Path):
    history = tmp_path / "history.jsonl"
    base = {
        "schema_version": "redactguard-suite-history-v1",
        "created_at": "2026-09-28T00:00:00Z",
        "dataset_id": "d",
        "benchmark_commit": "abc",
        "host": {},
        "runtime_strategy": "restart_per_model",
        "korgis": {"source_sha": "deadbeef"},
        "paths": {},
        "latency_case_ids": ["x"],
        "latency_repeats": 3,
        "models": {
            "m": {
                "quality": {
                    "micro_recall": 0.9,
                    "macro_recall": 0.8,
                    "micro_leakage": 0.1,
                    "macro_leakage": 0.2,
                    "micro_precision": 0.95,
                    "macro_precision": 0.9,
                    "zero_leak_documents": 0.5,
                    "valid_output_rate": 1.0,
                    "quality_p50_ms": 10,
                    "quality_p95_ms": 12,
                    "by_type": {},
                },
                "latency": {
                    "p50_ms": 11,
                    "p95_ms": 13,
                    "p99_ms": 14,
                    "valid_output_rate": 1.0,
                },
            }
        },
    }

    append_history(history, {**base, "suite_id": "s1"})
    append_history(history, {**base, "suite_id": "s2"})
    assert [entry["suite_id"] for entry in load_history(history)] == ["s1", "s2"]

    dashboard = write_history_dashboard(history, tmp_path / "dashboard.html")
    content = dashboard.read_text(encoding="utf-8")
    assert "s2" in content
    assert "Latest model comparison" in content
    assert "Run history" in content
    assert "restart_per_model" in content
    assert "deadbeef" in content


def _fake_model_run(root: Path, model: str, recall: float) -> Path:
    root.mkdir(parents=True)
    summary = {
        "pii_recall": recall,
        "precision": 1.0,
        "span_f1": recall,
        "leakage_rate": 1.0 - recall,
        "zero_leak_document_rate": recall,
        "over_redaction_rate": 0.0,
        "valid_output_rate": 1.0,
        "latency_p50_ms": 10.0,
        "latency_p95_ms": 12.0,
    }
    metrics = {
        model: {
            **summary,
            "micro": dict(summary),
            "macro": {
                "pii_recall": recall,
                "precision": 1.0,
                "span_f1": recall,
                "leakage_rate": 1.0 - recall,
                "zero_leak_document_rate": recall,
                "over_redaction_rate": 0.0,
                "valid_output_rate": 1.0,
            },
            "by_type": {},
            "by_document": {},
            "dataset_balance": {},
            "failure_analysis": [],
        }
    }
    (root / "metrics.json").write_text(json.dumps(metrics), encoding="utf-8")
    (root / "rows.json").write_text("[]", encoding="utf-8")
    (root / "failures.json").write_text(json.dumps({model: []}), encoding="utf-8")
    (root / "manifest.json").write_text(
        json.dumps(
            {
                "run_id": model,
                "created_at": "2026-09-28T00:00:00Z",
                "models": [model],
                "korgis": {"runtime_identity": {model: {"model": model}}},
            }
        ),
        encoding="utf-8",
    )
    (root / f"{model}.jsonl").write_text("", encoding="utf-8")
    return root


def test_combine_model_runs_builds_one_comparison(tmp_path: Path):
    a = _fake_model_run(tmp_path / "a", "a", 1.0)
    b = _fake_model_run(tmp_path / "b", "b", 0.5)

    output = combine_model_runs(
        [a, b],
        output=tmp_path / "combined",
        suite_id="suite-1",
        kind="quality",
    )

    metrics = json.loads((output / "metrics.json").read_text(encoding="utf-8"))
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    assert list(metrics) == ["a", "b"]
    assert manifest["models"] == ["a", "b"]
    assert manifest["runtime_strategy"] == "restart_per_model"
    assert (output / "report.html").exists()



def test_prepare_models_never_downloads_without_opt_in(monkeypatch, tmp_path: Path):
    inventory = {
        "a": {"key": "a", "downloaded": True, "path": "/models/a"},
        "b": {"key": "b", "downloaded": False, "path": "/models/b"},
    }
    calls = []

    monkeypatch.setattr(
        "redact_bench.korgis_process.inspect_korgis_models",
        lambda repo, models: inventory,
    )
    monkeypatch.setattr(
        "redact_bench.korgis_process.run_korgis_cli",
        lambda repo, *args, **kwargs: calls.append(args),
    )

    with pytest.raises(FileNotFoundError, match="does not download models by default"):
        prepare_korgis_models(tmp_path, ["a", "b"], download_missing=False)

    assert calls == []


def test_prepare_models_downloads_only_missing_when_explicit(monkeypatch, tmp_path: Path):
    state = {"b_downloaded": False}
    calls = []

    def inspect(repo, models):
        return {
            "a": {"key": "a", "downloaded": True, "path": "/models/a"},
            "b": {
                "key": "b",
                "downloaded": state["b_downloaded"],
                "path": "/models/b",
            },
        }

    def run(repo, *args, **kwargs):
        calls.append(args)
        if args == ("download", "b"):
            state["b_downloaded"] = True

    monkeypatch.setattr(
        "redact_bench.korgis_process.inspect_korgis_models",
        inspect,
    )
    monkeypatch.setattr(
        "redact_bench.korgis_process.run_korgis_cli",
        run,
    )

    inventory = prepare_korgis_models(
        tmp_path,
        ["a", "b"],
        download_missing=True,
    )

    assert calls == [("download", "b")]
    assert inventory["a"]["downloaded"] is True
    assert inventory["b"]["downloaded"] is True
