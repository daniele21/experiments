from io import StringIO

from redact_bench.progress import TerminalProgress


def test_terminal_progress_renders_live_case_eta():
    stream = StringIO()
    now = [0.0]
    progress = TerminalProgress(
        stream=stream,
        interactive=True,
        clock=lambda: now[0],
    )

    progress.run_started(
        run_id="run-1",
        dataset="realistic",
        cases=4,
        models=["model-a"],
        output="results/run-1",
    )
    progress.model_started(model="model-a", index=1, total=1)
    progress.warmups_started(model="model-a", total=1)
    progress.warmup_completed(model="model-a", completed=1, total=1)
    progress.cases_started(model="model-a", total=4)
    now[0] = 2.0
    progress.case_completed(
        model="model-a",
        completed=1,
        total=4,
        case_id="invoice_017",
        latency_ms=2800,
        errors=0,
    )

    output = stream.getvalue()
    assert "Dataset: realistic — 4 cases" in output
    assert "Cases 1/4" in output
    assert "25%" in output
    assert "Last: invoice_017" in output
    assert "Latency: 2.8s" in output
    assert "ETA: 00:06" in output
    assert "Errors: 0" in output


def test_non_interactive_progress_keeps_logs_compact():
    stream = StringIO()
    now = [0.0]
    progress = TerminalProgress(
        stream=stream,
        interactive=False,
        clock=lambda: now[0],
    )

    progress.run_started(
        run_id="run-1",
        dataset="realistic",
        cases=2,
        models=["model-a"],
        output="results/run-1",
    )
    progress.model_started(model="model-a", index=1, total=1)
    progress.warmups_started(model="model-a", total=1)
    progress.warmup_completed(model="model-a", completed=1, total=1)
    progress.cases_started(model="model-a", total=2)
    now[0] = 3.0
    progress.case_completed(
        model="model-a",
        completed=1,
        total=2,
        case_id="case-1",
        latency_ms=500,
        errors=1,
    )
    progress.model_completed(
        model="model-a",
        completed=2,
        total=2,
        errors=1,
    )
    progress.run_completed()

    output = stream.getvalue()
    assert "→ [1/1] model-a" in output
    assert "Warmup 1/1 ✓" in output
    assert "case-1" not in output
    assert "✓ model-a 2/2 | Errors: 1" in output
    assert "✓ Run complete" in output
