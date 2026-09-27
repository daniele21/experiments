from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml
from benchmark_core import (
    DatasetLoadContext,
    DatasetLoadResult,
    DatasetSpec,
    Sample,
    fingerprint_values,
    seeded_random,
    sha256_file,
)

from model_capability_bench.datasets.common import (
    require_mapping,
    require_text,
    safe_child,
)

ROOT = Path(__file__).resolve().parents[3]


class StructuredOutputControlledDataset:
    def __init__(self, spec: DatasetSpec) -> None:
        self._spec = spec

    @property
    def spec(self) -> DatasetSpec:
        return self._spec

    def _path(self) -> Path:
        relative = require_text(
            self.spec.options.get("path"),
            context=f"dataset {self.spec.dataset_id!r} path",
        )
        path = safe_child(
            ROOT,
            relative,
            context=f"dataset {self.spec.dataset_id!r} path",
        )
        if not path.is_file():
            raise FileNotFoundError(path)
        return path

    @staticmethod
    def _samples(path: Path, spec: DatasetSpec) -> tuple[Sample, ...]:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or not isinstance(payload.get("cases"), list):
            raise ValueError("controlled dataset root must contain a cases list")

        seen: set[str] = set()
        samples: list[Sample] = []
        allowed = {"sample_id", "input", "expected", "response_schema"}
        for index, raw in enumerate(payload["cases"]):
            case = require_mapping(raw, context=f"controlled case {index}")
            unknown = sorted(str(key) for key in case if str(key) not in allowed)
            if unknown:
                raise ValueError(
                    f"controlled case {index} contains unsupported fields: "
                    f"{', '.join(unknown)}"
                )
            sample_id = require_text(
                case.get("sample_id"),
                context=f"controlled case {index} sample_id",
            )
            if sample_id in seen:
                raise ValueError(f"duplicate controlled sample_id: {sample_id}")
            seen.add(sample_id)
            input_text = require_text(
                case.get("input"),
                context=f"controlled case {sample_id!r} input",
            )
            expected = case.get("expected")
            if not isinstance(expected, Mapping):
                raise ValueError(
                    f"controlled case {sample_id!r} expected must be an object"
                )
            schema = case.get("response_schema")
            if not isinstance(schema, Mapping) or not schema:
                raise ValueError(
                    f"controlled case {sample_id!r} response_schema must be an object"
                )
            samples.append(
                Sample(
                    sample_id=sample_id,
                    input=input_text,
                    expected=dict(expected),
                    metadata={
                        "dataset_id": spec.dataset_id,
                        "dataset_revision": spec.revision,
                        "source_split": spec.split,
                        "source_index": index,
                        "response_schema": dict(schema),
                    },
                )
            )
        return tuple(samples)

    def load(self, context: DatasetLoadContext) -> DatasetLoadResult:
        path = self._path()
        available = list(self._samples(path, self.spec))
        max_cases = context.profile.max_cases_for(self.spec.dataset_id)

        if max_cases is not None and max_cases < len(available):
            rng = seeded_random(context.seed)
            rng.shuffle(available)
            selected = available[:max_cases]
        else:
            selected = available

        samples = tuple(selected)
        return DatasetLoadResult(
            spec=self.spec,
            samples=samples,
            selection_fingerprint=fingerprint_values(
                [sample.sample_id for sample in samples]
            ),
            available_count=len(available),
            source_checksums={"repository_file": sha256_file(path)},
            metadata={"repository_path": str(path.relative_to(ROOT))},
        )
