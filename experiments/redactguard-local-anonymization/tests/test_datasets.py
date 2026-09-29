from pathlib import Path

from redact_bench.datasets import load_jsonl


def test_smoke_dataset_loads():
    root = Path(__file__).resolve().parents[1]
    cases = load_jsonl(root / "data/smoke/cases.jsonl")
    assert len(cases) == 20
    repeated = next(case for case in cases if case.case_id == "g03")
    assert len(repeated.gold) == 2


def test_load_dataset_filter_by_id():
    root = Path(__file__).resolve().parents[1]
    cases = load_jsonl(root / "data/smoke/cases.jsonl")
    by_id = {c.case_id: c for c in cases}
    selected = [by_id[cid] for cid in ["g01", "g03"] if cid in by_id]
    assert len(selected) == 2
    assert [c.case_id for c in selected] == ["g01", "g03"]

