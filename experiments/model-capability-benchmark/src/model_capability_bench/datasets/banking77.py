from __future__ import annotations

from benchmark_core import (
    DatasetLoadContext,
    DatasetLoadResult,
    DatasetSpec,
    Sample,
    fingerprint_values,
    load_banking77_categories,
    load_banking77_rows,
    seeded_random,
    sha256_file,
)

from model_capability_bench.datasets.common import cached_source


class Banking77Dataset:
    def __init__(self, spec: DatasetSpec) -> None:
        self._spec = spec

    @property
    def spec(self) -> DatasetSpec:
        return self._spec

    def load(self, context: DatasetLoadContext) -> DatasetLoadResult:
        test_path = cached_source(self.spec, context, file_key="test")
        categories_path = cached_source(
            self.spec,
            context,
            file_key="categories",
        )
        categories = load_banking77_categories(categories_path)
        category_set = set(categories)
        rows = load_banking77_rows(test_path)

        by_label: dict[str, list[tuple[int, str]]] = {
            label: [] for label in categories
        }
        for source_index, text, label in rows:
            if label not in category_set:
                raise ValueError(f"BANKING77 row uses unknown category {label!r}")
            by_label[label].append((source_index, text))

        rng = seeded_random(context.seed)
        for label in categories:
            rng.shuffle(by_label[label])

        max_cases = context.profile.max_cases_for(self.spec.dataset_id)
        target = len(rows) if max_cases is None else min(max_cases, len(rows))

        selected_rows: list[tuple[int, str, str]] = []
        offsets = {label: 0 for label in categories}
        while len(selected_rows) < target:
            progressed = False
            for label in categories:
                offset = offsets[label]
                bucket = by_label[label]
                if offset >= len(bucket):
                    continue
                source_index, text = bucket[offset]
                offsets[label] = offset + 1
                selected_rows.append((source_index, text, label))
                progressed = True
                if len(selected_rows) >= target:
                    break
            if not progressed:
                break

        rng.shuffle(selected_rows)
        samples = tuple(
            Sample(
                sample_id=f"banking77-test-{source_index:05d}",
                input=text,
                expected=label,
                metadata={
                    "dataset_id": self.spec.dataset_id,
                    "dataset_revision": self.spec.revision,
                    "source_split": self.spec.split,
                    "source_index": source_index,
                    "labels": categories,
                },
            )
            for source_index, text, label in selected_rows
        )
        return DatasetLoadResult(
            spec=self.spec,
            samples=samples,
            selection_fingerprint=fingerprint_values(
                [sample.sample_id for sample in samples]
            ),
            available_count=len(rows),
            source_checksums={
                "test": sha256_file(test_path),
                "categories": sha256_file(categories_path),
            },
            metadata={
                "sampling": self.spec.options.get("sampling"),
                "class_count": len(categories),
                "labels": categories,
            },
        )
