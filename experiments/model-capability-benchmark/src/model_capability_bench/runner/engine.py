from __future__ import annotations

import dataclasses
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from benchmark_core import (
    BenchmarkCaseIdentity,
    DatasetLoadContext,
    EvaluationRecord,
    InferenceProvider,
    InferenceResult,
    RawInferenceRecord,
    TaskExecutionContext,
    create_run_identity,
    preflight_models,
    resolve_capability_context,
)

from model_capability_bench.runner.aggregation import aggregate_capability
from model_capability_bench.runner.contracts import (
    RunnerConfig,
    RunnerSummary,
    RuntimeResolver,
)
from model_capability_bench.runner.evidence import EvidenceStore
from model_capability_bench.suite import CapabilitySuiteBundle


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
        generation = dataclasses.replace(
            self.suite.suite.generation,
            seed=config.seed,
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
                "model_keys": list(config.model_keys),
                "capability_ids": list(capability_ids),
            },
        )

        dataset_cache: dict[str, Any] = {}
        planned_cases = 0
        completed_cases = 0
        failed_cases = 0
        skipped_cases = 0
        model_failures = 0
        planned_case_ids: set[str] = set()

        for model in selected_models:
            model_arms = arms_by_model.get(model.model.model_key, [])
            if not model_arms:
                continue

            try:
                runtime = self.runtime_resolver(model)
                provider = runtime.prepare(model)
                if not isinstance(provider, InferenceProvider):
                    raise TypeError(
                        f"Runtime {model.runtime.runtime_key!r} did not return "
                        "an InferenceProvider"
                    )
            except Exception as exc:  # noqa: BLE001 - model/runtime boundary
                model_failures += 1
                self.evidence_store.record_event(
                    "runtime_prepare_failed",
                    metadata={
                        "run_id": identity.run_id,
                        "model_key": model.model.model_key,
                        "runtime_key": model.runtime.runtime_key,
                        "provider_key": model.provider.provider_key,
                    },
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

                    loaded_for_capability: dict[str, Any] = {}
                    dataset_failed = False
                    for dataset_id in capability.spec.dataset_ids:
                        try:
                            if dataset_id not in dataset_cache:
                                dataset_cache[dataset_id] = self.suite.datasets.load(
                                    dataset_id,
                                    DatasetLoadContext(
                                        cache_dir=self.cache_dir,
                                        profile=profile,
                                        seed=config.seed,
                                    ),
                                )
                            loaded_for_capability[dataset_id] = dataset_cache[dataset_id]
                        except Exception as exc:  # noqa: BLE001 - dataset boundary
                            dataset_failed = True
                            self.evidence_store.record_event(
                                "dataset_load_failed",
                                metadata={
                                    "run_id": identity.run_id,
                                    "model_key": model.model.model_key,
                                    "capability_id": capability.spec.capability_id,
                                    "dataset_id": dataset_id,
                                },
                                error=exc,
                            )
                            break

                    if dataset_failed:
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
                                continue

                            case_metadata = {
                                "run_id": identity.run_id,
                                "run_group": identity.run_group,
                                "suite_id": self.suite.suite.suite_id,
                                "suite_version": self.suite.suite.version,
                                "model_key": model.model.model_key,
                                "model_id": model.model.model_id,
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
                            }
                            attempt = self.evidence_store.begin_case(
                                case_id,
                                identity=case_identity,
                                metadata=case_metadata,
                            )

                            try:
                                request = task.build_request(sample, task_context)
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

                            try:
                                inference = provider.generate(request)
                                if not isinstance(inference, InferenceResult):
                                    raise TypeError(
                                        "InferenceProvider.generate() must return "
                                        "InferenceResult"
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
                            self.evidence_store.complete_case(
                                case_id,
                                attempt,
                                metadata=case_metadata,
                            )
                            completed_cases += 1
            finally:
                try:
                    runtime.release(model)
                except Exception as exc:  # noqa: BLE001 - runtime cleanup boundary
                    self.evidence_store.record_event(
                        "runtime_release_failed",
                        metadata={
                            "run_id": identity.run_id,
                            "model_key": model.model.model_key,
                            "runtime_key": model.runtime.runtime_key,
                        },
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
                    self.evidence_store.append_aggregate(record)
                    aggregate_count += 1

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
            metadata=dict(config.metadata),
        )
