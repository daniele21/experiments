from __future__ import annotations

import atexit
import json
import os
import subprocess
import time
from collections.abc import Mapping
from contextlib import suppress
from pathlib import Path
from typing import Any

from benchmark_core import (
    InferenceError,
    InferenceRequest,
    InferenceResult,
    ResolvedModel,
    TokenUsage,
    inference_error_from_exception,
)


class DecisioJsonProvider:
    provider_id = "decisio"

    def __init__(
        self,
        model: ResolvedModel,
        *,
        environ: Mapping[str, str],
        process: subprocess.Popen | None = None,
    ) -> None:
        self.resolved = model
        self.provider_id = model.provider.provider_key
        self.model_key = model.model.model_key
        options = dict(model.provider.options)

        if process is not None:
            self._proc = process
            return

        home = Path.home()
        candidate_roots = [
            environ.get("DECISIO_ROOT"),
            options.get("decisio_root"),
            home / "Personal" / "decisio",
            Path(__file__).resolve().parents[5] / "decisio" if len(Path(__file__).resolve().parents) > 5 else None,
        ]
        decisio_root = ""
        for cand in candidate_roots:
            if cand and Path(cand).is_dir():
                decisio_root = str(Path(cand).resolve())
                break
        if not decisio_root:
            decisio_root = str(home / "Personal" / "decisio")

        candidate_pythons = [
            environ.get("DECISIO_PYTHON"),
            options.get("decisio_python"),
            Path(decisio_root) / ".venv" / "bin" / "python",
        ]
        decisio_python = ""
        for cand in candidate_pythons:
            if cand and Path(cand).is_file():
                decisio_python = str(cand)
                break
        if not decisio_python:
            raise FileNotFoundError(
                f"Could not locate Decisio python interpreter in {decisio_root}. "
                "Specify DECISIO_PYTHON or DECISIO_ROOT."
            )

        device = str(
            environ.get("DECISIO_DEVICE")
            or options.get("device")
            or ("metal" if os.uname().sysname == "Darwin" else "cpu")
        )
        threads = str(
            environ.get("DECISIO_THREADS")
            or options.get("threads")
            or "4"
        )

        runtime_model_id = model.model.runtime_model_id or ""
        metadata_path = str(model.model.metadata.get("path") or "")
        effective_id = model.effective_model_id or ""

        gguf_path = ""
        for cand_path in (
            environ.get("DECISIO_MODEL_PATH"),
            runtime_model_id,
            metadata_path,
            effective_id,
        ):
            if cand_path and Path(cand_path).is_file():
                gguf_path = str(Path(cand_path).resolve())
                break

        if not gguf_path:
            # If not direct file, check standard LMStudio model directory
            lmstudio_dir = Path(environ.get("LMSTUDIO_MODELS_DIR") or (home / ".lmstudio" / "models"))
            candidates = [
                lmstudio_dir / "unsloth" / "Qwen3.5-2B-GGUF" / "Qwen3.5-2B-Q4_K_M.gguf"
                if "2b" in self.model_key
                else None,
                lmstudio_dir / "unsloth" / "Qwen3.5-4B-GGUF" / "Qwen3.5-4B-Q4_K_M.gguf"
                if "4b" in self.model_key
                else None,
                lmstudio_dir / "lmstudio-community" / "Qwen3.5-9B-GGUF" / "Qwen3.5-9B-Q4_K_M.gguf"
                if "9b" in self.model_key
                else None,
            ]
            for cand in candidates:
                if cand and cand.is_file():
                    gguf_path = str(cand.resolve())
                    break

        if not gguf_path:
            raise FileNotFoundError(
                f"Could not locate GGUF model file for {self.model_key!r}. "
                "Specify DECISIO_MODEL_PATH or ensure the model exists in LMStudio models dir."
            )

        worker_script = str(
            Path(__file__).resolve().parent / "decisio_worker.py"
        )

        self._proc = subprocess.Popen(
            [decisio_python, worker_script, decisio_root, gguf_path, device, threads],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        atexit.register(self.close)

        # Wait for worker ready
        if self._proc.stdout is None:
            raise RuntimeError("Failed to open stdout pipe to Decisio worker.")
        ready_line = self._proc.stdout.readline()
        try:
            ready_data = json.loads(ready_line)
            if ready_data.get("status") != "ready":
                raise RuntimeError(f"Unexpected worker startup output: {ready_line}")
        except Exception as exc:
            err = self._proc.stderr.read() if self._proc.stderr else ""
            self.close()
            raise RuntimeError(f"Decisio worker failed to start: {err or exc}") from exc

    def close(self) -> None:
        if hasattr(self, "_proc") and self._proc is not None:
            with suppress(Exception):
                if self._proc.stdin:
                    self._proc.stdin.close()
                self._proc.terminate()
                self._proc.wait(timeout=2)
            self._proc = None


    def generate(self, request: InferenceRequest) -> InferenceResult:
        started = time.perf_counter()
        try:
            if self._proc is None or self._proc.poll() is not None:
                raise RuntimeError("Decisio worker process is not running.")

            schema = request.response_schema or {}
            properties = (
                schema.get("properties")
                if isinstance(schema, Mapping)
                else None
            )
            if not properties or not isinstance(properties, Mapping):
                raise ValueError(
                    "Decisio only supports classification tasks with a defined response schema."
                )

            enum_field = None
            enum_values = None
            for key, prop in properties.items():
                if isinstance(prop, Mapping) and "enum" in prop:
                    enum_field = key
                    enum_values = prop["enum"]
                    break

            if enum_field is None or not enum_values:
                raise ValueError(
                    f"Decisio requires a discrete choice/enum field in response schema. Found: {list(properties.keys())}"
                )

            state: dict[str, Any]
            if isinstance(request.input, Mapping):
                state = dict(request.input)
            elif isinstance(request.input, str):
                state = {"text": request.input}
            else:
                state = {"input": request.input}

            seen_descriptions: set[str] = set()
            candidates: list[list[str]] = []
            for val in enum_values:
                val_str = str(val)
                desc = val_str.replace("_", " ").strip()
                if not desc:
                    desc = val_str
                if desc in seen_descriptions:
                    desc = f"{desc} ({val_str})"
                seen_descriptions.add(desc)
                candidates.append([val_str, desc])

            payload = {
                "request_id": request.request_id,
                "state": state,
                "question": request.system_prompt or "Classify customer intent",
                "candidates": candidates,
            }

            assert self._proc.stdin is not None
            assert self._proc.stdout is not None
            self._proc.stdin.write(json.dumps(payload) + "\n")
            self._proc.stdin.flush()

            resp_line = self._proc.stdout.readline()
            if not resp_line:
                raise RuntimeError("Decisio worker returned empty response.")

            resp_data = json.loads(resp_line)
            if "error" in resp_data:
                raise RuntimeError(resp_data["error"])

            choice = resp_data.get("choice")
            valid = bool(resp_data.get("valid", True) and choice is not None)
            if not valid:
                raise ValueError(
                    f"Decisio returned invalid choice: {resp_data.get('error') or 'null choice'}"
                )

            latency_ms = float(resp_data.get("latency_ms") or ((time.perf_counter() - started) * 1000))
            generated_tokens = int(resp_data.get("generated_tokens") or 0)

            normalized: dict[str, Any] = {enum_field: choice}
            # For calibrated tasks (like oos-calibration), provide standard decision confidence
            if "confidence" in properties:
                normalized["confidence"] = 0.90 if choice not in {"other", "out_of_scope"} else 0.50

            return InferenceResult(
                provider_id=self.provider_id,
                model_id=self.model_key,
                raw_output=resp_data,
                normalized_output=normalized,
                latency_ms=latency_ms,
                usage=TokenUsage(
                    input_tokens=None,
                    cached_input_tokens=0,
                    output_tokens=generated_tokens,
                ),
                estimated_cost_usd=0.0,
                metadata={"protocol": "decisio-engine"},
            )
        except Exception as exc:  # noqa: BLE001
            error = inference_error_from_exception(exc)
            if error.kind == "unknown":
                error = InferenceError(
                    kind="provider",
                    message=error.message,
                    retryable=False,
                )
            return InferenceResult(
                provider_id=self.provider_id,
                model_id=self.model_key,
                raw_output=None,
                normalized_output=None,
                latency_ms=(time.perf_counter() - started) * 1000,
                valid=False,
                error=error,
                estimated_cost_usd=0.0,
                metadata={"protocol": "decisio-engine"},
            )
