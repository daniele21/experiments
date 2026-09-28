from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TextSegment:
    start: int
    end: int
    text: str


def segment_text(
    text: str,
    *,
    max_chars: int,
    overlap_chars: int,
) -> list[TextSegment]:
    """Mirror RedactGuard detection-v2 deterministic text segmentation."""
    if max_chars <= 0 or len(text) <= max_chars:
        return [TextSegment(start=0, end=len(text), text=text)]
    if overlap_chars < 0 or overlap_chars >= max_chars:
        raise ValueError("overlap_chars must be >= 0 and smaller than max_chars")

    segments: list[TextSegment] = []
    start = 0
    text_len = len(text)

    while start < text_len:
        target_end = min(text_len, start + max_chars)
        end = target_end

        if target_end < text_len:
            search_floor = start + max(max_chars // 2, 1)
            newline = text.rfind("\n", search_floor, target_end)
            space = text.rfind(" ", search_floor, target_end)
            boundary = max(newline, space)
            if boundary > start:
                end = boundary + (1 if text[boundary] == "\n" else 0)

        if end <= start:
            end = target_end

        segments.append(TextSegment(start=start, end=end, text=text[start:end]))
        if end >= text_len:
            break

        next_start = max(0, end - overlap_chars)
        if next_start <= start:
            next_start = end
        start = next_start

    return segments
