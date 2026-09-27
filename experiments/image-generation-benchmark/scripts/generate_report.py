from __future__ import annotations

import argparse
from pathlib import Path

from imagegen_bench.reporting import generate_blind_review, generate_identified_report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate image benchmark HTML reports")
    parser.add_argument("--run-dir", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    generate_identified_report(args.run_dir, args.run_dir / "report.html")
    generate_blind_review(args.run_dir, args.run_dir / "blind_review.html")
    print(f"report={args.run_dir / 'report.html'}")
    print(f"blind_review={args.run_dir / 'blind_review.html'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
