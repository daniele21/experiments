import json

from redact_bench.suite_audit import build_suite_audit, write_suite_audit


def test_audit_suite_balances_micro_vs_document_and_semantic_family(tmp_path):
    root = tmp_path / "suite-1"
    (root / "quality").mkdir(parents=True)
    (root / "logs").mkdir()
    (root / "suite.json").write_text(
        json.dumps({"suite_id": "suite-1", "status": "completed",
                    "inference_cache_max_entries": 0}), encoding="utf-8"
    )
    cases = [
        ("large.xlsx", 100, 90, "spreadsheet", True),
        ("contract.doc", 10, 10, "contract", True),
        ("contract.docx", 10, 0, "contract", False),
    ]
    rows = [
        {"case_id": name, "model": "qwen", "gold_count": gold,
         "system_tp": tp, "system_pii_recall": tp / gold,
         "content_family_id": family, "human_reviewed": False,
         "valid": valid, "zero_leak": tp == gold and valid,
         "error_type": None if valid else "InternalServerError",
         "http_status": None if valid else 502,
         "error": "" if valid else
             "segment 2/6: Model returned invalid JSON (line 8, column 3)"}
        for name, gold, tp, family, valid in cases
    ]
    (root / "quality" / "rows.json").write_text(
        json.dumps(rows), encoding="utf-8"
    )
    (root / "logs" / "qwen.log").write_text(
        "Inference cache hit | model=qwen\nInference cache hit | model=qwen",
        encoding="utf-8",
    )

    data = build_suite_audit(root)
    assert data["data_status"]["largest_document_gold_share"] == 100 / 120
    assert data["data_status"]["semantic_families"] == 2
    assert data["data_status"]["human_reviewed"] == 0
    score = data["models"]["qwen"]
    assert score["system_micro_recall"] == 100 / 120
    assert score["system_macro_document_recall"] == (0.9 + 1 + 0) / 3
    assert score["system_macro_semantic_family_recall"] == (0.9 + 0.5) / 2
    assert score["valid_documents"] == 2
    assert score["inference_cache_hits_in_korgis_log"] == 2
    assert score["failures"][0]["failed_segment"] == {"index": 2, "total": 6}

    json_path, md_path = write_suite_audit(root)
    assert json.loads(json_path.read_text())["models"]["qwen"] == score
    text = md_path.read_text()
    assert "Macro family recall" in text
    assert "invalid JSON=True" in text
    assert "human_reviewed" not in text  # exported summary, not original gold


def test_audit_suite_does_not_export_raw_exception_messages(tmp_path):
    root = tmp_path / "suite"
    (root / "quality").mkdir(parents=True)
    (root / "quality" / "rows.json").write_text(json.dumps([{
        "model": "qwen", "case_id": "document.txt", "gold_count": 1,
        "system_tp": 0, "system_pii_recall": 0, "valid": False,
        "error": "Private data: user@example.com; segment 1/1",
        "error_type": "BackendError",
    }]), encoding="utf-8")
    json_path, markdown_path = write_suite_audit(root)
    assert "user@example.com" not in json_path.read_text()
    assert "user@example.com" not in markdown_path.read_text()
