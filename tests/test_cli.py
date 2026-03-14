from comment_resolution_engine.cli import build_parser


def test_cli_parser_accepts_expected_args():
    parser = build_parser()
    args = parser.parse_args([
        "--comments",
        "in.xlsx",
        "--report",
        "report_rev1.pdf",
        "--report",
        "report_rev2.pdf",
        "--output",
        "out.xlsx",
        "--config",
        "map.yaml",
        "--patch-output",
        "patch.json",
        "--faq-output",
        "faq.md",
        "--summary-output",
        "summary.md",
        "--briefing-output",
        "briefing.md",
        "--draft-rev2",
        "--draft-mode",
        "EXECUTIVE_PLAIN_LANGUAGE",
        "--draft-sections",
        "3.1,4.2",
        "--draft-high-priority-only",
        "--draft-shared-only",
        "--assemble-rev2",
        "--rev2-sections-output",
        "rev2.json",
        "--rev2-draft-output",
        "rev2.md",
        "--constitution",
        "config/constitution.yaml",
        "--constitution-report",
        "outputs/constitution_report.json",
        "--compatibility-mode",
        "warn",
        "--fail-on-drift",
        "--rules-path",
        "rules.yaml",
        "--rules-profile",
        "baseline",
        "--rules-version",
        "v1.2.3",
    ])
    assert args.comments == "in.xlsx"
    assert args.report == ["report_rev1.pdf", "report_rev2.pdf"]
    assert args.output == "out.xlsx"
    assert args.config == "map.yaml"
    assert args.patch_output == "patch.json"
    assert args.faq_output == "faq.md"
    assert args.summary_output == "summary.md"
    assert args.briefing_output == "briefing.md"
    assert args.draft_rev2 is True
    assert args.draft_mode == "EXECUTIVE_PLAIN_LANGUAGE"
    assert args.draft_sections == "3.1,4.2"
    assert args.draft_high_priority_only is True
    assert args.draft_shared_only is True
    assert args.assemble_rev2 is True
    assert args.rev2_sections_output == "rev2.json"
    assert args.rev2_draft_output == "rev2.md"
    assert args.constitution == "config/constitution.yaml"
    assert args.constitution_report == "outputs/constitution_report.json"
    assert args.compatibility_mode == "warn"
    assert args.fail_on_drift is True
    assert args.rules_path == "rules.yaml"
    assert args.rules_profile == "baseline"
    assert args.rules_version == "v1.2.3"
    assert args.rules_strict is False
    assert args.validate_rules is False
