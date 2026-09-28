from types import SimpleNamespace

from redact_bench.models import Case, Span
from redact_bench.provider import KorgisRedactProvider
from redact_bench.segmentation import segment_text


def test_segmentation_preserves_offsets_and_advances():
    text = "alpha beta gamma delta epsilon zeta eta theta iota kappa"
    segments = segment_text(text, max_chars=18, overlap_chars=4)

    assert len(segments) > 1
    for segment in segments:
        assert segment.text == text[segment.start : segment.end]
    for left, right in zip(segments, segments[1:]):
        assert right.start > left.start
        assert right.start < left.end


class _Completions:
    def create(self, **kwargs):
        text = kwargs["messages"][-1]["content"]
        fields = []
        if "Mario Rossi" in text:
            fields.append({"pii_type": "private_person", "value": "Mario Rossi"})
        content = __import__("json").dumps({"pii_fields": fields})
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content=content),
                    finish_reason="stop",
                )
            ],
            usage=SimpleNamespace(prompt_tokens=4, completion_tokens=4),
        )


class _Client:
    def __init__(self):
        self.chat = SimpleNamespace(completions=_Completions())


def test_provider_maps_chunk_local_findings_to_global_offsets(monkeypatch, tmp_path):
    profiles = tmp_path / "profiles.yaml"
    profiles.write_text(
        """
profiles:
  financial:
    private_person:
      description: person
      examples: [Mario Rossi]
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "redact_bench.provider.OpenAI",
        lambda **_kwargs: _Client(),
    )
    monkeypatch.setenv("REDACT_BENCH_CHUNK_MAX_CHARS", "32")
    monkeypatch.setenv("REDACT_BENCH_CHUNK_OVERLAP_CHARS", "8")

    prefix = "A" * 35 + " "
    text = prefix + "Mario Rossi" + " " + "B" * 35
    start = text.index("Mario Rossi")
    case = Case(
        case_id="segmented",
        profile="financial",
        text=text,
        gold=(Span(start, start + 11, "private_person", "Mario Rossi"),),
    )

    result = KorgisRedactProvider("model", str(profiles)).evaluate(case)

    assert result.valid is True
    assert result.segment_count > 1
    assert result.successful_segments == result.segment_count
    assert [(item.start, item.end) for item in result.findings] == [
        (start, start + 11)
    ]
