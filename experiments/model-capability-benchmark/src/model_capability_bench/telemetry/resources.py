from __future__ import annotations

import dataclasses
import threading
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from benchmark_core import InferenceProvider, InferenceRequest, InferenceResult

_RESOURCE_SOURCE = "korgis:/api/v1/resources"


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _metric_value(value: Any) -> tuple[float | None, str]:
    if not isinstance(value, Mapping):
        return None, "unavailable"
    return _number(value.get("value")), str(value.get("source") or "unavailable")


@dataclass(frozen=True)
class ResourceSample:
    captured_at_utc: str
    captured_at_monotonic: float
    runtime_key: str
    model_id: str
    backend: str
    scope: str
    process_rss_bytes: float | None
    process_cpu_seconds: float | None
    system_total_memory_bytes: float | None
    system_available_memory_bytes: float | None
    accelerator_memory_bytes: float | None
    sources: Mapping[str, str]
    platform: str | None = None

    def to_record(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


@dataclass(frozen=True)
class ResourceSummary:
    source: str
    scope: str
    sample_count: int
    sample_interval_ms: float | None
    process_cpu_percent_avg: float | None
    process_rss_bytes_avg: float | None
    process_rss_bytes_peak: float | None
    system_available_memory_bytes_min: float | None
    accelerator_memory_bytes_peak: float | None
    sampling_error_count: int = 0

    def to_record(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


def parse_korgis_resource_sample(
    payload: Mapping[str, Any],
    *,
    runtime_aliases: Sequence[str],
) -> ResourceSample | None:
    observation = payload.get("observation")
    if not isinstance(observation, Mapping):
        return None
    runtimes = observation.get("runtimes")
    if not isinstance(runtimes, list):
        return None

    aliases = {str(value) for value in runtime_aliases if str(value)}
    runtime: Mapping[str, Any] | None = None
    for candidate in runtimes:
        if not isinstance(candidate, Mapping):
            continue
        if {
            str(candidate.get("runtime_key") or ""),
            str(candidate.get("model_id") or ""),
        } & aliases:
            runtime = candidate
            break
    if runtime is None:
        return None

    system = observation.get("system")
    if not isinstance(system, Mapping):
        system = {}

    rss, rss_source = _metric_value(runtime.get("process_rss_bytes"))
    cpu, cpu_source = _metric_value(runtime.get("process_cpu_seconds"))
    total, total_source = _metric_value(system.get("total_memory_bytes"))
    available, available_source = _metric_value(system.get("available_memory_bytes"))
    accelerator, accelerator_source = _metric_value(
        system.get("accelerator_memory_bytes")
    )
    captured_monotonic = _number(observation.get("captured_at_monotonic"))
    if captured_monotonic is None:
        return None

    return ResourceSample(
        captured_at_utc=str(observation.get("captured_at_utc") or ""),
        captured_at_monotonic=captured_monotonic,
        runtime_key=str(runtime.get("runtime_key") or ""),
        model_id=str(runtime.get("model_id") or ""),
        backend=str(runtime.get("backend") or ""),
        scope=str(runtime.get("scope") or "unavailable"),
        process_rss_bytes=rss,
        process_cpu_seconds=cpu,
        system_total_memory_bytes=total,
        system_available_memory_bytes=available,
        accelerator_memory_bytes=accelerator,
        sources={
            "process_rss_bytes": rss_source,
            "process_cpu_seconds": cpu_source,
            "system_total_memory_bytes": total_source,
            "system_available_memory_bytes": available_source,
            "accelerator_memory_bytes": accelerator_source,
        },
        platform=str(observation["platform"]) if observation.get("platform") else None,
    )


def summarize_resource_samples(
    samples: Sequence[ResourceSample],
    *,
    sampling_error_count: int = 0,
) -> ResourceSummary:
    ordered = sorted(samples, key=lambda sample: sample.captured_at_monotonic)
    if not ordered:
        return ResourceSummary(
            source=_RESOURCE_SOURCE,
            scope="unavailable",
            sample_count=0,
            sample_interval_ms=None,
            process_cpu_percent_avg=None,
            process_rss_bytes_avg=None,
            process_rss_bytes_peak=None,
            system_available_memory_bytes_min=None,
            accelerator_memory_bytes_peak=None,
            sampling_error_count=sampling_error_count,
        )

    duration_seconds = (
        ordered[-1].captured_at_monotonic - ordered[0].captured_at_monotonic
    )
    cpu_percent = None
    first_cpu = ordered[0].process_cpu_seconds
    last_cpu = ordered[-1].process_cpu_seconds
    if (
        duration_seconds > 0
        and first_cpu is not None
        and last_cpu is not None
        and last_cpu >= first_cpu
    ):
        cpu_percent = ((last_cpu - first_cpu) / duration_seconds) * 100.0

    rss = [sample.process_rss_bytes for sample in ordered if sample.process_rss_bytes is not None]
    available = [
        sample.system_available_memory_bytes
        for sample in ordered
        if sample.system_available_memory_bytes is not None
    ]
    accelerator = [
        sample.accelerator_memory_bytes
        for sample in ordered
        if sample.accelerator_memory_bytes is not None
    ]
    interval_ms = (
        duration_seconds * 1000.0 / (len(ordered) - 1)
        if len(ordered) > 1 and duration_seconds >= 0
        else None
    )
    scopes = {sample.scope for sample in ordered}
    return ResourceSummary(
        source=_RESOURCE_SOURCE,
        scope=next(iter(scopes)) if len(scopes) == 1 else "mixed",
        sample_count=len(ordered),
        sample_interval_ms=interval_ms,
        process_cpu_percent_avg=cpu_percent,
        process_rss_bytes_avg=(sum(rss) / len(rss)) if rss else None,
        process_rss_bytes_peak=max(rss) if rss else None,
        system_available_memory_bytes_min=min(available) if available else None,
        accelerator_memory_bytes_peak=max(accelerator) if accelerator else None,
        sampling_error_count=sampling_error_count,
    )


class ResourceTelemetrySampler:
    def __init__(
        self,
        *,
        fetch: Callable[[], Mapping[str, Any]],
        runtime_aliases: Sequence[str],
        interval_seconds: float,
    ) -> None:
        if interval_seconds <= 0:
            raise ValueError("interval_seconds must be > 0")
        self.fetch = fetch
        self.runtime_aliases = tuple(runtime_aliases)
        self.interval_seconds = interval_seconds
        self.samples: list[ResourceSample] = []
        self.error_count = 0
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def _capture(self) -> None:
        try:
            payload = self.fetch()
            sample = parse_korgis_resource_sample(
                payload,
                runtime_aliases=self.runtime_aliases,
            )
            if sample is not None:
                self.samples.append(sample)
        except Exception:  # noqa: BLE001 - optional telemetry must never fail inference
            self.error_count += 1

    def start(self) -> None:
        self._capture()

        def poll() -> None:
            while not self._stop.wait(self.interval_seconds):
                self._capture()

        self._thread = threading.Thread(
            target=poll,
            name="mcb-resource-sampler",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=max(1.0, self.interval_seconds * 2))
        self._capture()


def resource_telemetry_payload(
    samples: Sequence[ResourceSample],
    *,
    sampling_error_count: int = 0,
) -> dict[str, Any]:
    summary = summarize_resource_samples(
        samples,
        sampling_error_count=sampling_error_count,
    )
    return {
        "schema_version": "1",
        "samples": [sample.to_record() for sample in samples],
        "summary": summary.to_record(),
    }


class ResourceSamplingProvider:
    def __init__(
        self,
        delegate: InferenceProvider,
        *,
        fetch: Callable[[], Mapping[str, Any]],
        runtime_aliases: Sequence[str],
        interval_seconds: float = 0.25,
    ) -> None:
        self.delegate = delegate
        self.provider_id = delegate.provider_id
        self.fetch = fetch
        self.runtime_aliases = tuple(runtime_aliases)
        self.interval_seconds = interval_seconds

    def generate(self, request: InferenceRequest) -> InferenceResult:
        sampler = ResourceTelemetrySampler(
            fetch=self.fetch,
            runtime_aliases=self.runtime_aliases,
            interval_seconds=self.interval_seconds,
        )
        sampler.start()
        try:
            result = self.delegate.generate(request)
        finally:
            sampler.stop()

        metadata = dict(result.metadata)
        metadata["resource_telemetry"] = resource_telemetry_payload(
            sampler.samples,
            sampling_error_count=sampler.error_count,
        )
        return dataclasses.replace(result, metadata=metadata)
