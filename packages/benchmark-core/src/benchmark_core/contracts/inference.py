from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Literal

from benchmark_core.contracts.media import ContentPart, OutputArtifact

MessageRole = Literal["system", "user", "assistant", "tool"]
ErrorKind = Literal[
    "configuration",
    "authentication",
    "timeout",
    "transport",
    "invalid_response",
    "provider",
    "unknown",
]


@dataclass(frozen=True)
class InferenceMessage:
    role: MessageRole
    content: Any
    name: str | None = None


@dataclass(frozen=True)
class GenerationConfig:
    temperature: float | None = None
    max_output_tokens: int | None = None
    seed: int | None = None
    stop: tuple[str, ...] = ()
    extra: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.temperature is not None and self.temperature < 0:
            raise ValueError("temperature must be >= 0")
        if self.max_output_tokens is not None and self.max_output_tokens <= 0:
            raise ValueError("max_output_tokens must be > 0")


@dataclass(frozen=True)
class TokenUsage:
    input_tokens: int | None = None
    cached_input_tokens: int | None = None
    output_tokens: int | None = None

    @property
    def total_tokens(self) -> int | None:
        if self.input_tokens is None and self.output_tokens is None:
            return None
        return (self.input_tokens or 0) + (self.output_tokens or 0)


@dataclass(frozen=True)
class InferenceError:
    kind: ErrorKind
    message: str
    retryable: bool = False
    details: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class InferenceRequest:
    request_id: str
    input: Any = None
    messages: tuple[InferenceMessage, ...] = ()
    content: tuple[ContentPart, ...] = ()
    system_prompt: str | None = None
    response_schema: Mapping[str, Any] | None = None
    generation: GenerationConfig = field(default_factory=GenerationConfig)
    task_metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.request_id.strip():
            raise ValueError("request_id must not be empty")
        if self.input is None and not self.messages and not self.content:
            raise ValueError("an inference request requires input, messages, or content")


@dataclass(frozen=True)
class InferenceResult:
    provider_id: str
    model_id: str
    raw_output: Any
    latency_ms: float
    normalized_output: Any = None
    output_artifacts: tuple[OutputArtifact, ...] = ()
    usage: TokenUsage = field(default_factory=TokenUsage)
    estimated_cost_usd: float | None = None
    valid: bool = True
    error: InferenceError | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.provider_id.strip():
            raise ValueError("provider_id must not be empty")
        if not self.model_id.strip():
            raise ValueError("model_id must not be empty")
        if self.latency_ms < 0:
            raise ValueError("latency_ms must be >= 0")
        if not self.valid and self.error is None:
            raise ValueError("invalid inference results require a typed error")
