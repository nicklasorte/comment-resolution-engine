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
    parser.add_argument("--draft-rev2", action="store_true", help="Generate Rev-2 section-level rewrites.")
    parser.add_argument("--draft-mode", required=False, default="CLEAN_REWRITE", help="Rev-2 drafting mode (MINIMAL_EDIT, CLEAN_REWRITE, TECHNICAL_CLARIFICATION, EXECUTIVE_PLAIN_LANGUAGE).")
    parser.add_argument("--draft-sections", required=False, help="Comma-separated list of sections to rewrite.")
    parser.add_argument("--draft-high-priority-only", action="store_true", help="Limit Rev-2 rewrites to high or structurally unstable sections.")
    parser.add_argument("--draft-shared-only", action="store_true", help="Limit Rev-2 rewrites to sections with shared fixes.")
    parser.add_argument("--assemble-rev2", action="store_true", help="Assemble Rev-2 narrative from section rewrites.")
    parser.add_argument("--rev2-sections-output", required=False, help="Optional path for section-level Rev-2 rewrite JSON.")
    parser.add_argument("--rev2-draft-output", required=False, help="Optional path for assembled Rev-2 draft markdown.")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    draft_sections = [part.strip() for part in (args.draft_sections.split(",") if args.draft_sections else []) if part.strip()]
    df = run_pipeline(
        comments_path=args.comments,
        report_path=args.report,
        output_path=args.output,
        config_path=args.config,
        patch_output=args.patch_output,
        faq_output=args.faq_output,
        summary_output=args.summary_output,
        briefing_output=args.briefing_output,
        draft_rev2=args.draft_rev2,
        draft_mode=args.draft_mode,
        draft_sections=draft_sections or None,
        draft_high_priority_only=args.draft_high_priority_only,
        draft_shared_only=args.draft_shared_only,
        assemble_rev2=args.assemble_rev2,
        rev2_sections_output=args.rev2_sections_output,
        rev2_draft_output=args.rev2_draft_output,
    )
    print(f"Wrote {len(df)} rows to {args.output}")


if __name__ == "__main__":
    main()
