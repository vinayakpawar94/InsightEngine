"""Unit tests for insightengine.rules.dsl.

Per the phase's acceptance criteria, every rule type gets both a passing
and a failing case.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from insightengine.core.exceptions import (
    InvalidRuleDefinitionError,
    RuleParseError,
    UnsafeExpressionError,
)
from insightengine.core.types import Severity
from insightengine.rules.dsl import (
    ExclusiveCategoryRule,
    MaxSelectionsRule,
    RangeRule,
    RankRule,
    RequiredRule,
    Rule,
    SkipLogicRule,
    SumEqualsRule,
    load_rules,
    parse_rules,
)
from insightengine.rules.evaluator import compile_expression


def _get(rules: tuple[Rule, ...], rule_id: str) -> Rule:
    for rule in rules:
        if rule.id == rule_id:
            return rule
    raise AssertionError(f"no rule with id {rule_id!r}")


class TestRuleBaseValidation:
    def test_empty_id_raises(self) -> None:
        with pytest.raises(InvalidRuleDefinitionError, match="empty"):
            RangeRule(id="  ", when=compile_expression("AGE < 18"))


class TestDirectConstructionValidation:
    """A few validity checks are only reachable by constructing a Rule
    dataclass directly with an already-blank-but-present string field —
    the YAML parser's own _require_str rejects a blank string before
    ever reaching these dataclass-level checks, so they need a direct
    construction test to exercise, not a YAML fixture.
    """

    def test_required_rule_blank_variable_raises(self) -> None:
        with pytest.raises(InvalidRuleDefinitionError, match="variable cannot be empty"):
            RequiredRule(id="r1", variable="   ")

    def test_max_selections_rule_blank_variable_raises(self) -> None:
        with pytest.raises(InvalidRuleDefinitionError, match="variable cannot be empty"):
            MaxSelectionsRule(id="r1", variable="   ", max_selections=1)

    def test_exclusive_category_rule_blank_variable_raises(self) -> None:
        with pytest.raises(InvalidRuleDefinitionError, match="variable cannot be empty"):
            ExclusiveCategoryRule(id="r1", variable="   ", exclusive_codes=(1,))

    def test_skip_logic_rule_duplicate_else_variables_raises(self) -> None:
        with pytest.raises(InvalidRuleDefinitionError, match="duplicate variable in else_variables"):
            SkipLogicRule(
                id="r1",
                when=compile_expression("Q1 == 'Yes'"),
                then_required=("Q2",),
                else_variables=("Q2", "Q2"),
            )


class TestRangeRulePassAndFail:
    def test_range_rule_passing_case(self) -> None:
        rules = parse_rules(
            """
rules:
  - id: age_range
    type: range
    when: "AGE < 18 or AGE > 99"
"""
        )
        rule = _get(rules, "age_range")
        assert isinstance(rule, RangeRule)
        assert rule.severity is Severity.ERROR
        assert rule.when.evaluate({"AGE": 5}) is True

    def test_range_rule_missing_when_raises(self) -> None:
        with pytest.raises(RuleParseError, match="missing required field 'when'"):
            parse_rules("rules:\n  - {id: age_range, type: range}\n")

    def test_range_rule_malicious_when_rejected(self) -> None:
        with pytest.raises(UnsafeExpressionError):
            parse_rules(
                """
rules:
  - id: malicious
    type: range
    when: "AGE.__class__.__mro__"
"""
            )


class TestRequiredRulePassAndFail:
    def test_required_rule_unconditional(self) -> None:
        rules = parse_rules("rules:\n  - {id: q1_required, type: required, variable: Q1}\n")
        rule = _get(rules, "q1_required")
        assert isinstance(rule, RequiredRule)
        assert rule.variable == "Q1"
        assert rule.when is None

    def test_required_rule_conditional(self) -> None:
        rules = parse_rules(
            """
rules:
  - id: q2_required_if_q1_yes
    type: required
    variable: Q2
    when: "Q1 == 'Yes'"
"""
        )
        rule = _get(rules, "q2_required_if_q1_yes")
        assert isinstance(rule, RequiredRule)
        assert rule.when is not None
        assert rule.when.evaluate({"Q1": "Yes"}) is True

    def test_required_rule_missing_variable_raises(self) -> None:
        with pytest.raises(RuleParseError, match="missing required field 'variable'"):
            parse_rules("rules:\n  - {id: q1_required, type: required}\n")


class TestSkipLogicRulePassAndFail:
    def test_skip_logic_rule_valid(self) -> None:
        rules = parse_rules(
            """
rules:
  - id: q2_gate
    type: skip_logic
    when: "Q1 == 'Yes'"
    then_required: [Q2]
    else_variables: [Q2]
"""
        )
        rule = _get(rules, "q2_gate")
        assert isinstance(rule, SkipLogicRule)
        assert rule.then_required == ("Q2",)
        assert rule.else_variables == ("Q2",)

    def test_skip_logic_rule_empty_then_required_raises(self) -> None:
        with pytest.raises(InvalidRuleDefinitionError, match="then_required cannot be empty"):
            parse_rules(
                """
rules:
  - id: q2_gate
    type: skip_logic
    when: "Q1 == 'Yes'"
    then_required: []
"""
            )

    def test_skip_logic_rule_duplicate_then_required_raises(self) -> None:
        with pytest.raises(InvalidRuleDefinitionError, match="duplicate variable"):
            parse_rules(
                """
rules:
  - id: q2_gate
    type: skip_logic
    when: "Q1 == 'Yes'"
    then_required: [Q2, Q2]
"""
            )


class TestSumEqualsRulePassAndFail:
    def test_sum_equals_rule_valid(self) -> None:
        rules = parse_rules(
            """
rules:
  - id: sum_to_100
    type: sum_equals
    variables: [S9_1, S9_2]
    target: 100
    tolerance: 0.5
"""
        )
        rule = _get(rules, "sum_to_100")
        assert isinstance(rule, SumEqualsRule)
        assert rule.variables == ("S9_1", "S9_2")
        assert rule.target == 100
        assert rule.tolerance == 0.5

    def test_sum_equals_rule_single_variable_raises(self) -> None:
        with pytest.raises(InvalidRuleDefinitionError, match="at least 2 variables"):
            parse_rules(
                """
rules:
  - id: sum_to_100
    type: sum_equals
    variables: [S9_1]
    target: 100
"""
            )

    def test_sum_equals_rule_negative_tolerance_raises(self) -> None:
        with pytest.raises(InvalidRuleDefinitionError, match="tolerance cannot be negative"):
            parse_rules(
                """
rules:
  - id: sum_to_100
    type: sum_equals
    variables: [S9_1, S9_2]
    target: 100
    tolerance: -1
"""
            )

    def test_sum_equals_rule_duplicate_variable_raises(self) -> None:
        with pytest.raises(InvalidRuleDefinitionError, match="duplicate variable"):
            parse_rules(
                """
rules:
  - id: sum_to_100
    type: sum_equals
    variables: [S9_1, S9_1]
    target: 100
"""
            )


class TestMaxSelectionsRulePassAndFail:
    def test_max_selections_rule_valid(self) -> None:
        rules = parse_rules(
            "rules:\n  - {id: max3, type: max_selections, variable: Q8, max_selections: 3}\n"
        )
        rule = _get(rules, "max3")
        assert isinstance(rule, MaxSelectionsRule)
        assert rule.max_selections == 3

    def test_max_selections_rule_zero_raises(self) -> None:
        with pytest.raises(InvalidRuleDefinitionError, match="max_selections must be >= 1"):
            parse_rules(
                "rules:\n  - {id: max3, type: max_selections, variable: Q8, max_selections: 0}\n"
            )


class TestExclusiveCategoryRulePassAndFail:
    def test_exclusive_category_rule_valid(self) -> None:
        rules = parse_rules(
            "rules:\n  - {id: excl, type: exclusive_category, variable: Q13, "
            "exclusive_codes: [7]}\n"
        )
        rule = _get(rules, "excl")
        assert isinstance(rule, ExclusiveCategoryRule)
        assert rule.exclusive_codes == (7,)

    def test_exclusive_category_rule_empty_codes_raises(self) -> None:
        with pytest.raises(InvalidRuleDefinitionError, match="exclusive_codes cannot be empty"):
            parse_rules(
                "rules:\n  - {id: excl, type: exclusive_category, variable: Q13, "
                "exclusive_codes: []}\n"
            )

    def test_exclusive_category_rule_duplicate_codes_raises(self) -> None:
        with pytest.raises(InvalidRuleDefinitionError, match="duplicate code"):
            parse_rules(
                "rules:\n  - {id: excl, type: exclusive_category, variable: Q13, "
                "exclusive_codes: [7, 7]}\n"
            )


class TestRankRulePassAndFail:
    def test_rank_rule_valid(self) -> None:
        rules = parse_rules(
            """
rules:
  - id: rank_q10
    type: rank
    rank_variables: [Q10_1, Q10_2, Q10_3]
    exclusive_flag_variable: Q10ex_98
    min_ranked: 1
    max_ranked: 3
    min_rank_value: 1
    max_rank_value: 3
"""
        )
        rule = _get(rules, "rank_q10")
        assert isinstance(rule, RankRule)
        assert rule.rank_variables == ("Q10_1", "Q10_2", "Q10_3")
        assert rule.max_rank_value == 3

    def test_rank_rule_defaults(self) -> None:
        rules = parse_rules(
            "rules:\n  - {id: rank_q10, type: rank, rank_variables: [Q10_1]}\n"
        )
        rule = _get(rules, "rank_q10")
        assert isinstance(rule, RankRule)
        assert rule.min_ranked == 1
        assert rule.max_ranked is None
        assert rule.exclusive_flag_variable is None

    def test_rank_rule_max_ranked_exceeding_variable_count_raises(self) -> None:
        with pytest.raises(InvalidRuleDefinitionError, match="out of bounds"):
            parse_rules(
                "rules:\n  - {id: rank_q10, type: rank, rank_variables: [Q10_1], "
                "max_ranked: 5}\n"
            )

    def test_rank_rule_min_greater_than_max_rank_value_raises(self) -> None:
        with pytest.raises(InvalidRuleDefinitionError, match="min_rank_value"):
            parse_rules(
                "rules:\n  - {id: rank_q10, type: rank, rank_variables: [Q10_1], "
                "min_rank_value: 5, max_rank_value: 1}\n"
            )

    def test_rank_rule_only_other_variable_without_text_raises(self) -> None:
        with pytest.raises(InvalidRuleDefinitionError, match="other_variable and other_text_variable"):
            parse_rules(
                "rules:\n  - {id: rank_q10, type: rank, rank_variables: [Q10_1], "
                "other_variable: Q10_98}\n"
            )

    def test_rank_rule_empty_rank_variables_raises(self) -> None:
        with pytest.raises(InvalidRuleDefinitionError, match="cannot be empty"):
            parse_rules("rules:\n  - {id: rank_q10, type: rank, rank_variables: []}\n")

    def test_rank_rule_duplicate_rank_variables_raises(self) -> None:
        with pytest.raises(InvalidRuleDefinitionError, match="duplicate variable"):
            parse_rules(
                "rules:\n  - {id: rank_q10, type: rank, rank_variables: [Q10_1, Q10_1]}\n"
            )


class TestSeverityAndMessage:
    def test_default_severity_is_error(self) -> None:
        rules = parse_rules("rules:\n  - {id: r1, type: required, variable: Q1}\n")
        assert _get(rules, "r1").severity is Severity.ERROR

    def test_explicit_severity(self) -> None:
        rules = parse_rules(
            "rules:\n  - {id: r1, type: required, variable: Q1, severity: warning}\n"
        )
        assert _get(rules, "r1").severity is Severity.WARNING

    def test_unrecognized_severity_raises(self) -> None:
        with pytest.raises(RuleParseError, match="unrecognized value"):
            parse_rules(
                "rules:\n  - {id: r1, type: required, variable: Q1, severity: critical}\n"
            )

    def test_custom_message(self) -> None:
        rules = parse_rules(
            'rules:\n  - {id: r1, type: required, variable: Q1, message: "Please answer Q1"}\n'
        )
        assert _get(rules, "r1").message == "Please answer Q1"

    def test_default_message_is_none(self) -> None:
        rules = parse_rules("rules:\n  - {id: r1, type: required, variable: Q1}\n")
        assert _get(rules, "r1").message is None


class TestFieldTypeValidationErrors:
    def test_require_str_wrong_type_raises(self) -> None:
        with pytest.raises(RuleParseError, match="field 'id' must be a non-empty string"):
            parse_rules("rules:\n  - {id: 123, type: required, variable: Q1}\n")

    def test_require_str_blank_raises(self) -> None:
        with pytest.raises(RuleParseError, match="field 'variable' must be a non-empty string"):
            parse_rules("rules:\n  - {id: r1, type: required, variable: '   '}\n")

    def test_optional_str_wrong_type_raises(self) -> None:
        with pytest.raises(RuleParseError, match="field 'message' must be a string"):
            parse_rules(
                "rules:\n  - {id: r1, type: required, variable: Q1, message: 123}\n"
            )

    def test_require_int_wrong_type_raises(self) -> None:
        with pytest.raises(RuleParseError, match="field 'max_selections' must be an integer"):
            parse_rules(
                "rules:\n  - {id: r1, type: max_selections, variable: Q8, "
                "max_selections: 'two'}\n"
            )

    def test_optional_int_wrong_type_raises(self) -> None:
        with pytest.raises(RuleParseError, match="field 'min_ranked' must be an integer"):
            parse_rules(
                "rules:\n  - {id: r1, type: rank, rank_variables: [Q10_1], "
                "min_ranked: 'one'}\n"
            )

    def test_require_number_wrong_type_raises(self) -> None:
        with pytest.raises(RuleParseError, match="field 'target' must be a number"):
            parse_rules(
                "rules:\n  - {id: r1, type: sum_equals, variables: [A, B], "
                "target: 'one hundred'}\n"
            )

    def test_optional_number_wrong_type_raises(self) -> None:
        with pytest.raises(RuleParseError, match="field 'tolerance' must be a number"):
            parse_rules(
                "rules:\n  - {id: r1, type: sum_equals, variables: [A, B], "
                "target: 100, tolerance: 'lots'}\n"
            )

    def test_require_list_of_str_wrong_type_raises(self) -> None:
        with pytest.raises(RuleParseError, match="field 'variables' must be a list of strings"):
            parse_rules(
                "rules:\n  - {id: r1, type: sum_equals, variables: 'not a list', target: 100}\n"
            )

    def test_optional_list_of_str_wrong_type_raises(self) -> None:
        with pytest.raises(
            RuleParseError, match="field 'else_variables' must be a list of strings"
        ):
            parse_rules(
                """
rules:
  - id: r1
    type: skip_logic
    when: "Q1 == 'Yes'"
    then_required: [Q2]
    else_variables: "not a list"
"""
            )

    def test_require_list_of_int_wrong_type_raises(self) -> None:
        with pytest.raises(
            RuleParseError, match="field 'exclusive_codes' must be a list of integers"
        ):
            parse_rules(
                "rules:\n  - {id: r1, type: exclusive_category, variable: Q13, "
                "exclusive_codes: ['seven']}\n"
            )


class TestTopLevelParsingErrors:
    def test_not_a_mapping_raises(self) -> None:
        with pytest.raises(RuleParseError, match="must be a mapping"):
            parse_rules("- just\n- a\n- list\n")

    def test_missing_rules_key_raises(self) -> None:
        with pytest.raises(RuleParseError, match="missing required field 'rules'"):
            parse_rules("not_rules: []\n")

    def test_rules_not_a_list_raises(self) -> None:
        with pytest.raises(RuleParseError, match="'rules' must be a list"):
            parse_rules("rules: {}\n")

    def test_invalid_yaml_raises(self) -> None:
        with pytest.raises(RuleParseError, match="not valid YAML"):
            parse_rules("rules: [unterminated\n")

    def test_unrecognized_rule_type_raises(self) -> None:
        with pytest.raises(RuleParseError, match="unrecognized type 'bogus'"):
            parse_rules("rules:\n  - {id: r1, type: bogus}\n")

    def test_missing_id_raises(self) -> None:
        with pytest.raises(RuleParseError, match="missing required field 'id'"):
            parse_rules("rules:\n  - {type: required, variable: Q1}\n")

    def test_duplicate_rule_id_raises(self) -> None:
        with pytest.raises(RuleParseError, match="Duplicate rule id 'r1'"):
            parse_rules(
                """
rules:
  - {id: r1, type: required, variable: Q1}
  - {id: r1, type: required, variable: Q2}
"""
            )

    def test_rule_entry_not_a_mapping_raises(self) -> None:
        with pytest.raises(RuleParseError, match=r"rules\[0\] must be a mapping"):
            parse_rules("rules:\n  - just a string\n")


class TestLoadRulesFromFile:
    def test_loads_from_a_real_file(self, tmp_path: Path) -> None:
        path = tmp_path / "rules.yaml"
        path.write_text("rules:\n  - {id: r1, type: required, variable: Q1}\n", encoding="utf-8")
        rules = load_rules(path)
        assert len(rules) == 1

    def test_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(RuleParseError, match="not found"):
            load_rules(tmp_path / "does_not_exist.yaml")

    def test_error_message_includes_file_path(self, tmp_path: Path) -> None:
        import re

        path = tmp_path / "bad.yaml"
        path.write_text("rules: {}\n", encoding="utf-8")
        with pytest.raises(RuleParseError, match=re.escape(str(path))):
            load_rules(path)

    def test_unreadable_file_raises_rule_parse_error(self, tmp_path: Path) -> None:
        import os

        path = tmp_path / "rules.yaml"
        path.write_text("rules: []\n", encoding="utf-8")
        path.chmod(0o000)
        try:
            if os.access(path, os.R_OK):
                pytest.skip("running as a user that bypasses file permissions (e.g. root)")
            with pytest.raises(RuleParseError, match="Could not read"):
                load_rules(path)
        finally:
            path.chmod(0o644)
