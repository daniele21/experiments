from io import StringIO

from redact_bench.progress import SuiteProgress, TerminalProgress


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


def test_suite_progress_prints_live_line_updates_and_eta_through_non_tty():
    stream = StringIO()
    now = [0.0]
    progress = SuiteProgress(
        models=2,
        quality_cases=2,
        latency_cases=1,
        latency_repeats=3,
        stream=stream,
        clock=lambda: now[0],
    )
    progress.suite_started(output="results/suites/example")
    progress.model_preparing(model="nemotron", index=1)
    now[0] = 15.0
    progress.startup_wait(15.0)
    progress.run_started(run_id="quality-1", dataset="realistic", cases=2,
                         models=["nemotron"], output="quality")
    progress.cases_started(model="nemotron", total=2)
    now[0] = 17.0
    progress.case_completed(
        model="nemotron", completed=1, total=2, case_id="lettera.txt",
        latency_ms=800, errors=0,
    )
    now[0] = 19.0
    progress.case_completed(
        model="nemotron", completed=2, total=2, case_id="contratto.pdf",
        latency_ms=900, errors=0,
    )
    progress.model_completed(model="nemotron", completed=2, total=2, errors=0)
    progress.latency_started()
    now[0] = 22.0
    progress.latency_sample("nemotron", 1, 3, "lettera.txt", 920.0)
    now[0] = 24.0
    progress.latency_sample("nemotron", 2, 3, "lettera.txt", 870.0)
    now[0] = 26.0
    progress.latency_sample("nemotron", 3, 3, "lettera.txt", 860.0)
    progress.latency_finished()
    progress.model_finished()
    output = stream.getvalue()

    assert "Model 1/2: nemotron" in output
    assert "startup in progress" in output
    assert "quality 1/2 (50%)" in output
    assert "quality 2/2 (100%)" in output
    assert "latency 1/3 (33%)" in output
    assert "latency 3/3 (100%)" in output
    assert "overall 5/10 (50%)" in output
    assert "stage ETA" in output
    assert "\\x1b" not in output
    assert "\\r" not in output


def test_suite_progress_marks_preflight_skips_explicitly():
    stream = StringIO()
    progress = SuiteProgress(
        models=1, quality_cases=2, latency_cases=1, latency_repeats=2,
        stream=stream,
    )
    progress.model_preparing(model="missing-contract-model", index=1)
    progress.model_completed(model="missing-contract-model", completed=0, total=2, errors=1)
    progress.latency_started()
    progress.latency_finished()
    progress.model_finished()
    output = stream.getvalue()
    assert "quality skipped after preflight" in output
    assert "latency preflight failed or samples skipped" in output
    assert "overall 4/4 (100%)" in output
