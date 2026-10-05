from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from benchmark_core import (
    InferenceRequest,
    InferenceResult,
    MetricResult,
    Sample,
    TaskExecutionContext,
    TaskResult,
    TaskSpec,
)
from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError


class StructuredOutputTask:
    def __init__(self, spec: TaskSpec) -> None:
        self._spec = spec

    @property
    def spec(self) -> TaskSpec:
        return self._spec

    def _option(self, name: str) -> str:
        value = self.spec.options.get(name)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(
                f"Task {self.spec.task_id!r} requires non-empty option {name!r}"
            )
        return value

    def _response_schema(self, sample: Sample) -> Mapping[str, Any]:
        metadata_key = self._option("schema_metadata_key")
        schema = sample.metadata.get(metadata_key)
        if not isinstance(schema, Mapping) or not schema:
            raise ValueError(
                f"Sample {sample.sample_id!r} metadata {metadata_key!r} "
                "must contain a response schema"
            )
        try:
            Draft202012Validator.check_schema(schema)
        except SchemaError as exc:
            raise ValueError(
                f"Sample {sample.sample_id!r} contains an invalid response schema"
            ) from exc
        return schema

    def build_request(
        self,
        sample: Sample,
        context: TaskExecutionContext,
    ) -> InferenceRequest:
        return InferenceRequest(
            request_id=f"{context.run_id}:{self.spec.task_id}:{sample.sample_id}",
            input=sample.input,
            system_prompt=self._option("instruction"),
            response_schema=self._response_schema(sample),
            generation=context.generation,
            task_metadata={
                "task_id": self.spec.task_id,
                "task_version": self.spec.version,
                "prompt_id": self.spec.prompt_id,
                "prompt_version": self.spec.prompt_version,
                "dataset_id": context.dataset_id,
            },
        )

    def evaluate(
        self,
        sample: Sample,
        inference: InferenceResult,
        context: TaskExecutionContext,
    ) -> TaskResult:
        expected = sample.expected
        prediction = inference.normalized_output
        expected_mapping = expected if isinstance(expected, Mapping) else None
        prediction_mapping = prediction if isinstance(prediction, Mapping) else None
        schema = self._response_schema(sample)

        schema_valid = bool(
            inference.valid
            and prediction_mapping is not None
            and Draft202012Validator(schema).is_valid(prediction_mapping)
        )
        expected_fields = set(expected_mapping or {})
        predicted_fields = set(prediction_mapping or {})
        matching_fields = (
            sum(
                prediction_mapping.get(field) == expected_mapping.get(field)
                for field in expected_fields
            )
            if expected_mapping is not None and prediction_mapping is not None
            else 0
        )
        field_accuracy = (
            matching_fields / len(expected_fields)
            if expected_fields
            else float(schema_valid)
        )
        hallucinated_fields = len(predicted_fields - expected_fields)
        exact_match = bool(
            schema_valid
            and expected_mapping is not None
            and prediction_mapping is not None
            and matching_fields == len(expected_fields)
            and hallucinated_fields == 0
        )

        error = inference.error.message if inference.error is not None else None
        if inference.valid and prediction_mapping is None:
            error = "normalized output is not an object"
        if expected_mapping is None:
            error = "sample expected value is not an object"

        return TaskResult(
            task_id=self.spec.task_id,
            sample_id=sample.sample_id,
            prediction=prediction,
            expected=expected,
            metrics=(
                MetricResult(
                    name="exact_match",
                    value=float(exact_match),
                    primary=True,
                ),
                MetricResult(
                    name="schema_valid_rate",
                    value=float(schema_valid),
                ),
                MetricResult(name="field_accuracy", value=float(field_accuracy)),
                MetricResult(
                    name="hallucinated_fields",
                    value=hallucinated_fields,
                ),
            ),
            valid=schema_valid and expected_mapping is not None,
            error=error,
            metadata={"dataset_id": context.dataset_id},
        )
