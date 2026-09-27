from __future__ import annotations

import argparse
from pathlib import Path

from vlm_bench.reporting import generate_vlm_report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate the VLM visual report")
    parser.add_argument("--run-dir", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output = generate_vlm_report(args.run_dir, args.run_dir / "report.html")
    print(f"report={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
