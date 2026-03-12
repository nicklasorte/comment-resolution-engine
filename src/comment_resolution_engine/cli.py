from __future__ import annotations

import argparse

from .pipeline import run_pipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build an NTIA comment-resolution workbook (NTIA Comments, Comment Disposition, Resolution) from a comment matrix and optional report PDF.")
    parser.add_argument("--comments", required=True, help="Path to input Excel comment matrix.")
    parser.add_argument("--report", required=False, help="Path to report PDF with line numbers.")
    parser.add_argument("--output", required=True, help="Path for generated output workbook.")
    parser.add_argument("--config", required=False, help="Path to YAML column mapping config.")
    parser.add_argument("--patch-output", required=False, help="Optional path for generated report patch JSON.")
    parser.add_argument("--faq-output", required=False, help="Optional path for generated FAQ/issue log markdown.")
    parser.add_argument("--summary-output", required=False, help="Optional path for generated section summary markdown.")
    parser.add_argument("--briefing-output", required=False, help="Optional path for generated working group briefing bullets.")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    df = run_pipeline(
        comments_path=args.comments,
        report_path=args.report,
        output_path=args.output,
        config_path=args.config,
        patch_output=args.patch_output,
        faq_output=args.faq_output,
        summary_output=args.summary_output,
        briefing_output=args.briefing_output,
    )
    print(f"Wrote {len(df)} rows to {args.output}")


if __name__ == "__main__":
    main()
