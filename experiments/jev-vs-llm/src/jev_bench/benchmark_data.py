from __future__ import annotations

from pathlib import Path

from benchmark_core import (
    DatasetLoadContext,
    DatasetProfileSpec,
    cached_source,
    load_banking77_categories,
    load_banking77_rows,
    load_clinc_rows,
    load_dataset_specs,
    require_string_list,
    seeded_random,
    single_cached_source,
)

from jev_bench.models import BenchmarkCase, QuestionSpec

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATASET_CATALOG = PROJECT_ROOT / "datasets.yaml"
DEFAULT_CACHE = Path("data/cache")


def _specs():
    return load_dataset_specs(DATASET_CATALOG)


def _context(cache_dir: Path) -> DatasetLoadContext:
    return DatasetLoadContext(
        cache_dir=cache_dir,
        profile=DatasetProfileSpec(
            profile_id="jev-public",
            default_max_cases=None,
        ),
        seed=0,
    )


def prepare_public_data(cache_dir: Path = DEFAULT_CACHE) -> dict[str, Path]:
    """Materialize pinned public data through the shared dataset source layer."""
    specs = _specs()
    context = _context(cache_dir)
    banking = specs["banking77"]
    clinc = specs["clinc150-oos"]
    return {
        "banking77_test": cached_source(
            banking,
            context,
            file_key="test",
        ),
        "banking77_categories": cached_source(
            banking,
            context,
            file_key="categories",
        ),
        "clinc150_full": single_cached_source(clinc, context),
    }


def _humanize(label: str) -> str:
    return label.replace("_", " ").strip()


def banking77_labels(cache_dir: Path = DEFAULT_CACHE) -> list[str]:
    paths = prepare_public_data(cache_dir)
    return list(load_banking77_categories(paths["banking77_categories"]))


def banking77_question(
    cache_dir: Path = DEFAULT_CACHE,
    include_other: bool = False,
) -> QuestionSpec:
    labels = banking77_labels(cache_dir)
    criteria = {
        label: f"Banking support intent: {_humanize(label)}."
        for label in labels
    }
    if include_other:
        criteria["other"] = (
            "The request does not match any of the supported banking intents."
        )
    return QuestionSpec(
        id="intent",
        type="choice",
        instructions=(
            "Classify the customer's request into the single best supported "
            "banking intent. Use other only when none of the banking intents apply."
            if include_other
            else "Classify the customer's request into the single best supported banking intent."
        ),
        criteria=criteria,
    )


def _read_banking77(cache_dir: Path = DEFAULT_CACHE) -> list[tuple[str, str]]:
    path = prepare_public_data(cache_dir)["banking77_test"]
    return [
        (text, category)
        for _, text, category in load_banking77_rows(path)
    ]


def balanced_banking77_cases(
    cache_dir: Path = DEFAULT_CACHE,
    *,
    max_cases: int | None = None,
    seed: int = 42,
    experiment: str = "01-routing",
) -> list[BenchmarkCase]:
    specs = _specs()
    revision = specs["banking77"].revision
    rows = _read_banking77(cache_dir)
    by_label: dict[str, list[str]] = {}
    for text, label in rows:
        by_label.setdefault(label, []).append(text)

    rng = seeded_random(seed)
    for texts in by_label.values():
        rng.shuffle(texts)

    labels = sorted(by_label)
    target = len(rows) if max_cases is None else min(max_cases, len(rows))
    base, remainder = divmod(target, len(labels))

    selected: list[BenchmarkCase] = []
    for label_index, label in enumerate(labels):
        take = base + (1 if label_index < remainder else 0)
        texts = by_label[label][:take]
        for idx, text in enumerate(texts):
            selected.append(
                BenchmarkCase(
                    case_id=f"banking77-{label}-{idx}",
                    state=text,
                    expected={"intent": label},
                    metadata={
                        "dataset": "banking77",
                        "dataset_revision": revision,
                        "source_split": specs["banking77"].split,
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
    max_cases: int | None = 500,
    seed: int = 42,
) -> list[BenchmarkCase]:
    specs = _specs()
    spec = specs["clinc150-oos"]
    path = prepare_public_data(cache_dir)["clinc150_full"]
    exclude_terms = require_string_list(
        spec.options.get("exclude_terms"),
        context="dataset 'clinc150-oos' exclude_terms",
    )
    rows = load_clinc_rows(
        path,
        split=spec.split,
        exclude_terms=exclude_terms,
    )

    shuffled = [
        (text, source_label)
        for _, text, source_label in rows
    ]
    rng = seeded_random(seed)
    rng.shuffle(shuffled)
    selected = shuffled if max_cases is None else shuffled[:max_cases]
    return [
        BenchmarkCase(
            case_id=f"clinc-oos-{idx}",
            state=text,
            expected={"intent": "other"},
            metadata={
                "dataset": "clinc150",
                "dataset_revision": spec.revision,
                "source_split": spec.split,
                "difficulty": "out_of_scope",
                "benchmark_tier": "public",
                "oos_filter": "conservative_non_finance",
            },
        )
        for idx, (text, _) in enumerate(selected)
    ]


def calibration_public_cases(
    cache_dir: Path = DEFAULT_CACHE,
    *,
    in_scope_cases: int | None = 500,
    oos_cases: int | None = 500,
    seed: int = 42,
) -> list[BenchmarkCase]:
    outside = clinc_oos_cases(cache_dir, max_cases=oos_cases, seed=seed)
    resolved_in_scope = len(outside) if in_scope_cases is None else in_scope_cases
    inside = balanced_banking77_cases(
        cache_dir,
        max_cases=resolved_in_scope,
        seed=seed,
        experiment="02-calibration",
    )
    combined = inside + outside
    seeded_random(seed).shuffle(combined)
    return combined
