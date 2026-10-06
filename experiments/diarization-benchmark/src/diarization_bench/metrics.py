from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from collections import defaultdict
from typing import Iterable

import numpy as np
from scipy.optimize import linear_sum_assignment


@dataclass(frozen=True)
class Segment:
    speaker: str
    start: float
    end: float

    def __post_init__(self) -> None:
        if self.end <= self.start:
            raise ValueError(f"Invalid segment for {self.speaker}: {self.start}..{self.end}")


def load_rttm(path: Path) -> list[Segment]:
    segments: list[Segment] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) < 8 or parts[0] != "SPEAKER":
            raise ValueError(f"Unsupported RTTM line {line_no} in {path}")
        start = float(parts[3])
        duration = float(parts[4])
        if duration <= 0:
            continue
        segments.append(Segment(speaker=parts[7], start=start, end=start + duration))
    return segments


def _intervals(reference: Iterable[Segment], hypothesis: Iterable[Segment]):
    ref = list(reference)
    hyp = list(hypothesis)
    events: dict[float, list[tuple[str, str, int]]] = defaultdict(list)
    for side, segments in (("r", ref), ("h", hyp)):
        for seg in segments:
            events[seg.start].append((side, seg.speaker, 1))
            events[seg.end].append((side, seg.speaker, -1))

    times = sorted(events)
    ref_counts: dict[str, int] = defaultdict(int)
    hyp_counts: dict[str, int] = defaultdict(int)
    out: list[tuple[float, set[str], set[str]]] = []
    for index, current in enumerate(times[:-1]):
        for side, speaker, delta in events[current]:
            counts = ref_counts if side == "r" else hyp_counts
            counts[speaker] += delta
        nxt = times[index + 1]
        if nxt <= current:
            continue
        active_ref = {speaker for speaker, count in ref_counts.items() if count > 0}
        active_hyp = {speaker for speaker, count in hyp_counts.items() if count > 0}
        out.append((nxt - current, active_ref, active_hyp))
    return out


def _speaker_overlap(reference: list[Segment], hypothesis: list[Segment]):
    ref_speakers = sorted({seg.speaker for seg in reference})
    hyp_speakers = sorted({seg.speaker for seg in hypothesis})
    matrix = np.zeros((len(ref_speakers), len(hyp_speakers)), dtype=float)
    ref_index = {speaker: i for i, speaker in enumerate(ref_speakers)}
    hyp_index = {speaker: i for i, speaker in enumerate(hyp_speakers)}

    intervals = _intervals(reference, hypothesis)
    for duration, refs, hyps in intervals:
        for ref_speaker in refs:
            for hyp_speaker in hyps:
                matrix[ref_index[ref_speaker], hyp_index[hyp_speaker]] += duration
    return ref_speakers, hyp_speakers, matrix, intervals


def _overlap_mapping(reference: list[Segment], hypothesis: list[Segment]) -> dict[str, str]:
    ref_speakers, hyp_speakers, matrix, _ = _speaker_overlap(reference, hypothesis)
    if not ref_speakers or not hyp_speakers:
        return {}
    rows, cols = linear_sum_assignment(-matrix)
    return {hyp_speakers[col]: ref_speakers[row] for row, col in zip(rows, cols, strict=True)}


def diarization_error(reference: list[Segment], hypothesis: list[Segment]) -> dict[str, float]:
    mapping = _overlap_mapping(reference, hypothesis)
    intervals = _intervals(reference, hypothesis)

    total_ref = 0.0
    miss = 0.0
    false_alarm = 0.0
    confusion = 0.0

    for duration, refs, hyps in intervals:
        n_ref = len(refs)
        n_hyp = len(hyps)
        total_ref += n_ref * duration
        mapped = {mapping[h] for h in hyps if h in mapping}
        correct = len(refs & mapped)
        miss += max(0, n_ref - n_hyp) * duration
        false_alarm += max(0, n_hyp - n_ref) * duration
        confusion += (min(n_ref, n_hyp) - correct) * duration

    if total_ref == 0:
        der = 0.0 if not hypothesis else 1.0
    else:
        der = (miss + false_alarm + confusion) / total_ref

    return {
        "der": der,
        "miss_seconds": miss,
        "false_alarm_seconds": false_alarm,
        "confusion_seconds": confusion,
        "reference_speaker_seconds": total_ref,
    }


def jaccard_error(reference: list[Segment], hypothesis: list[Segment]) -> float:
    ref_speakers, hyp_speakers, intersections, intervals = _speaker_overlap(reference, hypothesis)
    if not ref_speakers:
        return 0.0 if not hyp_speakers else 1.0

    ref_duration = {speaker: 0.0 for speaker in ref_speakers}
    hyp_duration = {speaker: 0.0 for speaker in hyp_speakers}
    for duration, refs, hyps in intervals:
        for speaker in refs:
            ref_duration[speaker] += duration
        for speaker in hyps:
            hyp_duration[speaker] += duration

    iou = np.zeros_like(intersections)
    for i, ref_speaker in enumerate(ref_speakers):
        for j, hyp_speaker in enumerate(hyp_speakers):
            inter = intersections[i, j]
            union = ref_duration[ref_speaker] + hyp_duration[hyp_speaker] - inter
            iou[i, j] = inter / union if union > 0 else 0.0

    scores = [0.0] * len(ref_speakers)
    if hyp_speakers:
        rows, cols = linear_sum_assignment(-iou)
        for row, col in zip(rows, cols, strict=True):
            scores[row] = float(iou[row, col])
    return 1.0 - float(np.mean(scores))


def evaluate(reference: list[Segment], hypothesis: list[Segment]) -> dict[str, float | int | bool]:
    der = diarization_error(reference, hypothesis)
    ref_count = len({seg.speaker for seg in reference})
    hyp_count = len({seg.speaker for seg in hypothesis})
    return {
        **der,
        "jer": jaccard_error(reference, hypothesis),
        "reference_speakers": ref_count,
        "detected_speakers": hyp_count,
        "speaker_count_error": hyp_count - ref_count,
        "speaker_count_absolute_error": abs(hyp_count - ref_count),
        "speaker_count_exact": hyp_count == ref_count,
    }
