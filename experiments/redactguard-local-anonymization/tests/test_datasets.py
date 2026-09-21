from pathlib import Path

from redact_bench.datasets import load_jsonl


def test_smoke_dataset_loads():
    root = Path(__file__).resolve().parents[1]
    cases = load_jsonl(root / "data/smoke/cases.jsonl")
    assert len(cases) == 20
    repeated = next(case for case in cases if case.case_id == "g03")
    assert len(repeated.gold) == 2
