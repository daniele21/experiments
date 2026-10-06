from diarization_bench.metrics import Segment, evaluate


def seg(speaker: str, start: float, end: float) -> Segment:
    return Segment(speaker=speaker, start=start, end=end)


def test_perfect_with_permuted_speaker_labels() -> None:
    reference = [seg("alice", 0, 5), seg("bob", 5, 10)]
    hypothesis = [seg("speaker_1", 0, 5), seg("speaker_0", 5, 10)]

    result = evaluate(reference, hypothesis)

    assert result["der"] == 0.0
    assert result["jer"] == 0.0
    assert result["speaker_count_exact"] is True


def test_half_missing_speech_is_half_der() -> None:
    reference = [seg("alice", 0, 10)]
    hypothesis = [seg("speaker_0", 0, 5)]

    result = evaluate(reference, hypothesis)

    assert result["der"] == 0.5
    assert result["miss_seconds"] == 5.0
    assert result["false_alarm_seconds"] == 0.0


def test_extra_false_alarm_is_counted() -> None:
    reference = [seg("alice", 0, 5)]
    hypothesis = [seg("speaker_0", 0, 5), seg("speaker_1", 5, 10)]

    result = evaluate(reference, hypothesis)

    assert result["der"] == 1.0
    assert result["false_alarm_seconds"] == 5.0
    assert result["detected_speakers"] == 2


def test_overlap_preserves_two_active_speakers() -> None:
    reference = [seg("alice", 0, 10), seg("bob", 5, 10)]
    hypothesis = [seg("a", 0, 10), seg("b", 5, 10)]

    result = evaluate(reference, hypothesis)

    assert result["der"] == 0.0
    assert result["reference_speaker_seconds"] == 15.0
