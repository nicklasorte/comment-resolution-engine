from __future__ import annotations

import argparse
import sys

from .pipeline import run_pipeline
from .errors import CREError
from .rules import Strictness, load_rule_pack


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build an NTIA comment-resolution workbook (NTIA Comments, Comment Disposition, Resolution) from a comment matrix and working paper PDF revisions.")
    parser.add_argument("--comments", required=False, help="Path to input Excel comment matrix.")
    parser.add_argument(
        "--report",
        required=False,
        action="append",
        help="Path to working paper PDF (rev1). Provide additional --report arguments for later revisions in order.",
    )
    parser.add_argument("--output", required=False, help="Path for generated output workbook.")
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
    parser.add_argument("--rules-path", required=False, help="Optional path to an external ruleset directory (e.g., ../spectrum-systems/rules/comment-resolution).")
    parser.add_argument("--rules-profile", required=False, help="Optional rules profile identifier (defaults to 'default' when available).")
    parser.add_argument("--rules-version", required=False, help="Optional rules version identifier to record in provenance.")
    parser.add_argument("--rules-strict", action="store_true", help="Validate rules in strict mode (unknown keys become errors).")
    parser.add_argument("--validate-rules", action="store_true", help="Validate a rules directory and exit.")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    draft_sections = [part.strip() for part in (args.draft_sections.split(",") if args.draft_sections else []) if part.strip()]
    try:
        if not args.validate_rules and (not args.comments or not args.report or not args.output):
            print("ERROR: --comments, --report, and --output are required unless --validate-rules is used.")
            sys.exit(1)
        if args.validate_rules:
            if not args.rules_path:
                print("ERROR: --rules-path is required when using --validate-rules.")
                sys.exit(1)
            pack = load_rule_pack(args.rules_path, profile=args.rules_profile, requested_version=args.rules_version, strictness=Strictness.STRICT if args.rules_strict else Strictness.PERMISSIVE)
            print(f"Rule validation succeeded for {args.rules_path} (profile={pack.rules_profile}, loaded={pack.loaded_count}).")
            if pack.validation_warnings:
                print("Warnings:")
                for warning in pack.validation_warnings:
                    file = warning.get("file", "")
                    rid = warning.get("rule_id") or ""
                    field = warning.get("field") or ""
                    message = warning.get("message", "")
                    category = warning.get("category", "WARNING")
                    print(f"- [{category}] {file} {rid} {field} {message}".strip())
            sys.exit(0)
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
            rules_path=args.rules_path,
            rules_profile=args.rules_profile,
            rules_version=args.rules_version,
            rules_strict=args.rules_strict,
        )
    except CREError as exc:
        print(f"ERROR {exc}")
        sys.exit(1)
    print(f"Wrote {len(df)} rows to {args.output}")


if __name__ == "__main__":
    main()
