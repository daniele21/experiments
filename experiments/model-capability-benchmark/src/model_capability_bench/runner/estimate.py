from __future__ import annotations

import dataclasses
import time
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from benchmark_core import (
    InferenceProvider,
    InferenceResult,
    TaskExecutionContext,
    preflight_models,
    resolve_capability_context,
)

from model_capability_bench.runner.capability_data import load_capability_datasets
from model_capability_bench.runner.contracts import RuntimeResolver
from model_capability_bench.runner.pricing import enrich_inference_cost
from model_capability_bench.suite import CapabilitySuiteBundle


def _percentile(values: Sequence[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * q
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def _representative_cases(
    loaded: Mapping[str, Any],
    dataset_order: Sequence[str],
    limit: int,
) -> list[tuple[str, Any]]:
    if limit <= 0:
        raise ValueError("pilot_cases must be > 0")

    entries = [
        (dataset_id, sample)
        for dataset_id in dataset_order
        for sample in loaded[dataset_id].samples
    ]
    if len(entries) <= limit:
        return entries

    selected: list[tuple[str, Any]] = []
    selected_ids: set[tuple[str, str]] = set()

    def add(entry: tuple[str, Any]) -> None:
        key = (entry[0], entry[1].sample_id)
        if key not in selected_ids and len(selected) < limit:
            selected.append(entry)
            selected_ids.add(key)

    # Preserve multi-dataset coverage first.
    for dataset_id in dataset_order:
        samples = loaded[dataset_id].samples
        if samples:
            add((dataset_id, samples[0]))

    # Controlled suites expose failure families. Cover distinct families next.
    by_family: dict[str, tuple[str, Any]] = {}
    for entry in entries:
        family = entry[1].metadata.get("family")
        if family is not None:
            by_family.setdefault(str(family), entry)
    for family in sorted(by_family):
        add(by_family[family])

    remaining = [
        entry
        for entry in entries
        if (entry[0], entry[1].sample_id) not in selected_ids
    ]
    slots = limit - len(selected)
    if slots > 0 and remaining:
        # Evenly spread the rest across the deterministic selected dataset.
        for index in range(slots):
            position = min(
                len(remaining) - 1,
                int(index * len(remaining) / slots),
            )
            add(remaining[position])

    return selected[:limit]


def _budget_status(
    *,
    deployment: str,
    tier,
    projected_seconds_p95: float | None,
    projected_cost_usd: float | None,
) -> bool | None:
    if tier is None:
        return None
    if deployment == "local":
        if tier.hard_local_seconds is None or projected_seconds_p95 is None:
            return None
        return projected_seconds_p95 <= tier.hard_local_seconds
    if tier.hard_api_cost_usd is None or projected_cost_usd is None:
        return None
    return projected_cost_usd <= tier.hard_api_cost_usd


def estimate_benchmark(
    bundle: CapabilitySuiteBundle,
    *,
    runtime_resolver: RuntimeResolver,
    cache_dir: Path,
    environ: Mapping[str, str],
    profile_id: str,
    model_keys: Sequence[str],
    capability_ids: Sequence[str] | None = None,
    pilot_cases: int = 5,
    seed: int = 42,
) -> dict[str, Any]:
    if pilot_cases <= 0:
        raise ValueError("pilot_cases must be > 0")
    try:
        profile = bundle.profiles[profile_id]
    except KeyError as exc:
        raise ValueError(f"Unknown profile {profile_id!r}") from exc

    selected_models = bundle.models.select(model_keys=model_keys)
    preflight_models(bundle.models, selected_models, environ).raise_for_errors()

    requested = set(capability_ids or ())
    capabilities = [
        capability
        for capability in bundle.resolved_capabilities
        if not requested or capability.spec.capability_id in requested
    ]
    if requested:
        found = {item.spec.capability_id for item in capabilities}
        missing = sorted(requested - found)
        if missing:
            raise ValueError("Unknown capability IDs: " + ", ".join(missing))

    generation = dataclasses.replace(bundle.suite.generation, seed=seed)
    dataset_cache: dict[tuple[str, str, str, int], Any] = {}
    model_results: list[dict[str, Any]] = []

    for model in selected_models:
        runtime = runtime_resolver(model)
        prepare_started = time.perf_counter()
        provider = runtime.prepare(model)
        prepare_seconds = time.perf_counter() - prepare_started

        capability_results: list[dict[str, Any]] = []
        try:
            if not isinstance(provider, InferenceProvider):
                raise TypeError(
                    f"Runtime {model.runtime.runtime_key!r} did not return "
                    "an InferenceProvider"
                )
            for capability in capabilities:
                loaded = load_capability_datasets(
                    suite=bundle,
                    capability=capability,
                    profile=profile,
                    profile_id=profile_id,
                    cache_dir=cache_dir,
                    seed=seed,
                    cache=dataset_cache,
                )
                context_metadata = resolve_capability_context(
                    capability.spec,
                    loaded,
                )
                pilot = _representative_cases(
                    loaded,
                    capability.spec.dataset_ids,
                    pilot_cases,
                )
                planned_cases = sum(
                    len(item.samples) for item in loaded.values()
                )
                task = bundle.tasks.get(capability.spec.task_id)

                latencies: list[float] = []
                costs: list[float] = []
                cost_sources: set[str] = set()
                failures = 0
                input_tokens = 0
                output_tokens = 0
                input_token_samples = 0
                output_token_samples = 0

                for dataset_id, sample in pilot:
                    task_context = TaskExecutionContext(
                        run_id="estimate",
                        dataset_id=dataset_id,
                        profile=profile_id,
                        generation=generation,
                        metadata=context_metadata,
                    )
                    request = task.build_request(sample, task_context)
                    try:
                        result = provider.generate(request)
                    except Exception:  # noqa: BLE001 - pilot provider boundary
                        failures += 1
                        continue
                    if not isinstance(result, InferenceResult):
                        failures += 1
                        continue
                    provider_cost_present = result.estimated_cost_usd is not None
                    result = enrich_inference_cost(
                        pricing_path=bundle.root / "pricing_snapshot.json",
                        model=model,
                        result=result,
                    )
                    latencies.append(float(result.latency_ms))
                    if not result.valid:
                        failures += 1
                    if result.estimated_cost_usd is not None:
                        costs.append(float(result.estimated_cost_usd))
                        cost_sources.add(
                            "provider"
                            if provider_cost_present
                            else "pricing_snapshot"
                        )
                    if result.usage.input_tokens is not None:
                        input_tokens += result.usage.input_tokens
                        input_token_samples += 1
                    if result.usage.output_tokens is not None:
                        output_tokens += result.usage.output_tokens
                        output_token_samples += 1

                mean_latency_ms = (
                    sum(latencies) / len(latencies) if latencies else None
                )
                p95_latency_ms = _percentile(latencies, 0.95)
                projected_seconds_mean = (
                    mean_latency_ms * planned_cases / 1000
                    if mean_latency_ms is not None
                    else None
                )
                projected_seconds_p95 = (
                    p95_latency_ms * planned_cases / 1000
                    if p95_latency_ms is not None
                    else None
                )
                cost_is_known = bool(costs) and len(costs) == len(latencies)
                mean_cost = (
                    sum(costs) / len(costs)
                    if cost_is_known
                    else None
                )
                projected_cost = (
                    mean_cost * planned_cases
                    if mean_cost is not None
                    else None
                )
                tier = capability.spec.benchmark_tier(profile_id)

                capability_results.append(
                    {
                        "capability_id": capability.spec.capability_id,
                        "planned_cases": planned_cases,
                        "pilot_cases_requested": pilot_cases,
                        "pilot_cases_observed": len(latencies),
                        "pilot_failures": failures,
                        "mean_latency_ms": mean_latency_ms,
                        "p95_latency_ms": p95_latency_ms,
                        "projected_seconds_mean": projected_seconds_mean,
                        "projected_seconds_p95": projected_seconds_p95,
                        "projected_cost_usd": projected_cost,
                        "cost_source": (
                            next(iter(cost_sources))
                            if len(cost_sources) == 1
                            else "mixed"
                            if cost_sources
                            else None
                        ),
                        "mean_input_tokens": (
                            input_tokens / input_token_samples
                            if input_token_samples
                            else None
                        ),
                        "mean_output_tokens": (
                            output_tokens / output_token_samples
                            if output_token_samples
                            else None
                        ),
                        "hard_local_seconds": (
                            tier.hard_local_seconds if tier is not None else None
                        ),
                        "hard_api_cost_usd": (
                            tier.hard_api_cost_usd if tier is not None else None
                        ),
                        "within_hard_budget": _budget_status(
                            deployment=model.runtime.deployment,
                            tier=tier,
                            projected_seconds_p95=projected_seconds_p95,
                            projected_cost_usd=projected_cost,
                        ),
                    }
                )
        finally:
            runtime.release(model)

        projected_mean_values = [
            item["projected_seconds_mean"]
            for item in capability_results
            if item["projected_seconds_mean"] is not None
        ]
        projected_p95_values = [
            item["projected_seconds_p95"]
            for item in capability_results
            if item["projected_seconds_p95"] is not None
        ]
        projected_cost_values = [
            item["projected_cost_usd"]
            for item in capability_results
            if item["projected_cost_usd"] is not None
        ]
        all_costs_known = (
            bool(capability_results)
            and len(projected_cost_values) == len(capability_results)
        )
        hard_local_total = sum(
            float(tier.hard_local_seconds or 0)
            for capability in capabilities
            if (tier := capability.spec.benchmark_tier(profile_id)) is not None
        )
        hard_api_total = sum(
            float(tier.hard_api_cost_usd or 0)
            for capability in capabilities
            if (tier := capability.spec.benchmark_tier(profile_id)) is not None
        )
        projected_total_p95 = (
            prepare_seconds + sum(projected_p95_values)
            if len(projected_p95_values) == len(capability_results)
            else None
        )
        projected_total_cost = (
            sum(projected_cost_values) if all_costs_known else None
        )
        if model.runtime.deployment == "local":
            overall_within = (
                projected_total_p95 <= hard_local_total
                if projected_total_p95 is not None and hard_local_total > 0
                else None
            )
        else:
            overall_within = (
                projected_total_cost <= hard_api_total
                if projected_total_cost is not None and hard_api_total > 0
                else None
            )

        model_results.append(
            {
                "model_key": model.model.model_key,
                "model_id": model.model.model_id,
                "runtime_key": model.runtime.runtime_key,
                "deployment": model.runtime.deployment,
                "prepare_seconds": prepare_seconds,
                "capabilities": capability_results,
                "projected_total_seconds_mean": (
                    prepare_seconds + sum(projected_mean_values)
                    if len(projected_mean_values) == len(capability_results)
                    else None
                ),
                "projected_total_seconds_p95": projected_total_p95,
                "projected_total_cost_usd": projected_total_cost,
                "hard_local_seconds": hard_local_total or None,
                "hard_api_cost_usd": hard_api_total or None,
                "within_hard_budget": overall_within,
            }
        )

    return {
        "suite_id": bundle.suite.suite_id,
        "suite_version": bundle.suite.version,
        "profile": profile_id,
        "pilot_cases_per_capability": pilot_cases,
        "models": model_results,
        "semantics": (
            "Runtime projections multiply pilot request latency by planned cases; "
            "the p95 projection is intentionally conservative. Model preparation is "
            "added once per model. API cost is projected only when every observed "
            "pilot request has provider-reported cost or a versioned pricing snapshot. "
            "Local hardware/runtime cost remains separate from provider token pricing."
        ),
    }
