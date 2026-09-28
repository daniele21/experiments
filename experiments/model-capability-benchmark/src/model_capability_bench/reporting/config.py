from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from benchmark_core import load_yaml_section


@dataclass(frozen=True)
class ReportingConfig:
    title: str
    html_filename: str
    json_filename: str
    numeric_precision: int
    max_case_rows_per_cell: int

    def __post_init__(self) -> None:
        if not self.title.strip():
            raise ValueError("reporting title must not be empty")
        if not self.html_filename.strip():
            raise ValueError("html_filename must not be empty")
        if not self.json_filename.strip():
            raise ValueError("json_filename must not be empty")
        if self.numeric_precision < 0:
            raise ValueError("numeric_precision must be >= 0")
        if self.max_case_rows_per_cell <= 0:
            raise ValueError("max_case_rows_per_cell must be > 0")


def load_reporting_config(root: Path) -> ReportingConfig:
    raw = load_yaml_section(
        root / "reporting.yaml",
        "reporting",
        required=True,
    )
    allowed = {
        "title",
        "html_filename",
        "json_filename",
        "numeric_precision",
        "max_case_rows_per_cell",
    }
    unknown = sorted(str(key) for key in raw if str(key) not in allowed)
    if unknown:
        raise ValueError(
            "reporting config contains unsupported fields: "
            + ", ".join(unknown)
        )
    return ReportingConfig(
        title=str(raw["title"]),
        html_filename=str(raw["html_filename"]),
        json_filename=str(raw["json_filename"]),
        numeric_precision=int(raw["numeric_precision"]),
        max_case_rows_per_cell=int(raw["max_case_rows_per_cell"]),
    )
