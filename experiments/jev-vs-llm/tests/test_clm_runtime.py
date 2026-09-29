from __future__ import annotations

from pathlib import Path

import pytest

from jev_bench.clm_runtime import (
    CLMLocalRuntimeManager,
    CLMLocalRuntimeSpec,
    load_clm_runtime_spec,
)


def _spec() -> CLMLocalRuntimeSpec:
    return CLMLocalRuntimeSpec(
        runtime_id="clm-v0.1-8b-q4km-outq2",
        benchmark_model_id="clm-v0.1-8b-q4km-outq2",
        served_model="clm-latest",
        head_model_id="Contrastive-LM/CLM-v0.1-8B",
        head_checkpoint_env="CLM_CKPT",
        encoder_model_id="czl/CLM-v0.1-8B-GGUF",
        encoder_filename="Qwen3-8B-Q4_K_M-outq2.gguf",
        encoder_path_env="CLM_ENCODER_GGUF",
        encoder_format="gguf",
        encoder_quantization="Q4_K_M",
        output_weight_quantization="Q2_K",
        encoder_backend="llama-server",
        encoder_alias="qwen3-8b",
        pooling="last",
        context_size=8192,
        parallel=4,
        max_tokens=2048,
        encoder_host="127.0.0.1",
        encoder_port=8090,
        clm_host="127.0.0.1",
        clm_port=8700,
        tags=("clm", "local"),
    )


def test_runtime_registry_loads_expected_q4_outq2_contract(tmp_path: Path):
    config = tmp_path / "clm_runtimes.yaml"
    config.write_text(
        """
runtimes:
  clm-v0.1-8b-q4km-outq2:
    served_model: clm-latest
    head:
      model_id: Contrastive-LM/CLM-v0.1-8B
      checkpoint_env: CLM_CKPT
    encoder:
      model_id: czl/CLM-v0.1-8B-GGUF
      filename: Qwen3-8B-Q4_K_M-outq2.gguf
      path_env: CLM_ENCODER_GGUF
      format: gguf
      quantization: Q4_K_M
      output_weight_quantization: Q2_K
      backend: llama-server
      alias: qwen3-8b
      pooling: last
      context_size: 8192
      parallel: 4
    clm:
      max_tokens: 2048
      encoder_port: 8090
      port: 8700
""",
        encoding="utf-8",
    )

    spec = load_clm_runtime_spec(config, "clm-v0.1-8b-q4km-outq2")

    assert spec.benchmark_model_id == "clm-v0.1-8b-q4km-outq2"
    assert spec.served_model == "clm-latest"
    assert spec.encoder_filename == "Qwen3-8B-Q4_K_M-outq2.gguf"
    assert spec.encoder_quantization == "Q4_K_M"
    assert spec.output_weight_quantization == "Q2_K"
    assert spec.pooling == "last"
    assert spec.context_size == spec.parallel * spec.max_tokens


def test_runtime_registry_rejects_context_smaller_than_parallel_slots():
    payload = {
        "served_model": "clm-latest",
        "head": {"model_id": "Contrastive-LM/CLM-v0.1-8B"},
        "encoder": {
            "model_id": "czl/CLM-v0.1-8B-GGUF",
            "filename": "Qwen3-8B-Q4_K_M-outq2.gguf",
            "quantization": "Q4_K_M",
            "pooling": "last",
            "context_size": 2048,
            "parallel": 4,
        },
        "clm": {"max_tokens": 2048},
    }

    with pytest.raises(ValueError, match="parallel \* max_tokens"):
        CLMLocalRuntimeSpec.from_mapping("bad-runtime", payload)


def test_managed_runtime_builds_pooling_encoder_and_clm_commands(tmp_path: Path):
    spec = _spec()
    encoder = tmp_path / spec.encoder_filename
    encoder.write_bytes(b"fixture")
    checkpoint = tmp_path / "CLM_v0.1-8B.pt"
    checkpoint.write_bytes(b"fixture")
    manager = CLMLocalRuntimeManager(spec, encoder_path=encoder)

    encoder_command = manager.encoder_command(
        encoder_path=encoder,
        llama_server_bin="/usr/local/bin/llama-server",
    )
    clm_command = manager.clm_command(
        clm_serve_bin="/usr/local/bin/clm-serve",
        checkpoint=checkpoint,
    )

    assert encoder_command[:3] == [
        "/usr/local/bin/llama-server",
        "--model",
        str(encoder),
    ]
    assert "--embedding" in encoder_command
    assert encoder_command[encoder_command.index("--pooling") + 1] == "last"
    assert encoder_command[encoder_command.index("--alias") + 1] == "qwen3-8b"
    assert encoder_command[encoder_command.index("--ctx-size") + 1] == "8192"
    assert encoder_command[encoder_command.index("--parallel") + 1] == "4"

    assert clm_command[0] == "/usr/local/bin/clm-serve"
    assert clm_command[clm_command.index("--emb-url") + 1] == (
        "http://127.0.0.1:8090/v1/embeddings"
    )
    assert clm_command[clm_command.index("--emb-model") + 1] == "qwen3-8b"
    assert clm_command[clm_command.index("--max-tokens") + 1] == "2048"
    assert clm_command[clm_command.index("--ckpt") + 1] == str(checkpoint)
    assert "--no-ui" in clm_command


def test_managed_runtime_requires_exact_registered_artifact_filename(tmp_path: Path):
    wrong = tmp_path / "Qwen3-8B-Q4_K_M.gguf"
    wrong.write_bytes(b"fixture")
    manager = CLMLocalRuntimeManager(_spec(), encoder_path=wrong)

    with pytest.raises(RuntimeError, match="expects"):
        manager.identity()
