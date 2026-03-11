from comment_resolution_engine.cli import build_parser


def test_cli_parser_accepts_expected_args():
    parser = build_parser()
    args = parser.parse_args([
        "--comments",
        "in.xlsx",
        "--report",
        "report.pdf",
        "--output",
        "out.xlsx",
        "--config",
        "map.yaml",
    ])
    assert args.comments == "in.xlsx"
    assert args.report == "report.pdf"
    assert args.output == "out.xlsx"
    assert args.config == "map.yaml"
