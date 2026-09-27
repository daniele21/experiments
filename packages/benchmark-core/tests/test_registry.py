from __future__ import annotations

from pathlib import Path

import pytest

from benchmark_core import (
    RegistryError,
    load_registry,
    preflight_models,
    registry_summary,
)


def _write_registry(path: Path) -> None:
    path.write_text(
        """
providers:
  local-provider:
    type: openai-compatible
    base_url_env: LOCAL_BASE_URL
    required_env: [LOCAL_BASE_URL]
  api-provider:
    type: openai
    api_key_env: API_KEY
    required_env: [API_KEY]

runtimes:
  local-runtime:
    provider: local-provider
    deployment: local
    lifecycle: managed
  api-runtime:
    provider: api-provider
    deployment: api
    lifecycle: external

models:
  local-small:
    model_id: vendor/local-small
    runtime_model_id: local-small-q4
    runtime: local-runtime
    family: local-family
    parameters_b: 2
    artifact:
      format: gguf
      quantization: Q4_K_M
    tags: [local, small]
  api-model:
    model_id: provider/api-model
    runtime: api-runtime
    family: api-family
    tags: [api]
""".strip(),
        encoding="utf-8",
    )


def test_registry_resolves_model_runtime_provider_chain(tmp_path: Path) -> None:
    path = tmp_path / "models.yaml"
    _write_registry(path)

    registry = load_registry(path)
    local = registry.resolve("local-small")
    api = registry.resolve("api-model")

    assert local.model.model_id == "vendor/local-small"
    assert local.effective_model_id == "local-small-q4"
    assert local.runtime.runtime_key == "local-runtime"
    assert local.runtime.deployment == "local"
    assert local.provider.provider_key == "local-provider"

    assert api.effective_model_id == "provider/api-model"
    assert api.runtime.deployment == "api"
    assert api.provider.provider_key == "api-provider"

    assert registry_summary(registry) == {
        "providers": 2,
        "runtimes": 2,
        "models": 2,
        "deployments": ["api", "local"],
    }


def test_registry_selection_filters_without_runner_branches(tmp_path: Path) -> None:
    path = tmp_path / "models.yaml"
    _write_registry(path)
    registry = load_registry(path)

    selected = registry.select(
        tags=["local"],
        deployment="local",
        family="local-family",
        max_parameters_b=3,
        quantization="Q4_K_M",
    )

    assert [item.model.model_key for item in selected] == ["local-small"]


def test_registry_preflight_checks_only_selected_provider_dependencies(
    tmp_path: Path,
) -> None:
    path = tmp_path / "models.yaml"
    _write_registry(path)
    registry = load_registry(path)

    local = registry.select(model_keys=["local-small"])
    assert preflight_models(
        registry,
        local,
        {"LOCAL_BASE_URL": "http://127.0.0.1:1235/v1"},
    ).ok

    api = registry.select(model_keys=["api-model"])
    result = preflight_models(registry, api, {})

    assert result.ok is False
    assert len(result.issues) == 1
    assert result.issues[0].code == "missing_env"
    assert result.issues[0].env_var == "API_KEY"
    with pytest.raises(RegistryError, match="API_KEY"):
        result.raise_for_errors()


def test_registry_rejects_broken_references(tmp_path: Path) -> None:
    path = tmp_path / "broken.yaml"
    path.write_text(
        """
providers:
  provider-a:
    type: openai
runtimes:
  runtime-a:
    provider: missing-provider
    deployment: api
models:
  model-a:
    model_id: model-a
    runtime: runtime-a
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(RegistryError, match="unknown provider"):
        load_registry(path)


def test_runtime_contract_rejects_unknown_deployment(tmp_path: Path) -> None:
    path = tmp_path / "broken.yaml"
    path.write_text(
        """
providers:
  provider-a:
    type: openai
runtimes:
  runtime-a:
    provider: provider-a
    deployment: spaceship
models:
  model-a:
    model_id: model-a
    runtime: runtime-a
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Unsupported deployment"):
        load_registry(path)
