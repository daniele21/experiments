"""Decisio CLI planning and terminal progress, without expensive model inference."""

import importlib.util
import io
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from rich.console import Console

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/decisio_runner.py"
spec = importlib.util.spec_from_file_location("decisio_runner", SCRIPT)
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def test_shared_launcher_exposes_decisio_options():
    result = subprocess.run(
        [sys.executable, str(SCRIPT.with_name("run_local_matrix.py")), "--help"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "--provider {korgis,decisio}" in result.stdout
    assert "--resume RESUME" in result.stdout
    assert "--profile" in result.stdout and "--progress" in result.stdout


@pytest.fixture
def setup(tmp_path):
    checkout = tmp_path / "decisio"
    (checkout / "src/decisio").mkdir(parents=True)
    registry = {}
    for key in runner.DEFAULT_MODELS:
        model = tmp_path / f"{key}.gguf"
        model.touch()
        registry[key] = {"path": str(model)}
    args = SimpleNamespace(
        experiments="routing",
        thinking=None,
        clean=False,
        keep_korgis=False,
        resume=None,
        output=tmp_path / "output",
        interactive=False,
        models=None,
        dataset=None,
        profile=None,
        cases=None,
        methods=None,
        device=None,
        threads=None,
        decisio_root=checkout,
        decisio_python=Path(sys.executable),
        progress=False,
    )
    return args, registry


@pytest.mark.parametrize(
    "profile,count", [("budget", 77), ("quick", 154), ("standard", 770), ("full", None)]
)
def test_public_profile_selects_semantic_and_both_models(setup, profile, count):
    args, registry = setup
    args.dataset, args.profile = "public", profile
    plan, directory, single = runner.build_plan(args, registry)
    assert plan["cases"] == count
    assert plan["methods"] == ["semantic", "json"]
    assert plan["device"] == ("metal" if sys.platform == "darwin" else "cpu")
    assert plan["models"] == runner.DEFAULT_MODELS
    command = runner.worker_command(
        plan, registry[plan["models"][0]]["path"], directory, resume=False
    )
    assert command[command.index("--dataset") + 1] == "banking77"
    assert ("--cases" in command) == (count is not None)
    assert "--events-json" in command
    assert command[command.index("--device") + 1] == plan["device"]
    assert not single and not directory.exists()


def test_invalid_later_model_fails_before_creating_output(setup):
    args, registry = setup
    registry[runner.DEFAULT_MODELS[1]]["path"] += ".missing"
    with pytest.raises(ValueError, match="GGUF not found"):
        runner.build_plan(args, registry)
    assert not args.output.exists()


def test_resume_matrix_infers_settings_and_rejects_incompatible_override(setup):
    args, registry = setup
    args.dataset = "public"
    plan, directory, _ = runner.build_plan(args, registry)
    directory.mkdir()
    (directory / "matrix.json").write_text(json.dumps(plan))
    args.resume, args.output, args.dataset = directory, None, None
    resumed, _, _ = runner.build_plan(args, registry)
    assert resumed == plan
    args.threads = 8
    with pytest.raises(ValueError, match="threads differs"):
        runner.build_plan(args, registry)


def test_resume_legacy_run_uses_single_directory(setup):
    args, registry = setup
    directory = args.output
    directory.mkdir()
    model = runner.DEFAULT_MODELS[0]
    (directory / "manifest.json").write_text(
        json.dumps(
            {
                "config": {"model": registry[model]["path"], "n_threads": 4},
                "dataset": "banking77",
                "methods": ["semantic", "json"],
                "device": "cpu",
            }
        )
    )
    (directory / "fixture.json").write_text(json.dumps({"cases": [1] * 77}))
    args.resume, args.output = directory, None
    args.device = "cpu"
    plan, resumed_directory, single = runner.build_plan(args, registry)
    assert plan["models"] == [model] and plan["cases"] == 77
    assert single and resumed_directory == directory


@pytest.mark.parametrize("live", [True, False])
def test_worker_events_render_warmup_resumed_progress_and_failure(live):
    stream = io.StringIO()
    console = Console(file=stream, force_terminal=live, width=160)
    display = runner.RunDisplay(console, "qwen-test", live)
    events = [
        {"event": "phase", "method": "semantic", "status": "Warmup semantic (77 candidates)"},
        {"event": "method_start", "method": "semantic", "total": 77, "completed": 12},
        {"event": "case_start", "case_id": "case-13", "completed": 12, "total": 77},
        {
            "event": "case",
            "case_id": "case-13",
            "completed": 13,
            "total": 77,
            "correct": False,
            "valid": False,
            "latency_ms": 10,
            "choice": None,
            "expected": "billing",
            "accuracy": 0.5,
        },
    ]
    code = (
        "\n".join(
            f"print({runner.EVENT_PREFIX + json.dumps(event)!r}, flush=True)" for event in events
        )
        + "\nraise SystemExit(3)"
    )
    assert runner.run_worker([sys.executable, "-c", code], display) == 3
    text = stream.getvalue()
    assert "Warmup semantic" in text
    assert "resumed: 12 cases" in text
    assert "invalid" in text and "case-13" in text
    assert display.progress.tasks[0].completed == 13


def test_interrupt_reaps_owned_worker(monkeypatch):
    display = runner.RunDisplay(Console(file=io.StringIO()), "test", False)

    class InterruptedStream:
        def __iter__(self):
            raise KeyboardInterrupt

        def close(self):
            pass

    process = SimpleNamespace(pid=12345, stdout=InterruptedStream(), poll=lambda: None)
    waited = []
    process.wait = lambda timeout: waited.append(timeout)
    monkeypatch.setattr(runner.subprocess, "Popen", lambda *a, **kw: process)
    signals = []
    monkeypatch.setattr(runner.os, "killpg", lambda pid, sig: signals.append((pid, sig)))
    with pytest.raises(KeyboardInterrupt):
        runner.run_worker(["unused"], display)
    assert signals == [(12345, runner.signal.SIGTERM)]
    assert waited == [5]
