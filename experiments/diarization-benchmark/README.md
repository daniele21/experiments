# Speaker Diarization Benchmark

A local-first benchmark for comparing open/open-weight speaker diarization systems that are plausible candidates for ClosedRoom and other Apple-Silicon meeting products.

The experiment follows the repository's existing benchmark style: declarative model registry, explicit dataset manifest, preflight/plan/run commands, immutable per-run evidence, deterministic metric tests, and a separate real-model execution boundary.

## Question

Which local diarization backend gives the best practical trade-off between speaker attribution quality and device efficiency for real meetings?

The benchmark deliberately does not collapse this into one winner score. A model can be preferable because of lower DER, better speaker-count behavior, higher overlap robustness, lower RTF, or lower memory pressure.

## Initial candidates

| Model key | Family | Max speakers | Mode | Why it is here |
|---|---|---:|---|---|
| community-1-vbx | Pyannote Community-1 + WeSpeaker + VBx | dynamic | offline | ClosedRoom-aligned baseline |
| sortformer-v2.1-balanced | NVIDIA Sortformer v2.1 | 4 | complete-buffer | stable identity, noise robustness |
| ls-eend-dihard3-500ms | LS-EEND | 10 | complete-buffer | overlap and larger meetings |
| nemotron3-fast32 | NVIDIA Nemotron 3 Diarization | 8 | complete-buffer | recommended general candidate |
| nemotron3-offline | NVIDIA Nemotron 3 Diarization | 8 | offline | quality ceiling / GPU-heavy challenger |

All inference is local. The Swift helper pins FluidAudio 0.17.5 and uses CoreML on macOS. Model files may be downloaded from their upstream registries on first use; no meeting audio is uploaded by this benchmark.

## Metrics

Primary metric:

- DER with collar = 0 seconds and overlap included.

Secondary metrics:

- JER;
- speaker-count exact rate and absolute error;
- miss, false-alarm and confusion speaker-seconds;
- model load time;
- inference RTF;
- end-to-end wall RTF;
- peak process RSS;
- process CPU seconds.

Results should also be sliced by meeting tags such as speaker band, overlap level, noise and capture topology.

## Structure

~~~text
diarization-benchmark/
├── models.yaml
├── data/manifest.example.yaml
├── runtime/fluidaudio-helper/
├── src/diarization_bench/
├── tests/
└── results/runs/<run-id>/
~~~

A run writes:

~~~text
run_manifest.json
raw.jsonl
evaluation.jsonl
aggregates.json
report.json
~~~

The run directory is immutable by convention. Use a new run id when changing models, data, post-processing or runtime conditions.

## Quick start

See [HOW_TO_USE.md](HOW_TO_USE.md) for the complete flow.

~~~bash
cd experiments/diarization-benchmark
uv sync --extra dev
uv run diarization-bench preflight
uv run diarization-bench build-helper
cp data/manifest.example.yaml data/manifest.local.yaml
# edit paths
uv run diarization-bench plan --manifest data/manifest.local.yaml --models all
uv run diarization-bench run --manifest data/manifest.local.yaml --models all
~~~

## Dataset policy

Audio and private annotations are not committed. The manifest points to local WAV files and RTTM references. This keeps the experiment reproducible without turning the repository into a storage location for meeting content.

For meaningful comparison, build a compact evaluation set with at least:

- clean 2-person remote call;
- 3-4 person meeting;
- 5-8 person meeting;
- high-overlap excerpt;
- noisy/distant speech;
- quiet speaker / short-turn case.

Public corpora such as AMI or VoxConverse can be added through local manifests, but the benchmark does not silently download or redistribute datasets.

## ClosedRoom relationship

This repository is an experiment harness, not a second product runtime. A model only becomes a ClosedRoom candidate after real benchmark evidence exists and the integration is separately shaped in the ClosedRoom repository. No cloud fallback is introduced here.
