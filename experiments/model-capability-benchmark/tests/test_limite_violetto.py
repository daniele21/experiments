from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from benchmark_core import (
    GenerationConfig,
    InferenceRequest,
    load_registry,
    preflight_models,
)

from model_capability_bench import load_capability_suite
from model_capability_bench.providers import (
    build_inference_provider,
    extract_json_from_text,
    extract_last_boxed_answer,
    parse_chat_response_content,
)
from model_capability_bench.suite import CAPABILITY_ALIASES, resolve_capability_id

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "models.yaml"


def test_limite_violetto_registry_resolution() -> None:
    registry = load_registry(REGISTRY)

    # In-process transformers-local configuration (default)
    limite = registry.resolve("limite-1b-violetto")
    assert limite.model.model_id == "paradigma-inc/limite-1b-violetto"
    assert limite.model.family == "limite"
    assert limite.model.parameters_b == 1
    assert limite.runtime.deployment == "local"
    assert limite.runtime.runtime_key == "transformers-local"
    assert limite.provider.provider_key == "transformers"
    assert "mathematics" in limite.model.tags
    assert "reasoning" in limite.model.tags
    assert "in-process" in limite.model.tags
    assert limite.model.metadata.get("output_format") == "boxed"
    assert limite.model.metadata.get("raw_input") is True
    assert limite.model.metadata.get("supports_response_format") is False

    # Preflight should pass without requiring extra environment variables
    preflight = preflight_models(registry, [limite], {})
    assert preflight.ok is True

    # vLLM local serving configuration
    limite_vllm = registry.resolve("limite-1b-violetto-vllm")
    assert limite_vllm.runtime.runtime_key == "vllm-local"
    assert limite_vllm.provider.provider_key == "vllm"

    # Korgis GGUF local configuration
    korgis_limite = registry.resolve("limite-1b-violetto-q4km")
    assert korgis_limite.model.model_id == "paradigma-inc/limite-1b-violetto"
    assert korgis_limite.runtime.runtime_key == "korgis-local"
    assert korgis_limite.provider.provider_key == "korgis"
    assert korgis_limite.model.artifact is not None
    assert korgis_limite.model.artifact.format == "gguf"
    assert korgis_limite.model.artifact.quantization == "Q4_K_M"
    assert korgis_limite.model.artifact.metadata["source_repo"] == (
        "yamura4/limite-1b-violetto-GGUF"
    )


def test_boxed_answer_extraction() -> None:
    # Simple boxed integer
    assert extract_last_boxed_answer(r"The answer is \boxed{45}.") == "45"

    # Boxed with whitespace
    assert extract_last_boxed_answer(r"Result: \boxed{ 3150 }") == "3150"

    # Boxed formula with nested braces
    assert (
        extract_last_boxed_answer(r"Simplifying gives \boxed{\frac{12}{5}}.")
        == r"\frac{12}{5}"
    )

    # Multiple boxed answers (returns the final conclusive boxed answer)
    assert (
        extract_last_boxed_answer(
            r"First step: $x = \boxed{10}$. Final calculation gives \boxed{45}."
        )
        == "45"
    )

    # Text containing boxed without leading backslash
    assert extract_last_boxed_answer(r"Solution: boxed{42}") == "42"

    # None when no boxed pattern exists
    assert extract_last_boxed_answer("No answer enclosed.") is None


def test_json_and_fenced_markdown_extraction() -> None:
    # Direct JSON
    assert extract_json_from_text('{"answer": "45"}') == {"answer": "45"}

    # Fenced codeblock
    fenced = "```json\n{\n  \"answer\": \"45\"\n}\n```"
    assert extract_json_from_text(fenced) == {"answer": "45"}

    # JSON surrounded by explanatory text
    surrounded = "Here is the solution:\n{\"answer\": \"45\"}\nDone."
    assert extract_json_from_text(surrounded) == {"answer": "45"}


def test_parse_chat_response_content_with_schema() -> None:
    schema = {
        "type": "object",
        "properties": {"answer": {"type": "string"}},
        "required": ["answer"],
    }

    # Boxed response parsed into target schema field
    content = r"To solve this, we sum 28 + 17 = 45. \boxed{45}"
    assert parse_chat_response_content(content, response_schema=schema) == {
        "answer": "45"
    }

    # Direct JSON response
    assert parse_chat_response_content('{"answer": "45"}', response_schema=schema) == {
        "answer": "45"
    }


def test_limite_violetto_transformers_local_provider() -> None:
    bundle = load_capability_suite(ROOT)
    model = bundle.models.resolve("limite-1b-violetto")
    provider = build_inference_provider(model, {})

    calls = []

    class _MockTokenizer:
        def apply_chat_template(self, messages, tokenize=False, add_generation_prompt=True):
            calls.append(("template", messages))
            return "formatted prompt"

        def __call__(self, texts, return_tensors=None):
            class _Inputs(dict):
                def __init__(self):
                    super().__init__(input_ids=SimpleNamespace(shape=(1, 10)))
                    self.input_ids = self["input_ids"]

                def to(self, device):
                    return self

            return _Inputs()

        def decode(self, token_ids, skip_special_tokens=True):
            return r"We solve 28 + 17 = 45. \boxed{45}"

    class _MockModel:
        device = "cpu"

        def generate(self, **kwargs):
            calls.append(("generate", kwargs))
            import torch
            return torch.tensor([[0] * 10 + [1] * 5])

    provider._tokenizer = _MockTokenizer()
    provider._model = _MockModel()

    request = InferenceRequest(
        request_id="req-math-local",
        input="A box contains 28 red and 17 blue balls. How many balls total?",
        system_prompt="Solve the problem.",
        response_schema={"type": "object", "properties": {"answer": {"type": "string"}}},
        generation=GenerationConfig(temperature=0.0),
    )

    result = provider.generate(request)

    assert result.valid is True
    assert result.normalized_output == {"answer": "45"}
    assert result.usage.input_tokens == 10
    assert result.usage.output_tokens == 5

    # Verify template was called with user question (canonical system prompt is auto-injected by Jinja)
    _, messages = next(c for c in calls if c[0] == "template")
    assert messages[0]["role"] == "user"
    assert messages[0]["content"] == "A box contains 28 red and 17 blue balls. How many balls total?"

    # Verify sampling parameters: temperature=0.6, top_p=0.95
    _, gen_kwargs = next(c for c in calls if c[0] == "generate")
    assert gen_kwargs["temperature"] == 0.6
    assert gen_kwargs["top_p"] == 0.95
    assert gen_kwargs["do_sample"] is True


def test_limite_violetto_vllm_provider_call_and_generation(monkeypatch) -> None:
    from model_capability_bench.providers import openai_json

    calls = []

    class _MockOpenAI:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self.chat = SimpleNamespace(
                completions=SimpleNamespace(create=self._create)
            )

        def _create(self, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(
                            content=(
                                "Let the total number of items be $N$.\n"
                                "We compute $28 + 17 = 45$.\n"
                                r"Therefore, \boxed{45}"
                            )
                        )
                    ),
                ],
                usage=SimpleNamespace(prompt_tokens=32, completion_tokens=18),
                model_dump=lambda: {"kind": "chat"},
            )

    monkeypatch.setattr(openai_json, "OpenAI", _MockOpenAI)

    bundle = load_capability_suite(ROOT)
    model = bundle.models.resolve("limite-1b-violetto-vllm")
    provider = build_inference_provider(model, {})

    request = InferenceRequest(
        request_id="req-math-1",
        input="A box contains 28 red and 17 blue balls. How many balls total?",
        system_prompt="Solve the problem and return structured response.",
        response_schema={
            "type": "object",
            "properties": {"answer": {"type": "string"}},
            "required": ["answer"],
        },
        generation=GenerationConfig(temperature=0.0),
    )

    result = provider.generate(request)

    assert len(calls) == 1
    call = calls[0]
    assert call["model"] == "paradigma-inc/limite-1b-violetto"
    # Verify recommended sampling parameters for Limite: temperature=0.6, top_p=0.95
    assert call["temperature"] == 0.6
    assert call["top_p"] == 0.95
    # Verify response_format was omitted for boxed format
    assert "response_format" not in call
    # Verify raw input was used rather than JSON payload wrapper
    user_msg = next(m for m in call["messages"] if m["role"] == "user")
    assert user_msg["content"] == (
        "A box contains 28 red and 17 blue balls. How many balls total?"
    )
    # Verify canonical mathematical system prompt was used
    sys_msg = next(m for m in call["messages"] if m["role"] == "system")
    assert r"\boxed{}" in sys_msg["content"]

    # Verify output was extracted and normalized to schema field
    assert result.valid is True
    assert result.normalized_output == {"answer": "45"}

    # Verify explicit overrides take precedence (e.g. in parameter sweeps)
    request_sweep = InferenceRequest(
        request_id="req-math-2",
        input="What is 2 + 2?",
        system_prompt="Solve the problem.",
        response_schema={"type": "object", "properties": {"answer": {"type": "string"}}},
        generation=GenerationConfig(temperature=0.2, extra={"top_p": 0.8}),
    )
    provider.generate(request_sweep)
    call_sweep = calls[1]
    assert call_sweep["temperature"] == 0.2
    assert call_sweep["top_p"] == 0.8


def test_mathematics_capability_alias_resolution() -> None:
    assert resolve_capability_id("mathematics") == "mathematical-reasoning"
    assert resolve_capability_id("math") == "mathematical-reasoning"
    assert (
        resolve_capability_id("intent-classification")
        == "intent-classification"
    )

    bundle = load_capability_suite(ROOT)
    # Planning with alias "mathematics"
    arms = bundle.plan_matrix(
        model_keys=["limite-1b-violetto"],
        capability_ids=["mathematics"],
    )
    assert arms[0].dataset_id == "math-reasoning-controlled-v3"


def test_transformers_local_memory_capping_and_release() -> None:
    registry = load_registry(REGISTRY)
    resolved = registry.resolve("limite-1b-violetto")

    # Verify memory cap metadata
    assert resolved.model.metadata.get("max_memory_gb") == 4.0
    assert resolved.model.metadata.get("mps_high_watermark_ratio") == 0.3
    assert resolved.model.metadata.get("mps_low_watermark_ratio") == 0.1

    provider = build_inference_provider(resolved, {})
    assert hasattr(provider, "close")

    # Simulate loaded state
    provider._model = "fake_model"
    provider._tokenizer = "fake_tokenizer"
    assert provider._model is not None

    # Verify close frees model and tokenizer
    provider.close()
    assert provider._model is None
    assert provider._tokenizer is None

    # Test ExternalProviderRuntime release lifecycle
    from model_capability_bench.runtimes.external import ExternalProviderRuntime

    runtime = ExternalProviderRuntime(
        environ={},
        provider_builder=lambda r, env: provider,
    )
    p = runtime.prepare(resolved)
    assert p is provider
    p._model = "active_model"
    runtime.release(resolved)
    assert p._model is None
