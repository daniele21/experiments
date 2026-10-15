from __future__ import annotations

import time
from collections.abc import Mapping
from typing import Any

from benchmark_core import (
    InferenceError,
    InferenceProvider,
    InferenceRequest,
    InferenceResult,
    ResolvedModel,
    TokenUsage,
)

from model_capability_bench.providers.parsing import parse_chat_response_content


class TransformersLocalProvider(InferenceProvider):
    """In-process inference provider powered by Hugging Face Transformers and PyTorch.

    Executes models directly without requiring external inference daemons or network ports.
    Automatically detects Apple Silicon Metal (MPS), NVIDIA CUDA, or CPU fallback.
    """

    def __init__(
        self,
        resolved: ResolvedModel,
        environ: Mapping[str, str] | None = None,
    ) -> None:
        self.resolved = resolved
        self.environ = dict(environ or {})
        self.model_id = resolved.model.model_id
        self.provider_id = resolved.provider.provider_key
        self._model: Any = None
        self._tokenizer: Any = None

    def _apply_memory_caps(self, torch: Any, target_device: str) -> None:
        """Applies hardware/allocator-level memory caps to prevent RAM/VRAM saturation."""
        if target_device == "mps" and torch.backends.mps.is_available():
            configured_gb = self.resolved.model.metadata.get(
                "max_memory_gb",
                self.environ.get("BENCH_MAX_MEMORY_GB"),
            )
            configured_fraction = self.resolved.model.metadata.get(
                "memory_fraction",
                self.environ.get("BENCH_MEMORY_FRACTION"),
            )

            if hasattr(torch.mps, "set_per_process_memory_fraction"):
                rec_bytes = (
                    torch.mps.recommended_max_memory()
                    if hasattr(torch.mps, "recommended_max_memory")
                    else (32 * 1024**3)
                )
                if configured_gb is not None:
                    target_bytes = float(configured_gb) * (1024**3)
                    fraction = min(max(target_bytes / max(rec_bytes, 1), 0.05), 1.0)
                elif configured_fraction is not None:
                    fraction = min(max(float(configured_fraction), 0.05), 1.0)
                else:
                    # Default: 4.0 GB cap for small in-process local models (e.g. 1B)
                    target_bytes = 4.0 * (1024**3)
                    fraction = min(max(target_bytes / max(rec_bytes, 1), 0.05), 1.0)

                torch.mps.set_per_process_memory_fraction(fraction)

        elif target_device == "cuda" and torch.cuda.is_available():
            cuda_fraction = float(
                self.resolved.model.metadata.get(
                    "cuda_memory_fraction",
                    self.environ.get("BENCH_CUDA_MEMORY_FRACTION", 0.8),
                )
            )
            if hasattr(torch.cuda, "set_per_process_memory_fraction"):
                torch.cuda.set_per_process_memory_fraction(cuda_fraction)

    def _ensure_loaded(self) -> tuple[Any, Any]:
        """Lazy-loads and caches model and tokenizer in memory/VRAM once per provider instance."""
        if self._model is not None and self._tokenizer is not None:
            return self._model, self._tokenizer

        import gc
        import os

        # 1. Enforce memory watermark ratios on Apple Silicon MPS before PyTorch initializes Metal
        high_ratio = str(
            self.resolved.model.metadata.get(
                "mps_high_watermark_ratio",
                self.environ.get("PYTORCH_MPS_HIGH_WATERMARK_RATIO", "0.3"),
            )
        )
        low_ratio = str(
            self.resolved.model.metadata.get(
                "mps_low_watermark_ratio",
                self.environ.get("PYTORCH_MPS_LOW_WATERMARK_RATIO", "0.1"),
            )
        )
        os.environ["PYTORCH_MPS_LOW_WATERMARK_RATIO"] = low_ratio
        os.environ["PYTORCH_MPS_HIGH_WATERMARK_RATIO"] = high_ratio

        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        # 2. Device selection: CUDA -> Apple Silicon MPS -> CPU
        # Note: Limite architecture requires a single explicit device per replica (disallows device_map='auto')
        if torch.cuda.is_available():
            target_device = "cuda"
            dtype = torch.bfloat16
        elif torch.backends.mps.is_available():
            target_device = "mps"
            dtype = torch.bfloat16
        else:
            target_device = "cpu"
            dtype = torch.float32

        metadata_device = self.resolved.model.metadata.get("device")
        if metadata_device:
            target_device = metadata_device

        # 3. Apply device-level hardware memory caps
        self._apply_memory_caps(torch, target_device)

        self._tokenizer = AutoTokenizer.from_pretrained(
            self.model_id,
            trust_remote_code=True,
        )
        self._model = AutoModelForCausalLM.from_pretrained(
            self.model_id,
            trust_remote_code=True,
            dtype=dtype,
            low_cpu_mem_usage=True,
        ).to(target_device)

        if target_device == "mps" and torch.backends.mps.is_available():
            torch.mps.empty_cache()
        elif target_device == "cuda" and torch.cuda.is_available():
            torch.cuda.empty_cache()
        gc.collect()

        return self._model, self._tokenizer

    def generate(self, request: InferenceRequest) -> InferenceResult:
        started = time.perf_counter()
        try:
            model, tokenizer = self._ensure_loaded()
            import torch

            # 1. Format user messages (Limite chat template auto-injects its canonical system prompt)
            messages: list[dict[str, str]] = []
            for msg in request.messages:
                if msg.role != "system":
                    messages.append({"role": msg.role, "content": str(msg.content)})

            messages.append({"role": "user", "content": str(request.input)})

            prompt_text = tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
            )

            inputs = tokenizer([prompt_text], return_tensors="pt").to(model.device)
            prompt_tokens = inputs.input_ids.shape[1]

            # 2. Determine sampling parameters
            model_default_max = self.resolved.model.metadata.get(
                "default_max_output_tokens", 512
            )
            if (
                request.generation.max_output_tokens
                and request.generation.max_output_tokens > 256
            ):
                max_new_tokens = request.generation.max_output_tokens
            else:
                max_new_tokens = int(model_default_max)

            model_default_temp = self.resolved.model.metadata.get("default_temperature", 0.6)
            model_default_top_p = self.resolved.model.metadata.get("default_top_p", 0.95)

            # Prioritize model-recommended temperature unless overridden by explicit config
            if (
                request.generation.temperature is None
                or request.generation.temperature == 0.0
            ):
                temperature = float(model_default_temp)
            else:
                temperature = float(request.generation.temperature)

            if request.generation.extra and "top_p" in request.generation.extra:
                top_p = float(request.generation.extra["top_p"])
            else:
                top_p = float(model_default_top_p)

            if request.generation.seed is not None:
                torch.manual_seed(request.generation.seed)

            # 3. Model generation
            with torch.inference_mode():
                output_ids = model.generate(
                    **inputs,
                    max_new_tokens=max_new_tokens,
                    do_sample=True,
                    temperature=temperature,
                    top_p=top_p,
                )

            # 4. Decode newly generated tokens
            completion_ids = output_ids[0, prompt_tokens:]
            completion_tokens = len(completion_ids)
            raw_text = tokenizer.decode(completion_ids, skip_special_tokens=True)

            # Eagerly free GPU/Metal tensors and clear activation cache
            del inputs
            del output_ids
            if torch.backends.mps.is_available():
                torch.mps.empty_cache()
            elif torch.cuda.is_available():
                torch.cuda.empty_cache()

            # 5. Extract structured output
            output_format = self.resolved.model.metadata.get("output_format")
            parsed = parse_chat_response_content(
                raw_text,
                response_schema=request.response_schema,
                output_format=output_format,
            )

            latency_ms = (time.perf_counter() - started) * 1000
            return InferenceResult(
                provider_id=self.provider_id,
                model_id=self.model_id,
                raw_output=raw_text,
                latency_ms=latency_ms,
                normalized_output=parsed,
                valid=parsed is not None,
                usage=TokenUsage(
                    input_tokens=prompt_tokens,
                    output_tokens=completion_tokens,
                ),
                metadata={
                    "protocol": "transformers-pipeline",
                    "device": str(model.device),
                },
            )
        except Exception as exc:  # noqa: BLE001 - provider boundary normalizes evidence
            latency_ms = (time.perf_counter() - started) * 1000
            return InferenceResult(
                provider_id=self.provider_id,
                model_id=self.model_id,
                raw_output=None,
                latency_ms=latency_ms,
                normalized_output=None,
                valid=False,
                error=InferenceError(
                    kind="provider",
                    message=f"{exc.__class__.__name__}: {exc}",
                ),
                metadata={"protocol": "transformers-pipeline"},
            )

    def close(self) -> None:
        """Explicitly unloads model tensors and releases device memory back to OS."""
        self._model = None
        self._tokenizer = None
        try:
            import torch

            if torch.backends.mps.is_available():
                torch.mps.empty_cache()
            elif torch.cuda.is_available():
                torch.cuda.empty_cache()
        except ImportError:
            pass
        import gc

        gc.collect()
