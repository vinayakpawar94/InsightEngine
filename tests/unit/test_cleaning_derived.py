"""Unit tests for insightengine.cleaning.derived.

``TestAcceptanceCriterion`` is this phase's actual acceptance test: a
3-deep derived-variable dependency chain that must compute correct
values, not just resolve in the correct order (which Phase 2 already
tested at the Codebook level).
"""

from __future__ import annotations

import pytest

from insightengine.cleaning.derived import DerivedVariableTransformer
from insightengine.core.codebook import Codebook, DerivedVariable, NumericQuestion
from insightengine.core.exceptions import TransformationError
from insightengine.data.base import RawTable


class TestBasicDerivation:
    def test_single_derived_variable(self) -> None:
        codebook = Codebook(
            [
                NumericQuestion(id="A", label="A"),
                DerivedVariable(id="B", label="B", expression="A + 1", depends_on=("A",)),
            ]
        )
        table = RawTable(columns={"A": (1, 2, 3)}, row_count=3)
        result = DerivedVariableTransformer().apply(table, codebook)
        assert result.columns["B"] == (2, 3, 4)

    def test_derived_variable_referencing_multiple_base_variables(self) -> None:
        codebook = Codebook(
            [
                NumericQuestion(id="A", label="A"),
                NumericQuestion(id="B", label="B"),
                DerivedVariable(id="SUM", label="Sum", expression="A + B", depends_on=("A", "B")),
            ]
        )
        table = RawTable(columns={"A": (1, 2), "B": (10, 20)}, row_count=2)
        result = DerivedVariableTransformer().apply(table, codebook)
        assert result.columns["SUM"] == (11, 22)

    def test_no_derived_variables_returns_equivalent_table(self) -> None:
        codebook = Codebook([NumericQuestion(id="A", label="A")])
        table = RawTable(columns={"A": (1,)}, row_count=1)
        result = DerivedVariableTransformer().apply(table, codebook)
        assert result.columns == table.columns

    def test_base_columns_preserved_alongside_derived(self) -> None:
        codebook = Codebook(
            [
                NumericQuestion(id="A", label="A"),
                DerivedVariable(id="B", label="B", expression="A + 1", depends_on=("A",)),
            ]
        )
        table = RawTable(columns={"A": (5,)}, row_count=1)
        result = DerivedVariableTransformer().apply(table, codebook)
        assert result.columns["A"] == (5,)
        assert result.columns["B"] == (6,)


class TestAcceptanceCriterion:
    def test_three_deep_dependency_chain_computes_correct_values(self) -> None:
        codebook = Codebook(
            [
                NumericQuestion(id="AGE", label="Age"),
                DerivedVariable(
                    id="AGE_PLUS_ONE",
                    label="Age plus one",
                    expression="AGE + 1",
                    depends_on=("AGE",),
                ),
                DerivedVariable(
                    id="AGE_PLUS_ONE_TIMES_TWO",
                    label="(Age+1)*2",
                    expression="AGE_PLUS_ONE * 2",
                    depends_on=("AGE_PLUS_ONE",),
                ),
                DerivedVariable(
                    id="FINAL",
                    label="Final",
                    expression="AGE_PLUS_ONE_TIMES_TWO - AGE",
                    depends_on=("AGE_PLUS_ONE_TIMES_TWO", "AGE"),
                ),
            ]
        )
        table = RawTable(columns={"AGE": (10, 20, 30)}, row_count=3)
        result = DerivedVariableTransformer().apply(table, codebook)

        # Hand-computed expectation for AGE=10: (10+1)*2 - 10 = 12
        # AGE=20: (20+1)*2 - 20 = 22 ; AGE=30: (30+1)*2 - 30 = 32
        assert result.columns["AGE_PLUS_ONE"] == (11, 21, 31)
        assert result.columns["AGE_PLUS_ONE_TIMES_TWO"] == (22, 42, 62)
        assert result.columns["FINAL"] == (12, 22, 32)

    def test_order_scrambled_at_construction_still_computes_correctly(self) -> None:
        # Codebook already guarantees correct topological order regardless
        # of construction order (tested at Phase 2) - this test confirms
        # the transformer actually relies on that order rather than
        # accidentally depending on insertion order itself.
        age_plus_one = DerivedVariable(
            id="AGE_PLUS_ONE", label="x", expression="AGE + 1", depends_on=("AGE",)
        )
        final = DerivedVariable(
            id="FINAL", label="x", expression="AGE_PLUS_ONE * 10", depends_on=("AGE_PLUS_ONE",)
        )
        age = NumericQuestion(id="AGE", label="Age")
        codebook = Codebook([final, age, age_plus_one])  # deliberately scrambled

        table = RawTable(columns={"AGE": (5,)}, row_count=1)
        result = DerivedVariableTransformer().apply(table, codebook)
        assert result.columns["AGE_PLUS_ONE"] == (6,)
        assert result.columns["FINAL"] == (60,)


class TestDerivationErrors:
    def test_missing_base_column_raises_transformation_error(self) -> None:
        codebook = Codebook(
            [
                NumericQuestion(id="A", label="A"),
                DerivedVariable(id="B", label="B", expression="A + 1", depends_on=("A",)),
            ]
        )
        table = RawTable(columns={"OTHER": (1,)}, row_count=1)
        with pytest.raises(TransformationError, match="DerivedVariable 'B'"):
            DerivedVariableTransformer().apply(table, codebook)

    def test_unsafe_expression_rejected_at_apply_time(self) -> None:
        codebook = Codebook(
            [DerivedVariable(id="B", label="B", expression="__import__('os')")]
        )
        table = RawTable(columns={}, row_count=1)
        from insightengine.core.exceptions import UnsafeExpressionError

        with pytest.raises(UnsafeExpressionError):
            DerivedVariableTransformer().apply(table, codebook)
