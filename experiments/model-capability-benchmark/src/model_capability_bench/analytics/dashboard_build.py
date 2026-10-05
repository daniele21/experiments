from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DashboardBuildSummary:
    html_path: str
    overview_path: str
    capability_path: str | None


def _safe_json(value: object) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).replace("<", "\\u003c")


def inject_dashboard_payloads(
    *,
    html_path: Path,
    overview_path: Path,
    capability_path: Path | None = None,
) -> None:
    html = html_path.read_text(encoding="utf-8")
    if "</head>" not in html:
        raise ValueError("dashboard HTML is missing </head>")

    overview = json.loads(overview_path.read_text(encoding="utf-8"))
    capability = (
        json.loads(capability_path.read_text(encoding="utf-8"))
        if capability_path is not None and capability_path.is_file()
        else None
    )
    data_root = overview_path.parent
    models = {
        path.stem: json.loads(path.read_text(encoding="utf-8"))
        for path in sorted((data_root / "models").glob("*.json"))
    } if (data_root / "models").is_dir() else {}
    runs = {
        path.stem: json.loads(path.read_text(encoding="utf-8"))
        for path in sorted((data_root / "runs").glob("*.json"))
    } if (data_root / "runs").is_dir() else {}
    injection = (
        "<script>"
        f"window.__MCB_OVERVIEW__={_safe_json(overview)};"
        + (
            f"window.__MCB_CAPABILITY__={_safe_json(capability)};"
            if capability is not None
            else ""
        )
        + f"window.__MCB_MODELS__={_safe_json(models)};"
        + f"window.__MCB_RUNS__={_safe_json(runs)};"
        + "</script>"
    )
    html_path.write_text(
        html.replace("</head>", injection + "</head>", 1),
        encoding="utf-8",
    )


def build_dashboard(
    *,
    root: Path,
    dashboard_data_dir: Path,
    output_path: Path,
    capability_id: str = "structured-output",
) -> DashboardBuildSummary:
    dashboard_root = root.resolve() / "dashboard"
    overview_path = dashboard_data_dir.resolve() / "overview.json"
    capability_path = (
        dashboard_data_dir.resolve()
        / "capabilities"
        / f"{capability_id}.json"
    )
    if not overview_path.is_file():
        raise FileNotFoundError(overview_path)

    subprocess.run(
        ["npm", "run", "build"],
        cwd=dashboard_root,
        check=True,
    )
    built = dashboard_root / "dist" / "index.html"
    if not built.is_file():
        raise FileNotFoundError(built)

    output_path = output_path.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(built, output_path)
    inject_dashboard_payloads(
        html_path=output_path,
        overview_path=overview_path,
        capability_path=capability_path if capability_path.is_file() else None,
    )
    return DashboardBuildSummary(
        html_path=str(output_path),
        overview_path=str(overview_path),
        capability_path=(
            str(capability_path) if capability_path.is_file() else None
        ),
    )
