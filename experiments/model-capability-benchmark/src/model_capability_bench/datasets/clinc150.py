from __future__ import annotations

import json

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
    require_string_list,
    require_text,
    single_cached_source,
)


class Clinc150OosDataset:
    def __init__(self, spec: DatasetSpec) -> None:
        self._spec = spec

    @property
    def spec(self) -> DatasetSpec:
        return self._spec

    def load(self, context: DatasetLoadContext) -> DatasetLoadResult:
        path = single_cached_source(self.spec, context)
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("CLINC150 data root must be an object")

        raw = payload.get(self.spec.split)
        if not isinstance(raw, list):
            raise ValueError(
                f"CLINC150 source has no list split {self.spec.split!r}"
            )

        exclude_terms = tuple(
            term.lower()
            for term in require_string_list(
                self.spec.options.get("exclude_terms"),
                context=f"dataset {self.spec.dataset_id!r} exclude_terms",
            )
        )
        expected_label = require_text(
            self.spec.options.get("expected_label"),
            context=f"dataset {self.spec.dataset_id!r} expected_label",
        )

        candidates: list[tuple[int, str, str]] = []
        for source_index, item in enumerate(raw):
            if not isinstance(item, list) or len(item) < 2:
                continue
            text = str(item[0]).strip()
            source_label = str(item[1]).strip()
            if not text:
                continue
            normalized = text.lower()
            if any(term in normalized for term in exclude_terms):
                continue
            candidates.append((source_index, text, source_label))

        rng = seeded_random(context.seed)
        rng.shuffle(candidates)
        max_cases = context.profile.max_cases_for(self.spec.dataset_id)
        selected = candidates if max_cases is None else candidates[:max_cases]

        samples = tuple(
            Sample(
                sample_id=f"clinc150-{self.spec.split}-{source_index:05d}",
                input=text,
                expected=expected_label,
                metadata={
                    "dataset_id": self.spec.dataset_id,
                    "dataset_revision": self.spec.revision,
                    "source_split": self.spec.split,
                    "source_index": source_index,
                    "source_label": source_label,
                    "oos": True,
                },
            )
            for source_index, text, source_label in selected
        )
        return DatasetLoadResult(
            spec=self.spec,
            samples=samples,
            selection_fingerprint=fingerprint_values(
                [sample.sample_id for sample in samples]
            ),
            available_count=len(candidates),
            source_checksums={"source": sha256_file(path)},
            metadata={
                "upstream_split_count": len(raw),
                "filtered_count": len(candidates),
                "filter": "exclude_terms",
            },
        )
