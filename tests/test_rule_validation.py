from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from comment_resolution_engine.errors import ErrorCategory
from comment_resolution_engine.rules import RuleEngine, Strictness, load_rule_pack
from comment_resolution_engine.rules.loader import RulePackLoadError
from types import SimpleNamespace


FIXTURES = Path(__file__).parent / "fixtures" / "rules" / "hardened"


def test_malformed_yaml_raises(tmp_path: Path):
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()
    (rules_dir / "canonical_terms.yaml").write_text("bad: [")
    with pytest.raises(RulePackLoadError) as exc:
        load_rule_pack(rules_dir, strictness=Strictness.STRICT)
    assert exc.value.category == ErrorCategory.SCHEMA_ERROR


def test_missing_required_fields_fail_strict():
    rules_dir = FIXTURES / "invalid_rules_missing_keys"
    with pytest.raises(RulePackLoadError) as exc:
        load_rule_pack(rules_dir, strictness=Strictness.STRICT)
    assert exc.value.category in {ErrorCategory.SCHEMA_ERROR, ErrorCategory.VALIDATION_ERROR}


def test_invalid_enums_fail():
    rules_dir = FIXTURES / "invalid_rules_bad_enum"
    with pytest.raises(RulePackLoadError) as exc:
        load_rule_pack(rules_dir, strictness=Strictness.STRICT)
    assert exc.value.category == ErrorCategory.VALIDATION_ERROR


def test_invalid_workflow_status_validation(tmp_path: Path):
    rules_dir = tmp_path / "bad_enum_workflow"
    rules_dir.mkdir()
    (rules_dir / "disposition_rules.yaml").write_text(
        "- rule_id: DISP_BAD_STATUS\n  rule_type: disposition\n  priority: 1\n  enabled: true\n"
        "  match:\n    field_equals:\n      normalized_type: \"TECHNICAL\"\n"
        "  action:\n    disposition: \"Accept\"\n    workflow_status: \"not_real\"\n"
    )
    with pytest.raises(RulePackLoadError) as exc:
        load_rule_pack(rules_dir, strictness=Strictness.STRICT)
    assert "workflow_status" in str(exc.value)


def test_wrong_types_fail(tmp_path: Path):
    rules_dir = tmp_path / "bad_types"
    rules_dir.mkdir()
    (rules_dir / "canonical_terms.yaml").write_text(
        "- rule_id: BAD_PRIORITY\n  rule_type: canonical_term\n  priority: \"high\"\n  enabled: true\n  match: {}\n  action: {}\n"
    )
    with pytest.raises(RulePackLoadError) as exc:
        load_rule_pack(rules_dir, strictness=Strictness.STRICT)
    assert exc.value.category == ErrorCategory.VALIDATION_ERROR


def test_unknown_keys_warn_permissive_and_fail_strict():
    rules_dir = FIXTURES / "invalid_rules_unknown_keys"
    pack = load_rule_pack(rules_dir, strictness=Strictness.PERMISSIVE)
    assert pack.validation_warnings
    with pytest.raises(RulePackLoadError):
        load_rule_pack(rules_dir, strictness=Strictness.STRICT)


def test_profile_override_structure():
    rules_dir = FIXTURES / "valid_rules"
    pack = load_rule_pack(rules_dir, profile="default", strictness=Strictness.STRICT)
    canonical = {r.rule_id: r for r in pack.canonical_term_rules}
    assert canonical["CANONICAL_FIX"].action.get("canonical_term") == "rev1_profile"

    bad_profile_dir = FIXTURES / "invalid_profile_structure"
    with pytest.raises(RulePackLoadError):
        load_rule_pack(bad_profile_dir, profile="default", strictness=Strictness.STRICT)


def test_conflicting_disposition_rules_resolve_deterministically():
    rules_dir = FIXTURES / "conflicting_rules"
    pack = load_rule_pack(rules_dir, strictness=Strictness.STRICT)
    engine = RuleEngine(pack)
    comment = SimpleNamespace(normalized_type="TECHNICAL")
    disposition, primary_match, matches = engine.disposition_for_comment(comment)
    assert disposition == "Accept"
    assert len(matches) == 2
    primary = primary_match or matches[0]
    assert any(m.skip_reason == "conflict" for m in matches)
    assert primary.conflict_with


def test_validate_rules_cli_success_and_failure():
    valid_dir = FIXTURES / "valid_rules"
    cmd = [sys.executable, "-m", "comment_resolution_engine.cli", "--validate-rules", "--rules-path", str(valid_dir)]
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}
    success = subprocess.run(cmd, capture_output=True, text=True, env=env)
    assert success.returncode == 0

    bad_dir = FIXTURES / "invalid_rules_bad_enum"
    fail_cmd = [sys.executable, "-m", "comment_resolution_engine.cli", "--validate-rules", "--rules-path", str(bad_dir), "--rules-strict"]
    failure = subprocess.run(fail_cmd, capture_output=True, text=True, env=env)
    assert failure.returncode != 0
