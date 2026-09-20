from jev_bench.metrics import brier_score, expected_calibration_error


def test_brier_perfect_is_zero():
    assert brier_score([1, 0], [1.0, 0.0]) == 0.0


def test_ece_perfect_is_zero():
    assert expected_calibration_error([1, 0], [1.0, 0.0], bins=2) == 0.0
