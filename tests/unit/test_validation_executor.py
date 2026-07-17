"""Unit tests for insightengine.validation.executor.

``TestAcceptanceCriterion`` is the phase's actual acceptance test: a full
rule set run against a synthetic dataset, with results compared against
a hand-computed expected set — not just "some errors were found."
"""

from __future__ import annotations

import pytest

from insightengine.core.codebook import (
    Category,
    Codebook,
    DerivedVariable,
    GridQuestion,
    MultiQuestion,
    NumericQuestion,
    RankingQuestion,
    SingleQuestion,
    TextQuestion,
)
from insightengine.core.exceptions import RuleEvaluationError, UnknownVariableError
from insightengine.core.types import Severity
from insightengine.data.backends.pandas_backend import PandasBackend
from insightengine.data.base import RawTable
from insightengine.rules.dsl import (
    ExclusiveCategoryRule,
    MaxSelectionsRule,
    RangeRule,
    RankRule,
    RequiredRule,
    SkipLogicRule,
    SumEqualsRule,
)
from insightengine.rules.evaluator import compile_expression
from insightengine.validation.context import ValidationContext
from insightengine.validation.executor import validate


def _context(codebook: Codebook, columns: dict[str, tuple[object, ...]], row_count: int) -> ValidationContext:
    table = RawTable(columns=columns, row_count=row_count)
    data = PandasBackend().load(table)
    return ValidationContext(codebook=codebook, data=data)


class TestCoerceCategoryCode:
    """Direct tests of the internal coercion helper - covers edge cases
    (bool, a genuinely fractional float) that a round-trip through the
    pandas backend doesn't naturally exercise.
    """

    def test_bool_is_never_a_valid_category_code(self) -> None:
        from insightengine.validation.executor import _coerce_category_code

        assert _coerce_category_code(True) is None
        assert _coerce_category_code(False) is None

    def test_fractional_float_is_rejected(self) -> None:
        from insightengine.validation.executor import _coerce_category_code

        assert _coerce_category_code(1.5) is None

    def test_whole_number_float_coerces_to_int(self) -> None:
        from insightengine.validation.executor import _coerce_category_code

        assert _coerce_category_code(2.0) == 2

    def test_plain_int_passes_through(self) -> None:
        from insightengine.validation.executor import _coerce_category_code

        assert _coerce_category_code(3) == 3

    def test_non_numeric_value_returns_none(self) -> None:
        from insightengine.validation.executor import _coerce_category_code

        assert _coerce_category_code("not a code") is None


class TestRankRuleDeferred:
    def test_rank_rule_raises_immediately(self) -> None:
        codebook = Codebook([])
        context = _context(codebook, {}, 0)
        rank_rule = RankRule(id="r1", rank_variables=("Q10_1",))
        with pytest.raises(RuleEvaluationError, match="deferred"):
            validate(context, [rank_rule])


class TestDomainChecksSingleQuestion:
    def test_valid_category_passes(self) -> None:
        codebook = Codebook(
            [
                SingleQuestion(
                    id="Q1",
                    label="Car?",
                    categories=(Category(code=1, label="Yes"), Category(code=2, label="No")),
                )
            ]
        )
        context = _context(codebook, {"Q1": (1, 2)}, 2)
        collector = validate(context, [])
        assert len(collector) == 0

    def test_invalid_category_code_flagged(self) -> None:

        codebook = Codebook(
            [SingleQuestion(id="Q1", label="Car?", categories=(Category(code=1, label="Yes"),))]
        )
        context = _context(codebook, {"Q1": (1, 99)}, 2)
        collector = validate(context, [])
        assert len(collector) == 1
        assert collector.results[0].row_index == 1
        assert "not a valid category code" in collector.results[0].message

    def test_required_but_missing_flagged(self) -> None:

        codebook = Codebook(
            [
                SingleQuestion(
                    id="Q1",
                    label="Car?",
                    required=True,
                    categories=(Category(code=1, label="Yes"),),
                )
            ]
        )
        context = _context(codebook, {"Q1": (1, None)}, 2)
        collector = validate(context, [])
        assert len(collector) == 1
        assert collector.results[0].row_index == 1
        assert "required but missing" in collector.results[0].message

    def test_not_required_and_missing_is_fine(self) -> None:

        codebook = Codebook(
            [
                SingleQuestion(
                    id="Q1", label="Car?", required=False, categories=(Category(code=1, label="Yes"),)
                )
            ]
        )
        context = _context(codebook, {"Q1": (1, None)}, 2)
        collector = validate(context, [])
        assert len(collector) == 0

    def test_question_without_a_column_is_skipped(self) -> None:

        codebook = Codebook(
            [SingleQuestion(id="Q1", label="Car?", categories=(Category(code=1, label="Yes"),))]
        )
        context = _context(codebook, {}, 0)
        collector = validate(context, [])
        assert len(collector) == 0


class TestDomainChecksMultiQuestion:
    def test_valid_selection_passes(self) -> None:

        codebook = Codebook(
            [
                MultiQuestion(
                    id="Q8", label="Brands", categories=(Category(code=1, label="A"), Category(code=2, label="B"))
                )
            ]
        )
        context = _context(codebook, {"Q8": ((1,), (1, 2))}, 2)
        collector = validate(context, [])
        assert len(collector) == 0

    def test_non_collection_value_flagged(self) -> None:

        codebook = Codebook(
            [MultiQuestion(id="Q8", label="Brands", categories=(Category(code=1, label="A"),))]
        )
        context = _context(codebook, {"Q8": ("not a list",)}, 1)
        collector = validate(context, [])
        assert len(collector) == 1
        assert "not a selection" in collector.results[0].message

    def test_invalid_category_code_flagged(self) -> None:

        codebook = Codebook(
            [MultiQuestion(id="Q8", label="Brands", categories=(Category(code=1, label="A"),))]
        )
        context = _context(codebook, {"Q8": ((1, 99),)}, 1)
        collector = validate(context, [])
        assert len(collector) == 1
        assert "invalid category codes" in collector.results[0].message

    def test_exceeding_declared_max_selections_flagged(self) -> None:

        codebook = Codebook(
            [
                MultiQuestion(
                    id="Q8",
                    label="Brands",
                    categories=(Category(code=1, label="A"), Category(code=2, label="B")),
                    max_selections=1,
                )
            ]
        )
        context = _context(codebook, {"Q8": ((1, 2),)}, 1)
        collector = validate(context, [])
        assert len(collector) == 1
        assert "exceeding the declared maximum" in collector.results[0].message


class TestDomainChecksNumericQuestion:
    def test_within_bounds_passes(self) -> None:
        codebook = Codebook([NumericQuestion(id="AGE", label="Age", min_value=18, max_value=99)])
        context = _context(codebook, {"AGE": (25,)}, 1)
        collector = validate(context, [])
        assert len(collector) == 0

    def test_below_minimum_flagged(self) -> None:
        codebook = Codebook([NumericQuestion(id="AGE", label="Age", min_value=18)])
        context = _context(codebook, {"AGE": (10,)}, 1)
        collector = validate(context, [])
        assert len(collector) == 1
        assert "below the minimum" in collector.results[0].message

    def test_above_maximum_flagged(self) -> None:
        codebook = Codebook([NumericQuestion(id="AGE", label="Age", max_value=99)])
        context = _context(codebook, {"AGE": (150,)}, 1)
        collector = validate(context, [])
        assert len(collector) == 1
        assert "above the maximum" in collector.results[0].message

    def test_non_numeric_value_flagged(self) -> None:
        codebook = Codebook([NumericQuestion(id="AGE", label="Age")])
        context = _context(codebook, {"AGE": ("not a number",)}, 1)
        collector = validate(context, [])
        assert len(collector) == 1
        assert "not numeric" in collector.results[0].message


class TestDomainChecksTextQuestion:
    def test_within_max_length_passes(self) -> None:
        codebook = Codebook([TextQuestion(id="COMMENTS", label="Comments", max_length=10)])
        context = _context(codebook, {"COMMENTS": ("short",)}, 1)
        collector = validate(context, [])
        assert len(collector) == 0

    def test_exceeding_max_length_flagged(self) -> None:
        codebook = Codebook([TextQuestion(id="COMMENTS", label="Comments", max_length=5)])
        context = _context(codebook, {"COMMENTS": ("this is too long",)}, 1)
        collector = validate(context, [])
        assert len(collector) == 1
        assert "exceeding" in collector.results[0].message

    def test_non_text_value_flagged(self) -> None:
        codebook = Codebook([TextQuestion(id="COMMENTS", label="Comments")])
        context = _context(codebook, {"COMMENTS": (123,)}, 1)
        collector = validate(context, [])
        assert len(collector) == 1
        assert "not text" in collector.results[0].message


class TestDomainChecksSkippedTypes:
    def test_derived_variable_without_column_skipped(self) -> None:
        codebook = Codebook(
            [
                NumericQuestion(id="AGE", label="Age"),
                DerivedVariable(id="BAND", label="Band", expression="f(AGE)", depends_on=("AGE",)),
            ]
        )
        context = _context(codebook, {"AGE": (25,)}, 1)
        collector = validate(context, [])
        assert len(collector) == 0

    def test_ranking_question_skipped(self) -> None:

        codebook = Codebook(
            [
                RankingQuestion(
                    id="Q10",
                    label="Rank",
                    items=(Category(code=1, label="A"),),
                    rank_count=1,
                )
            ]
        )
        # Even a wildly invalid value shouldn't be flagged - RankingQuestion
        # domain checks are deferred alongside RankRule execution.
        context = _context(codebook, {"Q10": ("nonsense",)}, 1)
        collector = validate(context, [])
        assert len(collector) == 0

    def test_grid_question_itself_has_no_domain_check_but_rows_do(self) -> None:

        row = SingleQuestion(id="Q2_1", label="Row", categories=(Category(code=1, label="A"),))
        grid = GridQuestion(id="Q2", label="Grid", rows=(row,), columns=(Category(code=1, label="A"),))
        codebook = Codebook([grid])
        context = _context(codebook, {"Q2_1": (99,)}, 1)  # invalid for the row
        collector = validate(context, [])
        assert len(collector) == 1
        assert collector.results[0].rule_id == "__domain__:Q2_1:category"


class TestRangeRuleExecution:
    def test_violation_flagged(self) -> None:
        codebook = Codebook([NumericQuestion(id="AGE", label="Age")])
        context = _context(codebook, {"AGE": (10, 30, 150)}, 3)
        rule = RangeRule(id="age_range", when=compile_expression("AGE < 18 or AGE > 99"))
        collector = validate(context, [rule])
        assert {r.row_index for r in collector.by_rule("age_range")} == {0, 2}

    def test_no_violation_when_all_in_range(self) -> None:
        codebook = Codebook([NumericQuestion(id="AGE", label="Age")])
        context = _context(codebook, {"AGE": (25, 30)}, 2)
        rule = RangeRule(id="age_range", when=compile_expression("AGE < 18 or AGE > 99"))
        collector = validate(context, [rule])
        assert len(collector.by_rule("age_range")) == 0

    def test_custom_message_used(self) -> None:
        codebook = Codebook([NumericQuestion(id="AGE", label="Age")])
        context = _context(codebook, {"AGE": (5,)}, 1)
        rule = RangeRule(
            id="age_range", when=compile_expression("AGE < 18"), message="Too young!"
        )
        collector = validate(context, [rule])
        assert collector.by_rule("age_range")[0].message == "Too young!"


class TestRequiredRuleExecution:
    def test_unconditional_missing_flagged(self) -> None:
        codebook = Codebook([TextQuestion(id="Q1", label="Q1")])
        context = _context(codebook, {"Q1": ("answer", None)}, 2)
        rule = RequiredRule(id="q1_required", variable="Q1")
        collector = validate(context, [rule])
        assert [r.row_index for r in collector.by_rule("q1_required")] == [1]

    def test_conditional_gate_true_and_missing_flagged(self) -> None:
        codebook = Codebook([TextQuestion(id="Q1", label="Q1"), TextQuestion(id="Q2", label="Q2")])
        context = _context(codebook, {"Q1": ("Yes", "No"), "Q2": (None, None)}, 2)
        rule = RequiredRule(id="q2_conditional", variable="Q2", when=compile_expression("Q1 == 'Yes'"))
        collector = validate(context, [rule])
        assert [r.row_index for r in collector.by_rule("q2_conditional")] == [0]

    def test_unknown_variable_raises(self) -> None:
        codebook = Codebook([])
        context = _context(codebook, {"Q1": ("x",)}, 1)
        rule = RequiredRule(id="bad", variable="DOES_NOT_EXIST")
        with pytest.raises(UnknownVariableError):
            validate(context, [rule])


class TestSkipLogicRuleExecution:
    def test_then_required_violation(self) -> None:
        codebook = Codebook([TextQuestion(id="Q1", label="Q1"), TextQuestion(id="Q2", label="Q2")])
        context = _context(codebook, {"Q1": ("Yes",), "Q2": (None,)}, 1)
        rule = SkipLogicRule(
            id="q2_gate",
            when=compile_expression("Q1 == 'Yes'"),
            then_required=("Q2",),
        )
        collector = validate(context, [rule])
        assert len(collector.by_rule("q2_gate")) == 1

    def test_else_variables_violation(self) -> None:
        codebook = Codebook([TextQuestion(id="Q1", label="Q1"), TextQuestion(id="Q2", label="Q2")])
        context = _context(codebook, {"Q1": ("No",), "Q2": ("should be blank",)}, 1)
        rule = SkipLogicRule(
            id="q2_gate",
            when=compile_expression("Q1 == 'Yes'"),
            then_required=("Q2",),
            else_variables=("Q2",),
        )
        collector = validate(context, [rule])
        assert len(collector.by_rule("q2_gate")) == 1
        assert "should be blank" in collector.by_rule("q2_gate")[0].message

    def test_both_branches_satisfied_no_violations(self) -> None:
        codebook = Codebook([TextQuestion(id="Q1", label="Q1"), TextQuestion(id="Q2", label="Q2")])
        context = _context(
            codebook, {"Q1": ("Yes", "No"), "Q2": ("answered", None)}, 2
        )
        rule = SkipLogicRule(
            id="q2_gate",
            when=compile_expression("Q1 == 'Yes'"),
            then_required=("Q2",),
            else_variables=("Q2",),
        )
        collector = validate(context, [rule])
        assert len(collector.by_rule("q2_gate")) == 0

    def test_unknown_target_variable_raises(self) -> None:
        codebook = Codebook([TextQuestion(id="Q1", label="Q1")])
        context = _context(codebook, {"Q1": ("Yes",)}, 1)
        rule = SkipLogicRule(
            id="q2_gate",
            when=compile_expression("Q1 == 'Yes'"),
            then_required=("DOES_NOT_EXIST",),
        )
        with pytest.raises(UnknownVariableError):
            validate(context, [rule])


class TestSumEqualsRuleExecution:
    def test_valid_sum_no_violation(self) -> None:
        codebook = Codebook([NumericQuestion(id="A", label="A"), NumericQuestion(id="B", label="B")])
        context = _context(codebook, {"A": (40,), "B": (60,)}, 1)
        rule = SumEqualsRule(id="sum100", variables=("A", "B"), target=100)
        collector = validate(context, [rule])
        assert len(collector.by_rule("sum100")) == 0

    def test_invalid_sum_flagged(self) -> None:
        codebook = Codebook([NumericQuestion(id="A", label="A"), NumericQuestion(id="B", label="B")])
        context = _context(codebook, {"A": (40,), "B": (50,)}, 1)
        rule = SumEqualsRule(id="sum100", variables=("A", "B"), target=100)
        collector = validate(context, [rule])
        assert len(collector.by_rule("sum100")) == 1

    def test_within_tolerance_no_violation(self) -> None:
        codebook = Codebook([NumericQuestion(id="A", label="A"), NumericQuestion(id="B", label="B")])
        context = _context(codebook, {"A": (40,), "B": (59.5,)}, 1)
        rule = SumEqualsRule(id="sum100", variables=("A", "B"), target=100, tolerance=1)
        collector = validate(context, [rule])
        assert len(collector.by_rule("sum100")) == 0

    def test_missing_value_skipped_not_flagged(self) -> None:
        codebook = Codebook([NumericQuestion(id="A", label="A"), NumericQuestion(id="B", label="B")])
        context = _context(codebook, {"A": (40,), "B": (None,)}, 1)
        rule = SumEqualsRule(id="sum100", variables=("A", "B"), target=100)
        collector = validate(context, [rule])
        assert len(collector.by_rule("sum100")) == 0

    def test_non_numeric_value_raises(self) -> None:
        codebook = Codebook([NumericQuestion(id="A", label="A"), NumericQuestion(id="B", label="B")])
        context = _context(codebook, {"A": ("oops",), "B": (50,)}, 1)
        rule = SumEqualsRule(id="sum100", variables=("A", "B"), target=100)
        with pytest.raises(RuleEvaluationError, match="non-numeric"):
            validate(context, [rule])


class TestMaxSelectionsRuleExecution:
    def test_within_max_no_violation(self) -> None:
        codebook = Codebook([])
        context = _context(codebook, {"Q8": ((1, 2),)}, 1)
        rule = MaxSelectionsRule(id="max2", variable="Q8", max_selections=2)
        collector = validate(context, [rule])
        assert len(collector.by_rule("max2")) == 0

    def test_exceeding_max_flagged(self) -> None:
        codebook = Codebook([])
        context = _context(codebook, {"Q8": ((1, 2, 3),)}, 1)
        rule = MaxSelectionsRule(id="max2", variable="Q8", max_selections=2)
        collector = validate(context, [rule])
        assert len(collector.by_rule("max2")) == 1

    def test_none_value_skipped(self) -> None:
        codebook = Codebook([])
        context = _context(codebook, {"Q8": (None,)}, 1)
        rule = MaxSelectionsRule(id="max2", variable="Q8", max_selections=2)
        collector = validate(context, [rule])
        assert len(collector.by_rule("max2")) == 0

    def test_non_collection_value_raises(self) -> None:
        codebook = Codebook([])
        context = _context(codebook, {"Q8": ("not a list",)}, 1)
        rule = MaxSelectionsRule(id="max2", variable="Q8", max_selections=2)
        with pytest.raises(RuleEvaluationError, match="expected a collection"):
            validate(context, [rule])


class TestExclusiveCategoryRuleExecution:
    def test_exclusive_alone_no_violation(self) -> None:
        codebook = Codebook([])
        context = _context(codebook, {"Q13": ((7,),)}, 1)
        rule = ExclusiveCategoryRule(id="excl", variable="Q13", exclusive_codes=(7,))
        collector = validate(context, [rule])
        assert len(collector.by_rule("excl")) == 0

    def test_others_alone_no_violation(self) -> None:
        codebook = Codebook([])
        context = _context(codebook, {"Q13": ((1, 2),)}, 1)
        rule = ExclusiveCategoryRule(id="excl", variable="Q13", exclusive_codes=(7,))
        collector = validate(context, [rule])
        assert len(collector.by_rule("excl")) == 0

    def test_exclusive_combined_with_other_flagged(self) -> None:
        codebook = Codebook([])
        context = _context(codebook, {"Q13": ((1, 7),)}, 1)
        rule = ExclusiveCategoryRule(id="excl", variable="Q13", exclusive_codes=(7,))
        collector = validate(context, [rule])
        assert len(collector.by_rule("excl")) == 1

    def test_none_value_skipped(self) -> None:
        codebook = Codebook([])
        context = _context(codebook, {"Q13": (None,)}, 1)
        rule = ExclusiveCategoryRule(id="excl", variable="Q13", exclusive_codes=(7,))
        collector = validate(context, [rule])
        assert len(collector.by_rule("excl")) == 0


class TestAcceptanceCriterion:
    """The phase's actual acceptance test: a full rule set against a
    synthetic dataset, hand-computed expected results.

    Dataset (4 respondents):

    | row | AGE | Q1  | Q2   | S9_1 | S9_2 | Q8      |
    |-----|-----|-----|------|------|------|---------|
    | 0   | 15  | Yes | None | 40   | 60   | (1,2)   |  <- AGE_RANGE violation (15<18), Q2 required violation
    | 1   | 30  | No  | None | 40   | 50   | (1,2,3) |  <- SUM violation (90!=100), MAX_SELECTIONS violation (3>2)
    | 2   | 45  | Yes | "ok" | 50   | 50   | (1,)    |  <- no violations
    | 3   | 150 | No  | "x"  | 50   | 50   | (2,)    |  <- AGE_RANGE violation (150>99), SkipLogic else-branch violation (Q2 should be blank when Q1 != Yes)
    """

    def test_full_rule_set_matches_hand_computed_expectations(self) -> None:
        codebook = Codebook(
            [
                NumericQuestion(id="AGE", label="Age"),
                TextQuestion(id="Q1", label="Own a car?"),
                TextQuestion(id="Q2", label="Which model?"),
                NumericQuestion(id="S9_1", label="Allocation 1"),
                NumericQuestion(id="S9_2", label="Allocation 2"),
            ]
        )
        context = _context(
            codebook,
            {
                "AGE": (15, 30, 45, 150),
                "Q1": ("Yes", "No", "Yes", "No"),
                "Q2": (None, None, "ok", "x"),
                "S9_1": (40, 40, 50, 50),
                "S9_2": (60, 50, 50, 50),
                "Q8": ((1, 2), (1, 2, 3), (1,), (2,)),
            },
            4,
        )

        rules = [
            RangeRule(id="age_range", when=compile_expression("AGE < 18 or AGE > 99")),
            SkipLogicRule(
                id="q2_gate",
                when=compile_expression("Q1 == 'Yes'"),
                then_required=("Q2",),
                else_variables=("Q2",),
            ),
            SumEqualsRule(id="sum100", variables=("S9_1", "S9_2"), target=100),
            MaxSelectionsRule(id="max2", variable="Q8", max_selections=2),
        ]

        collector = validate(context, rules)

        assert {r.row_index for r in collector.by_rule("age_range")} == {0, 3}
        assert {r.row_index for r in collector.by_rule("q2_gate")} == {0, 3}
        assert {r.row_index for r in collector.by_rule("sum100")} == {1}
        assert {r.row_index for r in collector.by_rule("max2")} == {1}

        # Row 2 has no violations from any rule at all.
        assert all(r.row_index != 2 for r in collector)

        # Exact total count, hand-computed: age_range(2) + q2_gate(2) +
        # sum100(1) + max2(1) = 6. No domain-check violations expected
        # since every value matches its question's own declared type.
        assert len(collector) == 6
