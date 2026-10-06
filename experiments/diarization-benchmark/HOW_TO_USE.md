# How to use

## 1. Requirements

Real model execution requires:

- Apple Silicon Mac;
- macOS 14 or newer;
- Swift toolchain;
- Python 3.11+;
- local audio files;
- RTTM ground truth for the same files.

The deterministic Python metric tests can run on Linux CI.

## 2. Install

~~~bash
cd experiments/diarization-benchmark
uv sync --extra dev
~~~

## 3. Preflight and build the local helper

~~~bash
uv run diarization-bench preflight
uv run diarization-bench build-helper
~~~

The release helper is built once and then reused so Swift compilation time is not mixed into inference latency.

On first model execution FluidAudio can download model assets. If an upstream model repository requires authentication, export the appropriate Hugging Face token before the run.

## 4. Prepare a manifest

~~~bash
cp data/manifest.example.yaml data/manifest.local.yaml
~~~

Use absolute paths to avoid ambiguity:

~~~yaml
cases:
  - id: real-meeting-01
    audio: /Users/me/bench/real-meeting-01.wav
    reference_rttm: /Users/me/bench/real-meeting-01.rttm
    tags:
      speaker_band: 2-4
      overlap: medium
      environment: remote
~~~

RTTM rows use the standard form:

~~~text
SPEAKER real-meeting-01 1 0.000 3.420 <NA> <NA> alice <NA> <NA>
~~~

## 5. Inspect the matrix before spending compute

~~~bash
uv run diarization-bench plan \
  --manifest data/manifest.local.yaml \
  --models community-1-vbx,nemotron3-fast32
~~~

Use all registered candidates with:

~~~bash
uv run diarization-bench plan \
  --manifest data/manifest.local.yaml \
  --models all
~~~

## 6. Run

~~~bash
uv run diarization-bench run \
  --manifest data/manifest.local.yaml \
  --models community-1-vbx,sortformer-v2.1-balanced,ls-eend-dihard3-500ms,nemotron3-fast32
~~~

For the maximum-quality Nemotron profile, add:

~~~text
nemotron3-offline
~~~

That profile is intentionally separate because it is a heavier GPU-oriented batch path and should not be conflated with the more product-plausible fast32 profile.

## 7. Read results

Open the latest directory under:

~~~text
results/runs/<run-id>/
~~~

Start with aggregates.json. Then use evaluation.jsonl for case-level diagnosis.

Interpret RTF as processing seconds divided by audio seconds:

- 0.25 = four times faster than real time;
- 1.00 = real time;
- >1.00 = slower than real time.

model_load_seconds is kept separate from inference_seconds so cold model acquisition/loading does not distort the core processing metric.

## 8. Recommended comparison protocol

Run the same immutable audio/RTTM set for every model. Do not tune thresholds on the final test set.

Use one small development subset for tuning, then freeze configuration and evaluate the held-out comparison set. Preserve run ids when sharing results.

For a ClosedRoom decision, look at both overall metrics and slices:

- <=4 speakers vs 5+;
- low vs high overlap;
- clean vs noisy;
- short turns / quiet speakers;
- system-audio-like clean capture vs room microphone.

## 9. Validation

~~~bash
uv run ruff check src tests
uv run pytest -q
swift build -c release --package-path runtime/fluidaudio-helper
~~~

The Swift build validates integration against the pinned FluidAudio API without downloading inference weights.
