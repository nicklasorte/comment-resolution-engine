from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .packaged_outputs import package_outputs
from .pipeline import run_pipeline
from .pipeline_result import PipelineRunResult
from .errors import CREError
from .rules import Strictness, load_rule_pack
from .contracts.loader import load_constitution
from .contracts import DEFAULT_CONSTITUTION_PATH


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build an NTIA comment-resolution workbook (NTIA Comments, Comment Disposition, Resolution) from a comment matrix and working paper PDF revisions.")
    parser.add_argument("--comments", required=False, help="Path to input Excel comment matrix.")
    parser.add_argument("--reviewer-comment-set", dest="reviewer_comment_set", required=False, help="Path to canonical reviewer_comment_set artifact (JSON or YAML).")
    parser.add_argument(
        "--report",
        required=False,
        action="append",
        help="Path to working paper PDF (rev1). Provide additional --report arguments for later revisions in order.",
    )
    parser.add_argument("--output", required=False, help="Path for generated output workbook.")
    parser.add_argument("--include-metadata-columns", action="store_true", help="Optionally include machine-generated metadata columns in the output workbook.")
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
    parser.add_argument("--constitution", required=False, default="config/constitution.yaml", help="Path to constitution manifest (YAML).")
    parser.add_argument("--check-constitution", action="store_true", help="Validate constitution compatibility and exit.")
    parser.add_argument("--constitution-report", required=False, help="Path for constitution compatibility report JSON.")
    parser.add_argument("--fail-on-drift", action="store_true", help="Treat constitution drift as fatal even in warn mode.")
    parser.add_argument("--compatibility-mode", required=False, choices=["strict", "warn"], help="Override manifest compatibility mode.")
    parser.add_argument("--rules-path", required=False, help="Optional path to an external ruleset directory (e.g., ../spectrum-systems/rules/comment-resolution).")
    parser.add_argument("--rules-profile", required=False, help="Optional rules profile identifier (defaults to 'default' when available).")
    parser.add_argument("--rules-version", required=False, help="Optional rules version identifier to record in provenance.")
    parser.add_argument("--rules-strict", action="store_true", help="Validate rules in strict mode (unknown keys become errors).")
    parser.add_argument("--validate-rules", action="store_true", help="Validate a rules directory and exit.")
    parser.add_argument("--output-dir", required=False, help="Optional root directory for packaged outputs.")
    parser.add_argument("--emit-run-manifest", action="store_true", help="Emit run_manifest.json and summary.json for automation workflows.")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    draft_sections = [part.strip() for part in (args.draft_sections.split(",") if args.draft_sections else []) if part.strip()]
    constitution_report_path = args.constitution_report
    if not constitution_report_path and args.output:
        base = Path(args.output)
        constitution_report_path = base.with_name(base.stem + "_constitution_report.json")
    if not constitution_report_path and args.check_constitution:
        constitution_report_path = Path("outputs/constitution_report.json")
    package_requested = bool(args.emit_run_manifest or args.output_dir)
    packaged_output_dir = Path(args.output_dir) if args.output_dir else None
    try:
        is_pipeline_run = not args.validate_rules and not args.check_constitution
        comments_path = args.reviewer_comment_set or args.comments
        if is_pipeline_run and not args.output:
            print("ERROR: --output is required for pipeline runs.")
            sys.exit(1)
        if is_pipeline_run and not args.report:
            print("ERROR: --report is required for pipeline runs.")
            sys.exit(1)
        if is_pipeline_run and not comments_path:
            print("ERROR: Provide either --comments or --reviewer-comment-set for pipeline runs.")
            sys.exit(1)
        if is_pipeline_run and args.comments and args.reviewer_comment_set:
            print("ERROR: Use only one of --comments or --reviewer-comment-set, not both.")
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
        if package_requested and constitution_report_path is None and args.output:
            target_dir = packaged_output_dir or Path(args.output).parent
            constitution_report_path = Path(target_dir) / "artifacts" / "constitution_report.json"
        constitution_context, constitution_report = load_constitution(
            manifest_path=args.constitution or DEFAULT_CONSTITUTION_PATH,
            compatibility_mode=args.compatibility_mode,
            rules_profile=args.rules_profile,
            rules_version=args.rules_version,
            fail_on_drift=args.fail_on_drift,
            require_compatible=True,
            report_path=constitution_report_path,
        )
        if args.check_constitution:
            status = "compatible" if constitution_report.compatible else "incompatible"
            print(f"Constitution check {status}. Report written to {constitution_report_path}.")
            sys.exit(0)
        packaged_output_dir = packaged_output_dir or (Path(args.output).parent if args.output else None)
        df = run_pipeline(
            comments_path=comments_path,
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
            constitution_path=args.constitution,
            constitution_report_path=constitution_report_path,
            compatibility_mode=args.compatibility_mode,
            fail_on_drift=args.fail_on_drift,
            constitution_context=constitution_context,
            skip_constitution_check=True,
            include_metadata_columns=args.include_metadata_columns,
            return_artifacts=package_requested,
        )
    except CREError as exc:
        if package_requested:
            print(json.dumps({"status": "error", "message": str(exc)}))
        else:
            print(f"ERROR {exc}")
        sys.exit(1)
    if isinstance(df, PipelineRunResult):
        result = df
        output_df = df.output_df
    else:
        result = None
        output_df = df

    if package_requested and result is not None:
        final_output_dir = packaged_output_dir or Path(args.output).parent
        package_result = package_outputs(result, final_output_dir, emit_manifest=True)
        payload = {
            "status": "success",
            "rows": len(output_df),
            "output_path": str(args.output),
            "output_dir": str(final_output_dir),
            "run_manifest": str(package_result["layout"].manifest_path) if package_result.get("manifest") else None,
            "summary": str(package_result["layout"].summary_path),
            "artifacts": {k: str(v) for k, v in package_result["outputs"].items()},
        }
        print(json.dumps(payload, separators=(",", ":")))
    else:
        print(f"Wrote {len(output_df)} rows to {args.output}")


if __name__ == "__main__":
    main()
