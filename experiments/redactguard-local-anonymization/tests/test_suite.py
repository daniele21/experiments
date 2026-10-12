import json
from pathlib import Path

from redact_bench.history import append_history, load_history
from redact_bench.history_dashboard import write_history_dashboard
from redact_bench.korgis_process import resolve_korgis_repo
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
  ensure_models: true
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


def test_clean_korgis_env_strips_runner_virtualenv(monkeypatch):
    from redact_bench.korgis_process import _clean_korgis_env

    monkeypatch.setenv("VIRTUAL_ENV", "/some/other/project/.venv")
    monkeypatch.setenv("PYTHONHOME", "/custom/python/home")
    monkeypatch.setenv("SOME_OTHER_VAR", "value123")

    env = _clean_korgis_env()
    assert "VIRTUAL_ENV" not in env
    assert "PYTHONHOME" not in env
    assert env.get("SOME_OTHER_VAR") == "value123"


def test_clean_korgis_env_preserves_explicit_llama_server_bin(monkeypatch):
    from redact_bench.korgis_process import _clean_korgis_env

    monkeypatch.setenv("LOCAL_LLM_SERVER_BIN", "/custom/path/llama-server")
    env = _clean_korgis_env()
    assert env.get("LOCAL_LLM_SERVER_BIN") == "/custom/path/llama-server"


def test_resolve_suite_dataset_handles_jsonl(tmp_path: Path):
    from redact_bench.suite import _resolve_suite_dataset

    jsonl_file = tmp_path / "cases.jsonl"
    jsonl_file.write_text(
        json.dumps(
            {
                "id": "c1",
                "profile": "general",
                "text": "Hello Mario Rossi",
                "entities": [{"pii_type": "private_person", "value": "Mario Rossi"}],
                "gold_version": "challenge_v0.1",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    dataset_id = _resolve_suite_dataset(jsonl_file)
    assert dataset_id == "challenge_v0.1"


def test_resolve_suite_dataset_handles_jsonl_without_gold_version(tmp_path: Path):
    from redact_bench.suite import _resolve_suite_dataset

    dataset_dir = tmp_path / "smoke"
    dataset_dir.mkdir()
    jsonl_file = dataset_dir / "cases.jsonl"
    jsonl_file.write_text(
        json.dumps(
            {
                "id": "c1",
                "profile": "general",
                "text": "Hello Mario Rossi",
                "entities": [{"pii_type": "private_person", "value": "Mario Rossi"}],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    dataset_id = _resolve_suite_dataset(jsonl_file)
    assert dataset_id == "smoke-cases"


def test_suite_defaults_to_no_korgis_inference_cache(tmp_path: Path):
    from redact_bench.suite import load_suite_config

    cfg = tmp_path / "suite.yaml"
    cfg.write_text(
        "suite:\n"
        "  models: [example]\n"
        "  dataset: cases.jsonl\n"
        "  profiles: profiles.yaml\n"
        "  latency:\n"
        "    case_ids: [case-1]\n",
        encoding="utf-8",
    )
    assert load_suite_config(cfg, root=tmp_path).inference_cache_max_entries == 0


def test_managed_korgis_cache_disabled_verified_fail_closed(tmp_path: Path):
    import pytest

    from redact_bench.korgis_process import ManagedKorgis

    server = ManagedKorgis(
        repo=tmp_path,
        anchor_model="model-a",
        log_path=tmp_path / "model.log",
        inference_cache_max_entries=0,
    )
    server.controller.health = lambda: {"inference_cache_max_entries": 0}
    server._assert_inference_cache()

    server.controller.health = lambda: {"inference_cache_max_entries": 256}
    with pytest.raises(RuntimeError, match="Latency measurements would be invalid"):
        server._assert_inference_cache()

    server.controller.health = lambda: {"ok": True}  # Older Korgis protocol.
    with pytest.raises(RuntimeError, match="got None"):
        server._assert_inference_cache()


def test_quality_only_suite_config_requires_no_latency_cases(tmp_path: Path):
    cfg = tmp_path / "quality-only.yaml"
    cfg.write_text(
        "suite:\n"
        "  models: [qwen]\n"
        "  dataset: data/challenge/cases.jsonl\n"
        "  profiles: config/profiles.yaml\n"
        "  quality_only: true\n",
        encoding="utf-8",
    )
    config = load_suite_config(cfg, root=tmp_path)
    assert config.quality_only
    assert config.latency_case_ids == ()
    assert config.inference_cache_max_entries == 0


def test_quality_only_suite_skips_latency_and_keeps_quality_artifacts(
    tmp_path: Path, monkeypatch,
):
    from contextlib import nullcontext

    from redact_bench import suite as module
    from redact_bench.models import Case

    config_path = tmp_path / "suite.yaml"
    data_path = tmp_path / "dataset.jsonl"
    data_path.write_text(
        json.dumps({
            "id": "case-1",
            "profile": "general",
            "text": "Example text.",
            "entities": [],
            "gold_version": "qualityonly_v1",
        }) + "\n",
        encoding="utf-8",
    )
    config_path.write_text(
        "suite:\n"
        "  models: [qwen]\n"
        "  dataset: dataset.jsonl\n"
        "  profiles: profiles.yaml\n"
        "  results_dir: results\n"
        "  quality_only: true\n"
        "  ensure_models: false\n",
        encoding="utf-8",
    )
    korgis = tmp_path / "korgis"
    korgis.mkdir()

    class FakeKorgis:
        def __init__(self, **kwargs):
            assert kwargs["inference_cache_max_entries"] == 0

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

    def forbidden(*args, **kwargs):
        raise AssertionError("Quality-only suite must never run the latency path")

    monkeypatch.setattr(module, "resolve_korgis_repo", lambda *a, **kw: korgis)
    monkeypatch.setattr(module, "korgis_git_sha", lambda *a: "fake-korgis-sha")
    monkeypatch.setattr(module, "ManagedKorgis", FakeKorgis)
    monkeypatch.setattr(
        module,
        "run_compare",
        lambda **kwargs: _fake_model_run(
            Path(kwargs["results_dir"]) / "quality-one",
            kwargs["models"][0],
            1.0,
        ),
    )
    monkeypatch.setattr(module, "run_latency", forbidden)
    monkeypatch.setattr(module, "build_history_entry", forbidden)
    monkeypatch.setattr(module, "write_history_dashboard", forbidden)

    output = module.run_managed_suite(
        config_path=config_path,
        experiment_root=tmp_path,
    )
    info = json.loads((output / "suite.json").read_text(encoding="utf-8"))
    assert info["status"] == "completed"
    assert info["quality_only"] is True
    assert info["dataset_id"] == "qualityonly_v1"
    assert (output / "quality" / "metrics.json").exists()
    assert (output / "quality" / "report.html").exists()
    assert not (output / "latency").exists()
    assert info["latency"] is None
    assert info["history"] is None
    assert info["dashboard"] is None
