"""Schema compliance is distinct from semantic field extraction.

JSONSchemaBench contains schemas, not source texts with gold field values.
Therefore only validity against the upstream schema is scored here; this
does not attempt to reproduce the official JSONSchemaBench harness score.
"""
from __future__ import annotations

import json
from collections.abc import Mapping

from benchmark_core import (
    InferenceRequest,
    InferenceResult,
    MetricResult,
    Sample,
    TaskExecutionContext,
    TaskResult,
    TaskSpec,
)
from jsonschema.validators import validator_for


class JsonSchemaComplianceTask:
    def __init__(self, spec: TaskSpec) -> None:
        self._spec = spec

    @property
    def spec(self) -> TaskSpec:
        return self._spec

    def _schema(self, sample: Sample) -> Mapping:
        schema = sample.metadata.get("response_schema")
        if not isinstance(schema, Mapping):
            raise ValueError(f"{sample.sample_id}: missing response_schema")
        validator_for(schema).check_schema(schema)
        return schema

    def build_request(
        self, sample: Sample, context: TaskExecutionContext
    ) -> InferenceRequest:
        schema = self._schema(sample)
        return InferenceRequest(
            request_id=f"{context.run_id}:{self.spec.task_id}:{sample.sample_id}",
            input=sample.input,
            system_prompt=str(self.spec.options.get("instruction") or
                              "Return only a JSON object conforming to the schema."),
            response_schema=schema,
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
        self, sample: Sample, inference: InferenceResult,
        context: TaskExecutionContext,
    ) -> TaskResult:
        prediction = inference.normalized_output
        if isinstance(prediction, str):
            try:
                prediction = json.loads(prediction)
            except json.JSONDecodeError:
                pass
        parse_valid = isinstance(prediction, dict)
        schema = self._schema(sample)
        schema_valid = bool(
            inference.valid
            and parse_valid
            and validator_for(schema)(schema).is_valid(prediction)
        )
        error = inference.error.message if inference.error else None
        if inference.valid and not parse_valid:
            error = "normalized output must be a JSON object"
        return TaskResult(
            task_id=self.spec.task_id,
            sample_id=sample.sample_id,
            prediction=prediction,
            expected=None,
            metrics=(
                MetricResult(name="schema_valid_rate", value=float(schema_valid), primary=True),
                MetricResult(name="parse_valid", value=float(inference.valid and parse_valid)),
            ),
            valid=bool(inference.valid and parse_valid),
            error=error,
            metadata={"dataset_id": context.dataset_id,
                      "schema_compliance_only": True},
        )
