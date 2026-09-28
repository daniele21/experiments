from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from benchmark_core.datasets import DatasetLoadResult
from benchmark_core.suites.contracts import CapabilitySpec


class CapabilityContextError(ValueError):
    """Raised when a capability context binding cannot be resolved."""


def resolve_capability_context(
    capability: CapabilitySpec,
    dataset_results: Mapping[str, DatasetLoadResult],
) -> dict[str, Any]:
    resolved: dict[str, Any] = {}

    for binding in capability.context_bindings:
        if binding.source == "literal":
            value = binding.value
        else:
            dataset_id = binding.dataset_id
            field = binding.field
            if dataset_id is None or field is None:
                raise CapabilityContextError(
                    f"Capability {capability.capability_id!r} has incomplete "
                    f"context binding {binding.key!r}"
                )
            try:
                dataset = dataset_results[dataset_id]
            except KeyError as exc:
                raise CapabilityContextError(
                    f"Capability {capability.capability_id!r} context "
                    f"{binding.key!r} requires unloaded dataset {dataset_id!r}"
                ) from exc
            if field not in dataset.metadata:
                raise CapabilityContextError(
                    f"Dataset {dataset_id!r} metadata does not contain "
                    f"field {field!r} required by context {binding.key!r}"
                )
            value = dataset.metadata[field]

        if binding.append:
            if (
                not isinstance(value, Sequence)
                or isinstance(value, (str, bytes))
            ):
                raise CapabilityContextError(
                    f"Capability {capability.capability_id!r} context "
                    f"{binding.key!r} can append only to a sequence"
                )
            value = tuple(value) + tuple(binding.append)

        resolved[binding.key] = value

    return resolved
