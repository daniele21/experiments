"""Pinned, offline-cacheable public benchmark Parquet adapters.

The original test/validation rows and gold answers are not modified. MCB selects a
small deterministic subset, and records the exact upstream artifact checksum.
These are MCB subsets, not claims of official full-benchmark scores.
"""
from __future__ import annotations

import json
import re
from collections.abc import Mapping
from decimal import Decimal, InvalidOperation

from benchmark_core import (
    DatasetLoadContext,
    DatasetLoadResult,
    DatasetSpec,
    Sample,
    fingerprint_values,
    sha256_file,
)
from jsonschema.exceptions import SchemaError
from jsonschema.validators import validator_for

from model_capability_bench.datasets.common import single_cached_source
from model_capability_bench.datasets.selection import select_samples


def _rows(path, columns: tuple[str, ...]) -> list[dict]:
    import duckdb

    selected = ", ".join(f'"{column}"' for column in columns)
    with duckdb.connect(":memory:") as conn:
        result = conn.execute(
            f"SELECT {selected} FROM read_parquet(?)", [str(path)]
        )
        names = [item[0] for item in result.description]
        return [dict(zip(names, row, strict=True)) for row in result.fetchall()]


def _required_text(value: object, *, case: str, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{case}: missing or empty {field}")
    return value


def _gsm_final_answer(solution: str) -> str:
    match = re.search(r"(?m)^\s*####\s*([^\r\n]+)\s*$", solution)
    if not match:
        raise ValueError("GSM8K gold has no #### final answer")
    text = match.group(1).strip().replace(",", "")
    try:
        result = Decimal(text)
    except InvalidOperation as exc:
        raise ValueError(f"Non-numeric GSM8K final answer: {text!r}") from exc
    if not result.is_finite():
        raise ValueError("Non-finite GSM8K final answer")
    return format(result.normalize(), "f")


def _squad_answers(value: object) -> tuple[str, ...]:
    if not isinstance(value, Mapping):
        raise TypeError("SQuAD answers must be an object")
    texts = value.get("text")
    if not isinstance(texts, list) or not all(isinstance(t, str) for t in texts):
        raise ValueError("SQuAD answers.text must be a string list")
    return tuple(dict.fromkeys(texts))


def _unsafe_ref(value: object) -> bool:
    if isinstance(value, Mapping):
        for key, item in value.items():
            # Never fetch remote references implicitly while scoring.
            if key in {"$ref", "$dynamicRef", "$recursiveRef"} and (
                not isinstance(item, str) or not item.startswith("#/")
            ):
                return True
            if _unsafe_ref(item):
                return True
    elif isinstance(value, list):
        return any(_unsafe_ref(item) for item in value)
    return False


def _schema(value: object, *, max_chars: int) -> dict | None:
    if not isinstance(value, str) or len(value) > max_chars:
        return None
    try:
        schema = json.loads(value)
        if not isinstance(schema, dict) or schema.get("type") != "object":
            return None
        if _unsafe_ref(schema):
            return None
        validator_for(schema).check_schema(schema)
        return schema
    except (ValueError, TypeError, SchemaError, RecursionError):
        # Third-party schema catalogs can include dialects/extensions outside
        # the local JSON Schema validator. Those cases are explicitly excluded.
        return None


class PublicParquetBenchmark:
    def __init__(self, spec: DatasetSpec) -> None:
        self._spec = spec

    @property
    def spec(self) -> DatasetSpec:
        return self._spec

    def _convert(self, rows: list[dict]) -> tuple[list[Sample], dict]:
        source = self.spec.source
        samples: list[Sample] = []
        discarded = 0
        seen: set[str] = set()
        max_schema_chars = int(self.spec.options.get("max_schema_chars", 12000))

        for index, row in enumerate(rows):
            common = {
                "dataset_id": self.spec.dataset_id,
                "dataset_revision": self.spec.revision,
                "source_split": self.spec.split,
                "source_index": index,
                "provenance": "public-upstream",
            }
            if source == "openai/gsm8k":
                question = _required_text(row.get("question"), case=str(index), field="question")
                solution = _required_text(row.get("answer"), case=str(index), field="answer")
                sample_id = f"gsm8k-main-test-{index:05d}"
                value = Sample(
                    sample_id=sample_id, input=question,
                    expected=_gsm_final_answer(solution),
                    metadata={**common, "family": "grade_school_word_problem"},
                )
            elif source == "rajpurkar/squad_v2":
                source_id = _required_text(row.get("id"), case=str(index), field="id")
                context = _required_text(row.get("context"), case=source_id, field="context")
                question = _required_text(row.get("question"), case=source_id, field="question")
                aliases = _squad_answers(row.get("answers"))
                answerable = bool(aliases)
                sample_id = f"squad-v2-validation-{source_id}"
                value = Sample(
                    sample_id=sample_id,
                    input={"context": context, "question": question},
                    expected={"answer": aliases[0] if answerable else "", "answerable": answerable},
                    metadata={
                        **common, "answerable": answerable,
                        "family": "answerable" if answerable else "unanswerable",
                        "accepted_answers": list(aliases),
                        "answer_normalization": "squad-v2",
                        "source_title": str(row.get("title") or ""),
                    },
                )
            elif source == "epfl-dlab/JSONSchemaBench":
                source_id = _required_text(row.get("unique_id"), case=str(index), field="unique_id")
                schema = _schema(row.get("json_schema"), max_chars=max_schema_chars)
                if schema is None:
                    discarded += 1
                    continue
                subset = str(self.spec.options.get("subset") or "Github_easy")
                sample_id = f"jsonschemabench-{subset}-{self.spec.split}-{source_id}"
                value = Sample(
                    sample_id=sample_id,
                    input="Generate an example JSON object satisfying the supplied schema.",
                    expected=None,  # No semantic gold: this is a compliance task.
                    metadata={
                        **common, "family": subset,
                        "response_schema": schema,
                        "schema_characters": len(row["json_schema"]),
                        "schema_root_type": "object",
                    },
                )
            else:
                raise ValueError(f"Unknown public benchmark source {source!r}")
            if sample_id in seen:
                raise ValueError(f"Duplicate public benchmark sample ID: {sample_id}")
            seen.add(sample_id)
            samples.append(value)
        return samples, {"source_rows": len(rows), "excluded_rows": discarded}

    def load(self, context: DatasetLoadContext) -> DatasetLoadResult:
        path = single_cached_source(self.spec, context)
        columns = {
            "openai/gsm8k": ("question", "answer"),
            "rajpurkar/squad_v2": ("id", "title", "context", "question", "answers"),
            "epfl-dlab/JSONSchemaBench": ("json_schema", "unique_id"),
        }[self.spec.source]
        available, stats = self._convert(_rows(path, columns))
        selected = select_samples(
            available, dataset_id=self.spec.dataset_id, context=context
        )
        return DatasetLoadResult(
            spec=self.spec,
            samples=selected,
            available_count=len(available),
            selection_fingerprint=fingerprint_values([s.sample_id for s in selected]),
            source_checksums={"source": sha256_file(path)},
            metadata={
                **stats, "eligible_rows": len(available),
                "selection_strategy": str(context.selection.get("strategy") or "profile"),
                "source": self.spec.source,
                "source_revision": self.spec.revision,
                "source_split": self.spec.split,
                "license": self.spec.license_id,
                "subset": self.spec.options.get("subset"),
            },
        )
