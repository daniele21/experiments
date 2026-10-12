import json
from pathlib import Path

import pytest

from redact_bench.quality_probe import run_quality_probe


def _setup(tmp_path: Path) -> tuple[Path, Path]:
    (tmp_path / "config").mkdir()
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "cases.jsonl").write_text(json.dumps({
        "id": "contratto.docx", "profile": "general",
        "text": "Hello", "entities": [],
    }) + "\n", encoding="utf-8")
    config = tmp_path / "config" / "suite.yaml"
    config.write_text(
        "suite:\n"
        "  models: [nemotron]\n"
        "  dataset: data/cases.jsonl\n"
        "  profiles: config/profiles.yaml\n"
        "  latency:\n"
        "    case_ids: [contratto.docx]\n",
        encoding="utf-8",
    )
    (tmp_path / "config" / "profiles.yaml").write_text("{}", encoding="utf-8")
    korgis = tmp_path / "korgis"
    (korgis / "src" / "local_llm_server").mkdir(parents=True)
    (korgis / "pyproject.toml").write_text("[project]\nname='local-llm-server'", encoding="utf-8")
    return config, korgis


def test_probe_rejects_unknown_case_before_starting_server(tmp_path):
    config, korgis = _setup(tmp_path)
    with pytest.raises(ValueError, match="Unknown case IDs"):
        run_quality_probe(
            root=tmp_path, config_path=config,
            models=["nemotron"], case_ids=["missing.xlsx"], korgis_repo=korgis,
        )


def test_probe_runs_selected_quality_cases_without_latency(tmp_path, monkeypatch):
    config, korgis = _setup(tmp_path)
    calls = []

    class FakeManagedKorgis:
        def __init__(self, **kwargs):
            calls.append(("korgis", kwargs))
        def __enter__(self):
            return self
        def __exit__(self, *_):
            return None

    def fake_run_compare(**kwargs):
        calls.append(("compare", kwargs))
        dest = Path(kwargs["results_dir"]) / "run-1"
        dest.mkdir(parents=True)
        return dest

    monkeypatch.setattr("redact_bench.quality_probe.ManagedKorgis", FakeManagedKorgis)
    monkeypatch.setattr("redact_bench.quality_probe.run_compare", fake_run_compare)

    output = run_quality_probe(
        root=tmp_path, config_path=config, models=["nemotron"],
        case_ids=["contratto.docx"], korgis_repo=korgis, chunk_max_chars=1500,
    )
    report = json.loads((output / "probe.json").read_text())
    assert report["status"] == "completed"
    assert report["cases"] == ["contratto.docx"]
    assert report["chunk_max_chars"] == 1500
    assert report["inference_cache_max_entries"] == 0
    assert calls[0][1]["inference_cache_max_entries"] == 0
    assert calls[1][1]["case_ids"] == ["contratto.docx"]
    assert calls[1][1]["warmups"] == 0
