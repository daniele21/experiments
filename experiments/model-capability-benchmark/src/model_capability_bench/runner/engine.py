from __future__ import annotations

import dataclasses
import os
from collections.abc import Mapping
from pathlib import Path
from time import perf_counter
from typing import Any

from benchmark_core import (
    BenchmarkCaseIdentity,
    EvaluationRecord,
    InferenceProvider,
    InferenceResult,
    RawInferenceRecord,
    TaskExecutionContext,
    create_run_identity,
    preflight_models,
    resolve_capability_context,
)
from model_capability_bench.observability import (
    EvidenceRef,
    benchmark_signature,
    execution_environment_identity,
    execution_signature,
    model_signature,
)
from model_capability_bench.runner.aggregation import aggregate_capability
from model_capability_bench.runner.capability_data import (
    CapabilityDatasetLoadError,
    load_capability_datasets,
)
from model_capability_bench.runner.contracts import (
    RunnerConfig,
    RunnerSummary,
    RuntimeResolver,
)
from model_capability_bench.runner.evidence import EvidenceStore
from model_capability_bench.runner.pricing import enrich_inference_cost
from model_capability_bench.suite import CapabilitySuiteBundle


_DIRECT_GENERATION_KEYS = {"temperature", "max_output_tokens", "seed", "stop"}
_EXTRA_GENERATION_KEYS = {"top_p", "top_k", "min_p", "repeat_penalty"}


def _configured_generation(base: Any, config: RunnerConfig) -> Any:
    overrides = dict(config.inference_config)
    unknown = sorted(
        set(overrides) - _DIRECT_GENERATION_KEYS - _EXTRA_GENERATION_KEYS
    )
    if unknown:
        raise ValueError(
            "Unsupported inference configuration keys: " + ", ".join(unknown)
        )

    extra = dict(base.extra)
    for key in _EXTRA_GENERATION_KEYS:
        if key in overrides:
            extra[key] = overrides.pop(key)

    stop = overrides.pop("stop", base.stop)
    if stop is None:
        stop = ()
    elif isinstance(stop, str):
        stop = (stop,)
    else:
        stop = tuple(stop)
    return dataclasses.replace(
        base,
        temperature=overrides.pop("temperature", base.temperature),
        max_output_tokens=overrides.pop(
            "max_output_tokens", base.max_output_tokens
        ),
        seed=overrides.pop("seed", config.seed),
        stop=stop,
        extra=extra,
    )


class CapabilityRunner:
    def __init__(
        self,
        *,
        suite: CapabilitySuiteBundle,
        runtime_resolver: RuntimeResolver,
        evidence_store: EvidenceStore,
        cache_dir: Path,
        environ: Mapping[str, str] | None = None,
    ) -> None:
        self.suite = suite
        self.runtime_resolver = runtime_resolver
        self.evidence_store = evidence_store
        self.cache_dir = cache_dir
        self.environ = dict(os.environ if environ is None else environ)

    def _profile(self, profile_id: str):
        try:
            return self.suite.profiles[profile_id]
        except KeyError as exc:
            available = ", ".join(sorted(self.suite.profiles))
            raise ValueError(
                f"Unknown profile {profile_id!r}; available: {available}"
            ) from exc

    def run(self, config: RunnerConfig) -> RunnerSummary:
        profile = self._profile(config.profile)
        generation = _configured_generation(
            self.suite.suite.generation,
            config,
        )
        selected_models = self.suite.models.select(
            model_keys=config.model_keys,
        )
        preflight_models(
            self.suite.models,
            selected_models,
            self.environ,
        ).raise_for_errors()

        matrix = self.suite.plan_matrix(
            model_keys=config.model_keys,
            capability_ids=config.capability_ids,
        )
        capability_ids = tuple(
            dict.fromkeys(arm.capability_id for arm in matrix)
        )
        capability_by_id = {
            capability.spec.capability_id: capability
            for capability in self.suite.resolved_capabilities
            if capability.spec.capability_id in capability_ids
        }
        arms_by_model: dict[str, list[Any]] = {}
        for arm in matrix:
            arms_by_model.setdefault(arm.model_key, []).append(arm)

        identity = create_run_identity(
            run_group=config.run_group,
            suite=self.suite.suite.suite_id,
            runner_location="model-capability-benchmark",
            run_id=config.run_id,
        )
        self.evidence_store.record_event(
            "run_started",
            metadata={
                "run_id": identity.run_id,
                "run_group": identity.run_group,
                "suite_id": self.suite.suite.suite_id,
                "suite_version": self.suite.suite.version,
                "profile": config.profile,
                "seed": config.seed,
                "configuration_id": config.configuration_id,
                "inference_config": dict(config.inference_config),
                "runtime_config": dict(config.runtime_config),
                "model_keys": list(config.model_keys),
                "capability_ids": list(capability_ids),
            },
        )

        dataset_cache: dict[tuple[str, str, str, int], Any] = {}
        planned_cases = 0
        completed_cases = 0
        failed_cases = 0
        skipped_cases = 0
        model_failures = 0
        planned_case_ids: set[str] = set()
        execution_environment = execution_environment_identity()
        signature_catalog: dict[str, Any] = {
            "models": {},
            "executions": {},
            "execution_metadata": {},
            "benchmarks": {},
            "execution_environment": execution_environment,
        }

        for model in selected_models:
            model_arms = arms_by_model.get(model.model.model_key, [])
            if not model_arms:
                continue

            model_sig = model_signature(model)
            signature_catalog["models"][model.model.model_key] = model_sig
            model_metadata = {
                "run_id": identity.run_id,
                "run_group": identity.run_group,
                "model_key": model.model.model_key,
                "model_signature": model_sig,
                "runtime_key": model.runtime.runtime_key,
                "provider_key": model.provider.provider_key,
            }
            self.evidence_store.record_stage_event(
                "model.prepare.started",
                metadata=model_metadata,
                status="started",
            )
            prepare_started = perf_counter()
            try:
                runtime = self.runtime_resolver(model)
                if config.runtime_config:
                    runtime_configurer = getattr(runtime, "configure", None)
                    if not callable(runtime_configurer):
                        raise ValueError(
                            f"Runtime {model.runtime.runtime_key!r} does not support "
                            "runtime configuration overrides"
                        )
                    runtime_configurer(config.runtime_config)
                provider = runtime.prepare(model)
                if not isinstance(provider, InferenceProvider):
                    raise TypeError(
                        f"Runtime {model.runtime.runtime_key!r} did not return "
                        "an InferenceProvider"
                    )

                runtime_execution_metadata: dict[str, Any] = {}
                runtime_metadata_getter = getattr(runtime, "execution_metadata", None)
                if callable(runtime_metadata_getter):
                    resolved_runtime_metadata = runtime_metadata_getter(model)
                    if resolved_runtime_metadata:
                        runtime_execution_metadata = dict(resolved_runtime_metadata)

                merged_execution_metadata = {
                    **dict(config.metadata),
                    "configuration_id": config.configuration_id,
                    "inference_config": dict(config.inference_config),
                    "runtime_config": dict(config.runtime_config),
                    **runtime_execution_metadata,
                }
                execution_sig = execution_signature(
                    model,
                    execution_metadata=merged_execution_metadata,
                    execution_environment=execution_environment,
                )
                signature_catalog["executions"][model.model.model_key] = execution_sig
                signature_catalog["execution_metadata"][
                    model.model.model_key
                ] = merged_execution_metadata
                model_metadata["execution_signature"] = execution_sig
                if runtime_execution_metadata:
                    model_metadata["runtime_execution_metadata"] = (
                        runtime_execution_metadata
                    )

                self.evidence_store.record_stage_event(
                    "model.prepare.completed",
                    metadata=model_metadata,
                    status="completed",
                    duration_ms=(perf_counter() - prepare_started) * 1000,
                )
            except Exception as exc:  # noqa: BLE001 - model/runtime boundary
                model_failures += 1
                self.evidence_store.record_event(
                    "runtime_prepare_failed",
                    metadata=model_metadata,
                    error=exc,
                )
                continue

            try:
                processed_capabilities: set[str] = set()
                for arm in model_arms:
                    if arm.capability_id in processed_capabilities:
                        continue
                    processed_capabilities.add(arm.capability_id)
                    capability = capability_by_id[arm.capability_id]
                    task = self.suite.tasks.get(capability.spec.task_id)

                    self.evidence_store.record_stage_event(
                        "capability.loading.started",
                        metadata={
                            **model_metadata,
                            "capability_id": capability.spec.capability_id,
                        },
                        status="started",
                    )
                    try:
                        loaded_for_capability = load_capability_datasets(
                            suite=self.suite,
                            capability=capability,
                            profile=profile,
                            profile_id=config.profile,
                            cache_dir=self.cache_dir,
                            seed=config.seed,
                            cache=dataset_cache,
                        )
                    except CapabilityDatasetLoadError as exc:
                        self.evidence_store.record_event(
                            "dataset_load_failed",
                            metadata={
                                "run_id": identity.run_id,
                                "model_key": model.model.model_key,
                                "capability_id": capability.spec.capability_id,
                                "dataset_id": exc.dataset_id,
                            },
                            error=exc.__cause__ or exc,
                        )
                        continue

                    context_metadata = resolve_capability_context(
                        capability.spec,
                        loaded_for_capability,
                    )
                    context_fingerprints = {
                        dataset_id: loaded.selection_fingerprint
                        for dataset_id, loaded in loaded_for_capability.items()
                    }
                    context_checksums = {
                        dataset_id: dict(loaded.source_checksums)
                        for dataset_id, loaded in loaded_for_capability.items()
                    }
                    benchmark_sig = benchmark_signature(
                        suite_id=self.suite.suite.suite_id,
                        suite_version=self.suite.suite.version,
                        capability=capability,
                        task=task,
                        loaded_datasets=loaded_for_capability,
                        profile_id=config.profile,
                        generation=generation,
                        seed=config.seed,
                    )
                    signature_catalog["benchmarks"][
                        capability.spec.capability_id
                    ] = benchmark_sig
                    capability_metadata = {
                        **model_metadata,
                        "capability_id": capability.spec.capability_id,
                        "benchmark_signature": benchmark_sig,
                        "profile": config.profile,
                    }
                    self.evidence_store.record_stage_event(
                        "capability.started",
                        metadata={
                            **capability_metadata,
                            "planned_cases": sum(
                                len(loaded_for_capability[dataset_id].samples)
                                for dataset_id in capability.spec.dataset_ids
                            ),
                        },
                        status="started",
                    )

                    for dataset_id in capability.spec.dataset_ids:
                        loaded = loaded_for_capability[dataset_id]
                        planned_cases += len(loaded.samples)
                        task_context = TaskExecutionContext(
                            run_id=identity.run_id,
                            dataset_id=dataset_id,
                            profile=config.profile,
                            generation=generation,
                            metadata=context_metadata,
                        )

                        for sample in loaded.samples:
                            case_identity = BenchmarkCaseIdentity(
                                suite_id=self.suite.suite.suite_id,
                                suite_version=self.suite.suite.version,
                                model_key=model.model.model_key,
                                model_id=model.model.model_id,
                                runtime_key=model.runtime.runtime_key,
                                capability_id=capability.spec.capability_id,
                                task_id=task.spec.task_id,
                                task_version=task.spec.version,
                                prompt_id=task.spec.prompt_id,
                                prompt_version=task.spec.prompt_version,
                                dataset_id=dataset_id,
                                dataset_revision=loaded.spec.revision,
                                dataset_split=loaded.spec.split,
                                selection_fingerprint=loaded.selection_fingerprint,
                                sample_id=sample.sample_id,
                                profile=config.profile,
                                generation=generation,
                                metadata={
                                    "context_fingerprints": context_fingerprints,
                                    "context_checksums": context_checksums,
                                    "configuration_id": config.configuration_id,
                                    "runtime_config": dict(config.runtime_config),
                                },
                            )
                            case_id = case_identity.case_id
                            planned_case_ids.add(case_id)

                            if (
                                config.resume
                                and self.evidence_store.should_skip(
                                    case_id,
                                    retry_failures=config.retry_failures,
                                )
                            ):
                                skipped_cases += 1
                                self.evidence_store.record_stage_event(
                                    "case.skipped",
                                    metadata={
                                        **capability_metadata,
                                        "case_id": case_id,
                                        "sample_id": sample.sample_id,
                                        "dataset_id": dataset_id,
                                        "previous_status": self.evidence_store.case_status(case_id),
                                    },
                                    status="skipped",
                                )
                                continue

                            case_metadata = {
                                "run_id": identity.run_id,
                                "run_group": identity.run_group,
                                "suite_id": self.suite.suite.suite_id,
                                "suite_version": self.suite.suite.version,
                                "model_key": model.model.model_key,
                                "model_id": model.model.model_id,
                                "model_signature": model_sig,
                                "execution_signature": execution_sig,
                                "benchmark_signature": benchmark_sig,
                                "runtime_key": model.runtime.runtime_key,
                                "provider_key": model.provider.provider_key,
                                "capability_id": capability.spec.capability_id,
                                "task_id": task.spec.task_id,
                                "task_version": task.spec.version,
                                "dataset_id": dataset_id,
                                "dataset_revision": loaded.spec.revision,
                                "dataset_split": loaded.spec.split,
                                "sample_id": sample.sample_id,
                                "profile": config.profile,
                                "benchmark_tier": config.profile,
                                "configuration_id": config.configuration_id,
                                "inference_config": dict(config.inference_config),
                                "runtime_config": dict(config.runtime_config),
                                "case_family": sample.metadata.get("family"),
                                "difficulty": sample.metadata.get("difficulty"),
                                "challenge_type": sample.metadata.get(
                                    "challenge_type"
                                ),
                            }
                            attempt = self.evidence_store.begin_case(
                                case_id,
                                identity=case_identity,
                                metadata=case_metadata,
                            )

                            request_started = perf_counter()
                            try:
                                request = task.build_request(sample, task_context)
                                self.evidence_store.record_stage_event(
                                    "request.built",
                                    metadata={
                                        **case_metadata,
                                        "case_id": case_id,
                                        "attempt": attempt,
                                    },
                                    status="completed",
                                    duration_ms=(
                                        perf_counter() - request_started
                                    ) * 1000,
                                )
                            except Exception as exc:  # noqa: BLE001 - task request boundary
                                failed_cases += 1
                                self.evidence_store.fail_case(
                                    case_id,
                                    attempt,
                                    stage="request",
                                    error=exc,
                                    metadata=case_metadata,
                                )
                                continue

                            inference_metadata = {
                                **case_metadata,
                                "case_id": case_id,
                                "attempt": attempt,
                            }
                            self.evidence_store.record_stage_event(
                                "inference.started",
                                metadata=inference_metadata,
                                status="started",
                            )
                            inference_started = perf_counter()
                            try:
                                inference = provider.generate(request)
                                if not isinstance(inference, InferenceResult):
                                    raise TypeError(
                                        "InferenceProvider.generate() must return "
                                        "InferenceResult"
                                    )
                                inference = enrich_inference_cost(
                                    pricing_path=self.suite.root / "pricing_snapshot.json",
                                    model=model,
                                    result=inference,
                                )
                            except Exception as exc:  # noqa: BLE001 - provider boundary
                                failed_cases += 1
                                self.evidence_store.fail_case(
                                    case_id,
                                    attempt,
                                    stage="provider",
                                    error=exc,
                                    metadata=case_metadata,
                                )
                                continue

                            inference_result_metadata = dict(inference.metadata)
                            resource_telemetry = inference_result_metadata.pop(
                                "resource_telemetry",
                                None,
                            )
                            if isinstance(resource_telemetry, Mapping):
                                resource_summary = (
                                    self.evidence_store.record_resource_telemetry(
                                        case_id,
                                        attempt,
                                        dict(resource_telemetry),
                                        metadata=case_metadata,
                                    )
                                )
                                if resource_summary is not None:
                                    inference_result_metadata["resource_summary"] = (
                                        resource_summary
                                    )
                                inference = dataclasses.replace(
                                    inference,
                                    metadata=inference_result_metadata,
                                )

                            raw_record = RawInferenceRecord.from_inference_result(
                                run_id=identity.run_id,
                                run_group=identity.run_group,
                                suite_id=self.suite.suite.suite_id,
                                task_id=task.spec.task_id,
                                sample_id=sample.sample_id,
                                result=inference,
                                metadata={
                                    **dict(inference.metadata),
                                    **case_metadata,
                                    "case_id": case_id,
                                    "attempt": attempt,
                                },
                            )
                            self.evidence_store.record_raw(
                                case_id,
                                attempt,
                                raw_record,
                                metadata=case_metadata,
                            )
                            self.evidence_store.record_stage_event(
                                "inference.completed",
                                metadata=inference_metadata,
                                status="completed",
                                duration_ms=(
                                    perf_counter() - inference_started
                                ) * 1000,
                                payload_ref=EvidenceRef(
                                    file="raw.jsonl",
                                    case_id=case_id,
                                    attempt=attempt,
                                ),
                            )

                            self.evidence_store.record_stage_event(
                                "evaluation.started",
                                metadata=inference_metadata,
                                status="started",
                            )
                            evaluation_started = perf_counter()
                            try:
                                task_result = task.evaluate(
                                    sample,
                                    inference,
                                    task_context,
                                )
                                evaluation_record = EvaluationRecord.from_task_result(
                                    run_id=identity.run_id,
                                    evaluator_version=task.spec.evaluator_version,
                                    result=task_result,
                                )
                            except Exception as exc:  # noqa: BLE001 - evaluator boundary
                                failed_cases += 1
                                self.evidence_store.fail_case(
                                    case_id,
                                    attempt,
                                    stage="evaluation",
                                    error=exc,
                                    metadata=case_metadata,
                                )
                                continue

                            self.evidence_store.record_evaluation(
                                case_id,
                                attempt,
                                evaluation_record,
                                metadata=case_metadata,
                            )
                            self.evidence_store.record_stage_event(
                                "evaluation.completed",
                                metadata=inference_metadata,
                                status="completed",
                                duration_ms=(
                                    perf_counter() - evaluation_started
                                ) * 1000,
                                payload_ref=EvidenceRef(
                                    file="evaluation.jsonl",
                                    case_id=case_id,
                                    attempt=attempt,
                                ),
                            )
                            self.evidence_store.complete_case(
                                case_id,
                                attempt,
                                metadata=case_metadata,
                            )
                            completed_cases += 1
                    self.evidence_store.record_stage_event(
                        "capability.completed",
                        metadata=capability_metadata,
                        status="completed",
                    )
            finally:
                self.evidence_store.record_stage_event(
                    "model.release.started",
                    metadata=model_metadata,
                    status="started",
                )
                release_started = perf_counter()
                try:
                    runtime.release(model)
                    self.evidence_store.record_stage_event(
                        "model.release.completed",
                        metadata=model_metadata,
                        status="completed",
                        duration_ms=(perf_counter() - release_started) * 1000,
                    )
                except Exception as exc:  # noqa: BLE001 - runtime cleanup boundary
                    self.evidence_store.record_event(
                        "runtime_release_failed",
                        metadata=model_metadata,
                        error=exc,
                    )

        evidence = self.evidence_store.completed_evidence()
        failures = self.evidence_store.failed_states()
        aggregate_count = 0
        for model in selected_models:
            for capability_id in capability_ids:
                capability = capability_by_id[capability_id].spec
                subset = [
                    item
                    for item in evidence
                    if item["case_id"] in planned_case_ids
                    and item["state"]["metadata"].get("model_key")
                    == model.model.model_key
                    and item["state"]["metadata"].get("capability_id")
                    == capability_id
                ]
                if not subset:
                    continue
                failure_count = sum(
                    state.get("case_id") in planned_case_ids
                    and state.get("metadata", {}).get("model_key")
                    == model.model.model_key
                    and state.get("metadata", {}).get("capability_id")
                    == capability_id
                    for state in failures
                )
                self.evidence_store.append_report_index(
                    {
                        "run_id": identity.run_id,
                        "run_group": identity.run_group,
                        "model_key": model.model.model_key,
                        "capability_id": capability_id,
                        "task_id": capability.task_id,
                        "profile": config.profile,
                        "cases": [
                            {
                                "case_id": item["case_id"],
                                "attempt": item["attempt"],
                            }
                            for item in subset
                        ],
                        "dataset_ids": sorted(
                            {
                                str(
                                    item["state"]["metadata"].get("dataset_id")
                                )
                                for item in subset
                            }
                        ),
                        "failure_count": failure_count,
                    }
                )
                aggregate_records = aggregate_capability(
                    capability,
                    subset,
                    model_key=model.model.model_key,
                    run_id=identity.run_id,
                    run_group=identity.run_group,
                    profile=config.profile,
                    failure_count=failure_count,
                )
                for record in aggregate_records:
                    record["model_signature"] = signature_catalog["models"].get(
                        model.model.model_key
                    )
                    record["execution_signature"] = signature_catalog[
                        "executions"
                    ].get(model.model.model_key)
                    record["benchmark_signature"] = signature_catalog[
                        "benchmarks"
                    ].get(capability_id)
                    self.evidence_store.append_aggregate(record)
                    aggregate_count += 1
                self.evidence_store.record_stage_event(
                    "capability.aggregated",
                    metadata={
                        "run_id": identity.run_id,
                        "run_group": identity.run_group,
                        "model_key": model.model.model_key,
                        "model_signature": signature_catalog["models"].get(
                            model.model.model_key
                        ),
                        "execution_signature": signature_catalog[
                            "executions"
                        ].get(model.model.model_key),
                        "benchmark_signature": signature_catalog[
                            "benchmarks"
                        ].get(capability_id),
                        "capability_id": capability_id,
                        "aggregate_count": len(aggregate_records),
                    },
                    status="completed",
                )

        self.evidence_store.record_event(
            "run_completed",
            metadata={
                "run_id": identity.run_id,
                "run_group": identity.run_group,
                "planned_cases": planned_cases,
                "completed_cases": completed_cases,
                "failed_cases": failed_cases,
                "skipped_cases": skipped_cases,
                "model_failures": model_failures,
                "aggregate_count": aggregate_count,
            },
        )
        return RunnerSummary(
            run_id=identity.run_id,
            run_group=identity.run_group,
            planned_cases=planned_cases,
            completed_cases=completed_cases,
            failed_cases=failed_cases,
            skipped_cases=skipped_cases,
            model_failures=model_failures,
            aggregate_count=aggregate_count,
            output_dir=str(self.evidence_store.root),
            metadata={
                **dict(config.metadata),
                "signatures": signature_catalog,
            },
        )
