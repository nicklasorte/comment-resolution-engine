from __future__ import annotations

import argparse

from .pipeline import run_pipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a comment-resolution workbook from a comment matrix and optional report PDF.")
    parser.add_argument("--comments", required=True, help="Path to input Excel comment matrix.")
    parser.add_argument("--report", required=False, help="Path to report PDF with line numbers.")
    parser.add_argument("--output", required=True, help="Path for generated output workbook.")
    parser.add_argument("--config", required=False, help="Path to YAML column mapping config.")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    df = run_pipeline(
        comments_path=args.comments,
        report_path=args.report,
        output_path=args.output,
        config_path=args.config,
    )
    print(f"Wrote {len(df)} rows to {args.output}")


if __name__ == "__main__":
    main()
