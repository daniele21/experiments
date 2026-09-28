from __future__ import annotations

from benchmark_core import (
    DatasetLoadContext,
    DatasetLoadResult,
    DatasetSpec,
    Sample,
    fingerprint_values,
    load_clinc_rows,
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
        exclude_terms = require_string_list(
            self.spec.options.get("exclude_terms"),
            context=f"dataset {self.spec.dataset_id!r} exclude_terms",
        )
        expected_label = require_text(
            self.spec.options.get("expected_label"),
            context=f"dataset {self.spec.dataset_id!r} expected_label",
        )
        candidates = load_clinc_rows(
            path,
            split=self.spec.split,
            exclude_terms=exclude_terms,
        )

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
                "upstream_split_count": len(
                    load_clinc_rows(path, split=self.spec.split)
                ),
                "filtered_count": len(candidates),
                "filter": "exclude_terms",
            },
        )
