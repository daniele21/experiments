from __future__ import annotations

from benchmark_core import InferenceRequest, InferenceResult

from model_capability_bench.runner.evidence import EvidenceStore
from model_capability_bench.telemetry.resources import (
    ResourceSamplingProvider,
    parse_korgis_resource_sample,
    summarize_resource_samples,
)


def _payload(
    *,
    captured: float,
    rss: float,
    cpu: float,
) -> dict:
    return {
        "observation": {
            "platform": "darwin",
            "captured_at_utc": f"2026-10-05T08:00:{captured:02.0f}+00:00",
            "captured_at_monotonic": captured,
            "system": {
                "total_memory_bytes": {
                    "value": 16_000,
                    "source": "measured",
                    "unit": "bytes",
                },
                "available_memory_bytes": {
                    "value": 8_000 - captured,
                    "source": "measured",
                    "unit": "bytes",
                },
                "accelerator_memory_bytes": {
                    "value": None,
                    "source": "unavailable",
                    "unit": "bytes",
                },
            },
            "runtimes": [
                {
                    "runtime_key": "qwen-runtime",
                    "model_id": "vendor/qwen",
                    "backend": "llama_server",
                    "scope": "owned_backend_process",
                    "process_rss_bytes": {
                        "value": rss,
                        "source": "measured",
                        "unit": "bytes",
                    },
                    "process_cpu_seconds": {
                        "value": cpu,
                        "source": "measured",
                        "unit": "seconds",
                    },
                }
            ],
        }
    }


def test_resource_sample_parser_and_summary_preserve_measurement_semantics():
    first = parse_korgis_resource_sample(
        _payload(captured=10, rss=1000, cpu=2.0),
        runtime_aliases=("qwen-runtime",),
    )
    second = parse_korgis_resource_sample(
        _payload(captured=12, rss=1500, cpu=3.0),
        runtime_aliases=("qwen-runtime",),
    )

    assert first is not None and second is not None
    assert first.platform == "darwin"
    summary = summarize_resource_samples([first, second])

    assert summary.scope == "owned_backend_process"
    assert summary.sample_count == 2
    assert summary.process_cpu_percent_avg == 50.0
    assert summary.process_rss_bytes_avg == 1250
    assert summary.process_rss_bytes_peak == 1500
    assert summary.system_available_memory_bytes_min == 7988
    assert summary.accelerator_memory_bytes_peak is None


class _Delegate:
    provider_id = "fake"

    def generate(self, request):
        return InferenceResult(
            provider_id=self.provider_id,
            model_id="vendor/qwen",
            raw_output={"ok": True},
            normalized_output={"ok": True},
            latency_ms=10.0,
        )


def test_resource_sampling_provider_is_non_intrusive_and_persists_separate_evidence(
    tmp_path,
):
    payloads = iter(
        [
            _payload(captured=10, rss=1000, cpu=2.0),
            _payload(captured=12, rss=1500, cpu=3.0),
        ]
    )
    provider = ResourceSamplingProvider(
        _Delegate(),
        fetch=lambda: next(payloads),
        runtime_aliases=("qwen-runtime",),
        interval_seconds=60,
    )

    result = provider.generate(
        InferenceRequest(request_id="req-1", input="hello")
    )

    telemetry = result.metadata["resource_telemetry"]
    assert telemetry["summary"]["sample_count"] == 2
    assert telemetry["summary"]["process_rss_bytes_peak"] == 1500

    store = EvidenceStore(tmp_path)
    summary = store.record_resource_telemetry(
        "case-1",
        1,
        telemetry,
        metadata={
            "run_id": "run-1",
            "model_key": "qwen",
            "capability_id": "structured-output",
        },
    )

    assert summary["process_cpu_percent_avg"] == 50.0
    assert len(store.resource_samples_path.read_text().splitlines()) == 2
    assert len(store.resource_summary_path.read_text().splitlines()) == 1


def test_resource_sampling_provider_never_fails_inference_when_telemetry_is_unavailable():
    provider = ResourceSamplingProvider(
        _Delegate(),
        fetch=lambda: (_ for _ in ()).throw(RuntimeError("admin API disabled")),
        runtime_aliases=("qwen-runtime",),
        interval_seconds=60,
    )

    result = provider.generate(
        InferenceRequest(request_id="req-2", input="hello")
    )

    summary = result.metadata["resource_telemetry"]["summary"]
    assert result.valid is True
    assert summary["sample_count"] == 0
    assert summary["sampling_error_count"] == 2
