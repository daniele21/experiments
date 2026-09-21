"""runner_orchestrator.py.

Modular experiment runner that iterates across local models sequentially.
For each selected model:
  1. Calls Korgis to activate the model.
  2. Runs the designated benchmark experiment(s) with rich live progress bars.
  3. Displays per-case evaluation details (accuracy, validity, latency, outcome).
  4. Appends raw results and logs performance metrics.
  5. Unloads the model from RAM/VRAM.
  6. Generates the aggregated HTML report across all evaluated models.
"""

from __future__ import annotations

import logging
import os
import time
import uuid
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pandas as pd
from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)

from jev_bench.benchmark_data import (
    DEFAULT_CACHE,
    balanced_banking77_cases,
    banking77_question,
    calibration_public_cases,
    prepare_public_data,
)
from jev_bench.cli import (
    PUBLIC_PROFILES,
    _record_manifest,
    _tag_run,
    append_results,
    build_report,
)
from jev_bench.datasets import (
    calibration_cases,
    expense_cases,
    expense_questions,
    routing_cases,
    routing_questions,
    support_cases,
    support_questions,
)
from jev_bench.models import BenchmarkCase, QuestionSpec
from jev_bench.progress import run_cases_with_progress
from jev_bench.providers.base import DecisionProvider
from jev_bench.providers.jev import JevProvider
from jev_bench.providers.korgis import KorgisProvider
from jev_bench.runner import (
    _expense_action,
    _rows_for_case,
    _support_action,
    run_scaling,
    run_workflow,
)

from .korgis_manager import KorgisManager

logger = logging.getLogger(__name__)
console = Console()


class ExperimentOrchestrator:
    """Orchestrates benchmark experiments across a sequence of local models."""

    def __init__(
        self,
        korgis_manager: KorgisManager,
        output_csv: Path = Path("results/raw/local_results.csv"),
        report_html: Path = Path("results/local_report.html"),
        cache_dir: Path = DEFAULT_CACHE,
        max_output_tokens: int = 512,
        seed: int = 42,
        enable_thinking: bool = False,
    ) -> None:
        self.korgis = korgis_manager
        self.output_csv = output_csv
        self.report_html = report_html
        self.cache_dir = cache_dir
        self.max_output_tokens = max_output_tokens
        self.seed = seed
        self.enable_thinking = enable_thinking

    def run_matrix(
        self,
        models: list[str],
        experiments: list[str],
        dataset: str = "smoke",
        profile: str = "budget",
    ) -> dict[str, Any]:
        """Run the list of experiments across all chosen models, one at a time."""
        if not models:
            raise ValueError("No models specified for execution.")
        if not experiments:
            raise ValueError("No experiments specified for execution.")

        eff_tokens = self.max_output_tokens
        if self.enable_thinking and eff_tokens <= 512:
            eff_tokens = 2048
        os.environ["KORGIS_MAX_OUTPUT_TOKENS"] = str(eff_tokens)
        os.environ["KORGIS_BASE_URL"] = self.korgis.base_url
        os.environ["KORGIS_ENABLE_THINKING"] = "true" if self.enable_thinking else "false"

        group_id = str(uuid.uuid4())
        total_models = len(models)
        summary_records: list[dict[str, Any]] = []
        all_frames: list[pd.DataFrame] = []

        console.print(f"\n[bold magenta]🚀 Starting Benchmark Group:[/] [cyan]{group_id}[/]")
        console.print(f"   • Models ({total_models}) : [bold]{', '.join(models)}[/]")
        console.print(f"   • Experiments     : [bold]{', '.join(experiments)}[/]")
        console.print(f"   • Dataset Tier    : [bold]{dataset}[/] (profile: [yellow]{profile}[/])\n")

        # Prepare public datasets if needed
        if dataset == "public":
            console.print("[dim]Checking public dataset cache (Banking77 / CLINC150)...[/dim]")
            prepare_public_data(self.cache_dir)

        for idx, model in enumerate(models, start=1):
            console.print("\n" + "━" * 70)
            console.print(f"[bold white on blue] MODEL [{idx}/{total_models}]: {model} [/]")
            console.print("━" * 70)

            is_jev = model.strip().lower() in {"jev", "jev-latest"} or model.startswith("jev-")
            if is_jev:
                jev_m = os.getenv("JEV_MODEL", "jev-1.13.0") if model == "jev" else model
                provider: DecisionProvider = JevProvider(model=jev_m)
            else:
                # 1. Activate model in Korgis
                try:
                    self.korgis.activate_model(model)
                except Exception as exc:
                    logger.error("Failed to activate model '%s': %s", model, exc)
                    summary_records.append({
                        "model": model,
                        "status": "ERROR_ACTIVATION",
                        "error": str(exc),
                    })
                    continue

                provider = KorgisProvider(
                    model=model,
                    base_url=self.korgis.base_url,
                    seed=self.seed,
                    enable_thinking=self.enable_thinking,
                )

            # 2. Run experiments for this model
            for exp_name in experiments:
                t0 = time.perf_counter()
                try:
                    frame = self._run_single_experiment(
                        exp_name=exp_name,
                        provider=provider,
                        model_name=model,
                        dataset=dataset,
                        profile=profile,
                    )
                    elapsed = time.perf_counter() - t0

                    tagged_frame = _tag_run(frame, group_id, f"{dataset}-{exp_name}")
                    tagged_frame["thinking_mode"] = "on" if self.enable_thinking else "off"
                    tagged_frame["dataset_type"] = dataset
                    append_results(tagged_frame, self.output_csv)
                    all_frames.append(tagged_frame)

                    # Compute quick metrics for model summary
                    valid_cases = int(tagged_frame["valid"].sum()) if "valid" in tagged_frame else 0
                    total_cases = len(tagged_frame)
                    correct_cases = int(tagged_frame["correct"].sum()) if "correct" in tagged_frame else 0
                    accuracy = (correct_cases / total_cases * 100) if total_cases > 0 else 0.0
                    avg_lat = float(tagged_frame["latency_ms"].mean()) if "latency_ms" in tagged_frame else 0.0

                    summary_records.append({
                        "model": model,
                        "experiment": exp_name,
                        "status": "SUCCESS",
                        "total_cases": total_cases,
                        "valid_cases": valid_cases,
                        "accuracy_pct": round(accuracy, 1),
                        "avg_latency_ms": round(avg_lat, 1),
                        "duration_s": round(elapsed, 1),
                    })
                    console.print(
                        f"\n[bold green]✓ Done {model}[/] on [bold yellow]{exp_name}[/] in [cyan]{elapsed:.1f}s[/] "
                        f"| Acc: [bold]{accuracy:.1f}%[/] | Valid: [bold]{valid_cases}/{total_cases}[/] | Latency: [cyan]{avg_lat:.0f}ms[/]\n"
                    )
                except Exception as exc:
                    logger.error("Experiment '%s' on model '%s' failed: %s", exp_name, model, exc)
                    summary_records.append({
                        "model": model,
                        "experiment": exp_name,
                        "status": "ERROR_EXECUTION",
                        "error": str(exc),
                    })
                    console.print(f"[bold red]✗ Failed {model} on {exp_name}:[/] {exc}")

            # 3. Unload model to completely free VRAM/RAM before next model
            if not is_jev and idx < total_models:
                self.korgis.unload_model(model)
                time.sleep(1.0)

        # 4. Build report across all evaluated frames
        if all_frames:
            combined = pd.concat(all_frames, ignore_index=True)
            requested_korgis = [
                m for m in models
                if not (m.strip().lower() in {"jev", "jev-latest"} or m.startswith("jev-"))
            ]
            _record_manifest(
                combined,
                group=group_id,
                suite=f"local-{dataset}",
                parameters={
                    "models": models,
                    "experiments": experiments,
                    "dataset": dataset,
                    "profile": profile if dataset == "public" else None,
                    "seed": self.seed,
                    "enable_thinking": self.enable_thinking,
                },
                requested_korgis_models=requested_korgis,
            )
            build_report(self.output_csv, self.report_html, run_group="latest_per_model")
            logger.info("Report updated at: %s", self.report_html)

        return {
            "group_id": group_id,
            "summary": summary_records,
            "report_html": str(self.report_html),
            "output_csv": str(self.output_csv),
        }

    def _run_single_experiment(
        self,
        exp_name: str,
        provider: DecisionProvider,
        model_name: str,
        dataset: str,
        profile: str,
    ) -> pd.DataFrame:
        clean_exp = exp_name.strip().lower().replace("_", "-")

        if dataset == "public":
            sizes = PUBLIC_PROFILES[profile]
            if clean_exp == "routing":
                cases = balanced_banking77_cases(
                    self.cache_dir,
                    max_cases=sizes["routing"],
                    seed=self.seed,
                    experiment="01-routing-public",
                )
                questions = [banking77_question(self.cache_dir, include_other=False)]
                rows = self._run_cases_with_progress(
                    "01-routing-public", provider, cases, questions, model_name,
                )
                return pd.DataFrame(rows)
            elif clean_exp == "calibration":
                cases = calibration_public_cases(
                    self.cache_dir,
                    in_scope_cases=sizes["in_scope"],
                    oos_cases=sizes["oos"],
                    seed=self.seed,
                )
                questions = [banking77_question(self.cache_dir, include_other=True)]
                rows = self._run_cases_with_progress(
                    "02-calibration-public", provider, cases, questions, model_name,
                )
                return pd.DataFrame(rows)
            else:
                raise ValueError(
                    f"Public dataset tier supports only 'routing' and 'calibration', got '{clean_exp}'."
                )

        # Smoke experiments
        if clean_exp == "routing":
            rows = self._run_cases_with_progress(
                "01-routing", provider, routing_cases(), routing_questions(), model_name,
            )
        elif clean_exp == "calibration":
            rows = self._run_cases_with_progress(
                "02-calibration", provider, calibration_cases(), routing_questions(), model_name,
            )
        elif clean_exp == "scaling":
            rows = run_scaling(provider)
        elif clean_exp == "workflow":
            rows = run_workflow("04-workflow", provider, expense_cases(), expense_questions(), _expense_action)
        elif clean_exp == "agent":
            rows = run_workflow("05-hybrid-agent", provider, support_cases(), support_questions(), _support_action)
        else:
            raise ValueError(f"Unknown experiment '{clean_exp}'.")

        return pd.DataFrame(rows)

    def _run_cases_with_progress(
        self,
        experiment: str,
        provider: DecisionProvider,
        cases: Sequence[BenchmarkCase],
        questions: Sequence[QuestionSpec],
        model_name: str,
    ) -> list[dict]:
        """Execute benchmark cases while displaying a live progress bar and per-case details."""
        return run_cases_with_progress(
            experiment=experiment,
            provider=provider,
            cases=cases,
            questions=questions,
            model_name=model_name,
            console=console,
            row_builder=_rows_for_case,
        )
