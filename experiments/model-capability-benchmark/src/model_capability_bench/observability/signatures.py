from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

from benchmark_core import ResolvedModel, to_jsonable

SIGNATURE_SCHEMA_VERSION = "1"


def _canonical(value: Any) -> bytes:
    return json.dumps(
        to_jsonable(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def stable_signature(kind: str, payload: Any) -> str:
    if not kind.strip():
        raise ValueError("signature kind must not be empty")
    digest = hashlib.sha256(
        _canonical(
            {
                "signature_schema_version": SIGNATURE_SCHEMA_VERSION,
                "kind": kind,
                "payload": payload,
            }
        )
    ).hexdigest()
    return f"sha256:{kind}:{digest}"


def _semantic_model_metadata(metadata: Mapping[str, Any]) -> dict[str, Any]:
    excluded = {
        "prices_per_million_tokens",
        "display_name",
        "description",
        "notes",
    }
    return {
        str(key): value
        for key, value in metadata.items()
        if str(key) not in excluded
    }


def model_signature(model: ResolvedModel) -> str:
    artifact = model.model.artifact
    payload = {
        "model_key": model.model.model_key,
        "model_id": model.model.model_id,
        "runtime_model_id": model.model.runtime_model_id,
        "effective_model_id": model.effective_model_id,
        "family": model.model.family,
        "parameters_b": model.model.parameters_b,
        "artifact": (
            {
                "format": artifact.format,
                "quantization": artifact.quantization,
                "size_bytes": artifact.size_bytes,
                "source": artifact.source,
                "metadata": dict(artifact.metadata),
            }
            if artifact is not None
            else None
        ),
        "metadata": _semantic_model_metadata(model.model.metadata),
    }
    return stable_signature("model", payload)


def execution_signature(
    model: ResolvedModel,
    *,
    execution_metadata: Mapping[str, Any] | None = None,
) -> str:
    payload = {
        "runtime": {
            "runtime_key": model.runtime.runtime_key,
            "deployment": model.runtime.deployment,
            "lifecycle": model.runtime.lifecycle,
            "options": dict(model.runtime.options),
        },
        "provider": {
            "provider_key": model.provider.provider_key,
            "provider_type": model.provider.provider_type,
            "options": dict(model.provider.options),
        },
        "execution_metadata": dict(execution_metadata or {}),
    }
    return stable_signature("execution", payload)


def benchmark_signature(
    *,
    suite_id: str,
    suite_version: str,
    capability: Any,
    task: Any,
    loaded_datasets: Mapping[str, Any],
    profile_id: str,
    generation: Any,
    seed: int,
) -> str:
    dataset_payload = []
    for dataset_id in capability.spec.dataset_ids:
        loaded = loaded_datasets[dataset_id]
        dataset_payload.append(
            {
                "dataset_id": dataset_id,
                "version": loaded.spec.version,
                "revision": loaded.spec.revision,
                "split": loaded.spec.split,
                "selection_fingerprint": loaded.selection_fingerprint,
                "source_checksums": dict(loaded.source_checksums),
            }
        )

    payload = {
        "suite_id": suite_id,
        "suite_version": suite_version,
        "capability_id": capability.spec.capability_id,
        "task_id": task.spec.task_id,
        "task_version": task.spec.version,
        "prompt_id": task.spec.prompt_id,
        "prompt_version": task.spec.prompt_version,
        "evaluator_id": task.spec.evaluator_id,
        "evaluator_version": task.spec.evaluator_version,
        "datasets": dataset_payload,
        "profile": profile_id,
        "generation": generation,
        "seed": seed,
        "comparison": capability.spec.comparison,
    }
    return stable_signature("benchmark", payload)
