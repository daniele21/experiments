from __future__ import annotations

import csv
import json
import random
import urllib.request
from pathlib import Path

from jev_bench.models import BenchmarkCase, QuestionSpec

BANKING77_BASE = "https://raw.githubusercontent.com/PolyAI-LDN/task-specific-datasets/master/banking_data"
BANKING77_TEST_URL = f"{BANKING77_BASE}/test.csv"
BANKING77_CATEGORIES_URL = f"{BANKING77_BASE}/categories.json"
CLINC150_FULL_URL = "https://raw.githubusercontent.com/clinc/oos-eval/master/data/data_full.json"

DEFAULT_CACHE = Path("data/cache")


def _download(url: str, target: Path) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and target.stat().st_size > 0:
        return target
    request = urllib.request.Request(url, headers={"User-Agent": "jev-bench/0.1"})
    with urllib.request.urlopen(request, timeout=60) as response:
        target.write_bytes(response.read())
    return target


def prepare_public_data(cache_dir: Path = DEFAULT_CACHE) -> dict[str, Path]:
    """Download canonical public evaluation data into a gitignored local cache."""
    return {
        "banking77_test": _download(BANKING77_TEST_URL, cache_dir / "banking77" / "test.csv"),
        "banking77_categories": _download(
            BANKING77_CATEGORIES_URL, cache_dir / "banking77" / "categories.json"
        ),
        "clinc150_full": _download(CLINC150_FULL_URL, cache_dir / "clinc150" / "data_full.json"),
    }


def _humanize(label: str) -> str:
    return label.replace("_", " ").strip()


def banking77_labels(cache_dir: Path = DEFAULT_CACHE) -> list[str]:
    paths = prepare_public_data(cache_dir)
    labels = json.loads(paths["banking77_categories"].read_text(encoding="utf-8"))
    if not isinstance(labels, list) or not all(isinstance(x, str) for x in labels):
        raise ValueError("Unexpected BANKING77 categories format")
    return labels


def banking77_question(cache_dir: Path = DEFAULT_CACHE, include_other: bool = False) -> QuestionSpec:
    labels = banking77_labels(cache_dir)
    criteria = {
        label: f"Banking support intent: {_humanize(label)}."
        for label in labels
    }
    if include_other:
        criteria["other"] = "The request does not match any of the supported banking intents."
    return QuestionSpec(
        id="intent",
        type="choice",
        instructions=(
            "Classify the customer's request into the single best supported banking intent. "
            "Use other only when none of the banking intents apply."
            if include_other
            else "Classify the customer's request into the single best supported banking intent."
        ),
        criteria=criteria,
    )


def _read_banking77(cache_dir: Path = DEFAULT_CACHE) -> list[tuple[str, str]]:
    path = prepare_public_data(cache_dir)["banking77_test"]
    rows: list[tuple[str, str]] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        header = next(reader, None)
        if header != ["text", "category"]:
            raise ValueError(f"Unexpected BANKING77 header: {header}")
        for text, category in reader:
            rows.append((text, category))
    return rows


def balanced_banking77_cases(
    cache_dir: Path = DEFAULT_CACHE,
    *,
    max_cases: int | None = None,
    seed: int = 42,
    experiment: str = "01-routing",
) -> list[BenchmarkCase]:
    rows = _read_banking77(cache_dir)
    by_label: dict[str, list[str]] = {}
    for text, label in rows:
        by_label.setdefault(label, []).append(text)

    rng = random.Random(seed)
    for texts in by_label.values():
        rng.shuffle(texts)

    labels = sorted(by_label)
    if max_cases is None or max_cases >= len(rows):
        per_label = max(len(v) for v in by_label.values())
    else:
        per_label = max(1, max_cases // len(labels))

    selected: list[BenchmarkCase] = []
    for label in labels:
        texts = by_label[label][:per_label]
        for idx, text in enumerate(texts):
            selected.append(
                BenchmarkCase(
                    case_id=f"banking77-{label}-{idx}",
                    state=text,
                    expected={"intent": label},
                    metadata={
                        "dataset": "banking77",
                        "source_split": "test",
                        "difficulty": "in_scope",
                        "benchmark_tier": "public",
                        "experiment_source": experiment,
                    },
                )
            )

    rng.shuffle(selected)
    if max_cases is not None:
        selected = selected[:max_cases]
    return selected


def clinc_oos_cases(
    cache_dir: Path = DEFAULT_CACHE,
    *,
    max_cases: int = 500,
    seed: int = 42,
) -> list[BenchmarkCase]:
    path = prepare_public_data(cache_dir)["clinc150_full"]
    data = json.loads(path.read_text(encoding="utf-8"))
    raw = data.get("oos_test")
    if not isinstance(raw, list):
        raise ValueError("CLINC150 data_full.json has no oos_test split")

    rows = [(str(item[0]), str(item[1])) for item in raw if len(item) >= 2]
    rng = random.Random(seed)
    rng.shuffle(rows)
    return [
        BenchmarkCase(
            case_id=f"clinc-oos-{idx}",
            state=text,
            expected={"intent": "other"},
            metadata={
                "dataset": "clinc150",
                "source_split": "oos_test",
                "difficulty": "out_of_scope",
                "benchmark_tier": "public",
            },
        )
        for idx, (text, _) in enumerate(rows[:max_cases])
    ]


def calibration_public_cases(
    cache_dir: Path = DEFAULT_CACHE,
    *,
    in_scope_cases: int = 500,
    oos_cases: int = 500,
    seed: int = 42,
) -> list[BenchmarkCase]:
    inside = balanced_banking77_cases(
        cache_dir,
        max_cases=in_scope_cases,
        seed=seed,
        experiment="02-calibration",
    )
    outside = clinc_oos_cases(cache_dir, max_cases=oos_cases, seed=seed)
    combined = inside + outside
    random.Random(seed).shuffle(combined)
    return combined
