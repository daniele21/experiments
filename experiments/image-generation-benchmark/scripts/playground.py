"""Local image-generation playground using the Experiments provider catalog.

The browser never sees provider credentials. One output is saved per request,
outside the benchmark result directories so exploratory prompts do not alter
the reproducible benchmark matrix.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Mapping

from benchmark_core import ArtifactStore, GenerationConfig, InferenceRequest, load_yaml_section

from imagegen_bench.config import ResolvedImageModel, resolve_image_models
from imagegen_bench.provider_factory import create_image_provider

ROOT = Path(__file__).resolve().parents[1]
MAX_PROMPT_LENGTH = 4000
MAX_SEED = (2**31) - 1
SUPPORTED_MIMES = {
    "image/png": ("png", b"\x89PNG\r\n\x1a\n"),
    "image/jpeg": ("jpg", b"\xff\xd8\xff"),
    "image/webp": ("webp", b"RIFF"),
}


def available_models(environ: Mapping[str, str]) -> list[dict[str, Any]]:
    """Generate select options from the existing benchmark model configuration."""
    configs = load_yaml_section(ROOT / "models.yaml", "models", required=True)
    resolved = resolve_image_models(ROOT, list(configs))
    options: list[dict[str, Any]] = []
    for model in resolved:
        is_local = model.provider_type == "korgis-image"
        if is_local:
            configured = bool(environ.get(model.base_url_env or "", "").strip())
        else:
            configured = bool(environ.get(model.api_key_env or "", "").strip())
        options.append({
            "key": model.model_key,
            "name": model.model_key.replace("-", " "),
            "model_id": model.model_id,
            "runtime": model.runtime_key,
            "kind": "local" if is_local else "cloud",
            "provider": model.provider_type,
            "generation": dict(model.generation),
            "seed_supported": is_local,
            "configured": configured,
            "setup_hint": (
                f"Set {model.base_url_env} and start Korgis locally"
                if is_local else f"Set {model.api_key_env} on the UI server"
            ) if not configured else None,
        })
    return options


def require_model(model_key: str, environ: Mapping[str, str]) -> ResolvedImageModel:
    if not isinstance(model_key, str) or not model_key:
        raise ValueError("Choose a model")
    model, = resolve_image_models(ROOT, [model_key])
    missing = model.base_url_env if model.provider_type == "korgis-image" else model.api_key_env
    if not missing or not environ.get(missing, "").strip():
        raise ValueError(f"{model_key} is not configured on the server (missing {missing})")
    return model


def validate(prompt: str, seed: int | None, model: ResolvedImageModel) -> None:
    if not isinstance(prompt, str) or not 1 <= len(prompt.strip()) <= MAX_PROMPT_LENGTH:
        raise ValueError(f"Prompt must be 1 to {MAX_PROMPT_LENGTH} characters")
    if seed is not None:
        if model.provider_type != "korgis-image":
            raise ValueError("Seed is supported only for the local Korgis engines")
        if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed <= MAX_SEED:
            raise ValueError(f"Seed must be an integer from 0 to {MAX_SEED}")


def generate(
    *,
    model_key: str,
    prompt: str,
    seed: int | None,
    output_root: Path,
    environ: Mapping[str, str],
    provider_builder: Any = create_image_provider,
) -> dict[str, Any]:
    model = require_model(model_key, environ)
    validate(prompt, seed, model)
    run_id = uuid.uuid4().hex
    folder = output_root / run_id
    folder.mkdir(parents=True, exist_ok=False)
    start = time.perf_counter()
    try:
        store = ArtifactStore(folder / "artifacts")
        provider = provider_builder(model, artifact_store=store, environ=environ)
        request = InferenceRequest(
            request_id=f"playground-{run_id}",
            input=prompt.strip(),
            generation=GenerationConfig(seed=seed),
        )
        result = provider.generate(request)
        if not result.valid or not result.output_artifacts:
            error = getattr(result, "error", None)
            raise RuntimeError(
                (str(getattr(error, "message", "")) if error else "")
                or "The selected engine returned no valid image"
            )
        artifact = result.output_artifacts[0]
        mime = str(artifact.mime_type or "").lower()
        if mime not in SUPPORTED_MIMES:
            raise ValueError(f"Unsupported image format: {mime}")
        extension, signature = SUPPORTED_MIMES[mime]
        source = Path(artifact.path)
        image_bytes = source.read_bytes()
        if not image_bytes.startswith(signature):
            raise ValueError("Provider response is not a valid image")
        digest = hashlib.sha256(image_bytes).hexdigest()
        image_name = f"image.{extension}"
        (folder / image_name).write_bytes(image_bytes)
        manifest = {
            "id": run_id,
            "model_key": model_key,
            "model_id": result.model_id,
            "provider": result.provider_id,
            "runtime": model.runtime_key,
            "kind": "local" if model.provider_type == "korgis-image" else "cloud",
            "prompt": prompt.strip(),
            "seed_requested": seed,
            "seed_effective": (result.metadata.get("korgis") or {}).get("seed")
                if isinstance(result.metadata, Mapping) else None,
            "generation": dict(model.generation),
            "mime_type": mime,
            "filename": image_name,
            "sha256": digest,
            "size_bytes": len(image_bytes),
            "latency_ms": float(result.latency_ms),
            "elapsed_ms": round((time.perf_counter() - start) * 1000, 1),
            "metadata": dict(result.metadata),
        }
        (folder / "result.json").write_text(json.dumps(manifest, default=str, indent=2))
        return {
            **{k: v for k, v in manifest.items() if k != "metadata"},
            "image_url": f"/api/playground/image?id={run_id}",
        }
    except Exception:
        # Do not leave incomplete result directories in the gallery.
        shutil.rmtree(folder, ignore_errors=True)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description="Experiments image playground backend")
    parser.add_argument("action", choices=["models", "generate"])
    parser.add_argument("--model", default="")
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--output-root", type=Path, default=ROOT / "playground-results")
    arguments = parser.parse_args()

    try:
        if arguments.action == "models":
            print(json.dumps({"models": available_models(os.environ)}))
            return 0
        payload = json.load(sys.stdin)
        if not isinstance(payload, dict):
            raise ValueError("Expected JSON request object")
        result = generate(
            model_key=arguments.model,
            prompt=payload.get("prompt"),
            seed=arguments.seed,
            output_root=arguments.output_root,
            environ=os.environ,
        )
        print(json.dumps(result, default=str))
        return 0
    except (ValueError, RuntimeError, OSError, KeyError) as exc:
        print(json.dumps({"error": str(exc)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
