from jev_bench.metrics import brier_score, expected_calibration_error


def test_brier_perfect_is_zero():
    assert brier_score([1, 0], [1.0, 0.0]) == 0.0


def test_ece_perfect_is_zero():
    assert expected_calibration_error([1, 0], [1.0, 0.0], bins=2) == 0.0



def test_summary_uses_primary_outcome_and_request_latency():
    import pandas as pd
    from jev_bench.metrics import summarize

    rows = pd.DataFrame([
        {"experiment":"04-workflow","provider":"jev","model":"x","case_id":"1","question_id":"q1","valid":True,"correct":False,"primary_metric":False,"latency_ms":100,"input_tokens":10,"output_tokens":1},
        {"experiment":"04-workflow","provider":"jev","model":"x","case_id":"1","question_id":"final_action","valid":True,"correct":True,"primary_metric":True,"latency_ms":100,"input_tokens":10,"output_tokens":1},
    ])
    out = summarize(rows).iloc[0]
    assert out["accuracy"] == 1.0
    assert out["intermediate_accuracy"] == 0.0
    assert out["latency_p50_ms"] == 100.0
