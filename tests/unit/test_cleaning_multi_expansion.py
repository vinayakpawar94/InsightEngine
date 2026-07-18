"""Unit tests for insightengine.cleaning.multi_expansion."""

from __future__ import annotations

import pytest

from insightengine.cleaning.multi_expansion import MultiResponseExpansionTransformer
from insightengine.core.codebook import Category, Codebook, MultiQuestion
from insightengine.core.exceptions import TransformationError
from insightengine.data.base import RawTable


def _question(*, max_selections: int | None = None) -> MultiQuestion:
    return MultiQuestion(
        id="Q8",
        label="Brands",
        categories=(
            Category(code=1, label="A"),
            Category(code=2, label="B"),
            Category(code=3, label="C"),
        ),
        max_selections=max_selections,
    )


class TestDelimitedStringExpansion:
    def test_parses_comma_delimited_string(self) -> None:
        codebook = Codebook([_question()])
        table = RawTable(columns={"Q8": ("1,3",)}, row_count=1)
        result = MultiResponseExpansionTransformer().apply(table, codebook)
        assert result.columns["Q8"][0] == frozenset({1, 3})

    def test_custom_delimiter(self) -> None:
        codebook = Codebook([_question()])
        table = RawTable(columns={"Q8": ("1;2;3",)}, row_count=1)
        result = MultiResponseExpansionTransformer(delimiter=";").apply(table, codebook)
        assert result.columns["Q8"][0] == frozenset({1, 2, 3})

    def test_whitespace_around_tokens_stripped(self) -> None:
        codebook = Codebook([_question()])
        table = RawTable(columns={"Q8": (" 1 , 2 ",)}, row_count=1)
        result = MultiResponseExpansionTransformer().apply(table, codebook)
        assert result.columns["Q8"][0] == frozenset({1, 2})

    def test_none_value_stays_none(self) -> None:
        codebook = Codebook([_question()])
        table = RawTable(columns={"Q8": (None,)}, row_count=1)
        result = MultiResponseExpansionTransformer().apply(table, codebook)
        assert result.columns["Q8"][0] is None

    def test_empty_string_becomes_none(self) -> None:
        codebook = Codebook([_question()])
        table = RawTable(columns={"Q8": ("   ",)}, row_count=1)
        result = MultiResponseExpansionTransformer().apply(table, codebook)
        assert result.columns["Q8"][0] is None

    def test_single_code_no_delimiter(self) -> None:
        codebook = Codebook([_question()])
        table = RawTable(columns={"Q8": ("2",)}, row_count=1)
        result = MultiResponseExpansionTransformer().apply(table, codebook)
        assert result.columns["Q8"][0] == frozenset({2})

    def test_empty_tokens_from_double_or_trailing_delimiter_ignored(self) -> None:
        codebook = Codebook([_question()])
        table = RawTable(columns={"Q8": ("1,,2,",)}, row_count=1)
        result = MultiResponseExpansionTransformer().apply(table, codebook)
        assert result.columns["Q8"][0] == frozenset({1, 2})

    def test_non_numeric_token_raises(self) -> None:
        codebook = Codebook([_question()])
        table = RawTable(columns={"Q8": ("1,two",)}, row_count=1)
        with pytest.raises(TransformationError, match="could not parse 'two'"):
            MultiResponseExpansionTransformer().apply(table, codebook)

    def test_non_string_non_none_value_raises(self) -> None:
        codebook = Codebook([_question()])
        table = RawTable(columns={"Q8": (123,)}, row_count=1)
        with pytest.raises(TransformationError, match="expected a delimited string"):
            MultiResponseExpansionTransformer().apply(table, codebook)

    def test_already_expanded_column_left_untouched(self) -> None:
        codebook = Codebook([_question()])
        table = RawTable(columns={"Q8": (frozenset({1, 2}),)}, row_count=1)
        result = MultiResponseExpansionTransformer().apply(table, codebook)
        assert result is table

    def test_already_expanded_as_plain_tuple_left_untouched(self) -> None:
        codebook = Codebook([_question()])
        table = RawTable(columns={"Q8": ((1, 2),)}, row_count=1)
        result = MultiResponseExpansionTransformer().apply(table, codebook)
        assert result is table


class TestBinaryIndicatorExpansion:
    def test_merges_indicator_columns_into_one(self) -> None:
        codebook = Codebook([_question()])
        table = RawTable(
            columns={
                "Q8_1": ("1",),
                "Q8_2": ("0",),
                "Q8_3": ("1",),
            },
            row_count=1,
        )
        result = MultiResponseExpansionTransformer().apply(table, codebook)
        assert result.columns["Q8"][0] == frozenset({1, 3})
        assert "Q8_1" not in result.columns
        assert "Q8_2" not in result.columns
        assert "Q8_3" not in result.columns

    def test_accepts_int_and_bool_indicator_values(self) -> None:
        codebook = Codebook([_question()])
        table = RawTable(
            columns={"Q8_1": (1,), "Q8_2": (True,), "Q8_3": (0,)}, row_count=1
        )
        result = MultiResponseExpansionTransformer().apply(table, codebook)
        assert result.columns["Q8"][0] == frozenset({1, 2})

    def test_all_falsy_indicators_produce_empty_frozenset_not_none(self) -> None:
        # All indicators genuinely present and all "0" means "answered,
        # selected nothing" - a real, meaningful state distinct from
        # "no data at all" (None).
        codebook = Codebook([_question()])
        table = RawTable(
            columns={"Q8_1": ("0",), "Q8_2": ("0",), "Q8_3": ("0",)}, row_count=1
        )
        result = MultiResponseExpansionTransformer().apply(table, codebook)
        assert result.columns["Q8"][0] == frozenset()

    def test_all_indicators_none_produces_none(self) -> None:
        codebook = Codebook([_question()])
        table = RawTable(
            columns={"Q8_1": (None,), "Q8_2": (None,), "Q8_3": (None,)}, row_count=1
        )
        result = MultiResponseExpansionTransformer().apply(table, codebook)
        assert result.columns["Q8"][0] is None

    def test_unrecognized_indicator_value_raises(self) -> None:
        codebook = Codebook([_question()])
        table = RawTable(
            columns={"Q8_1": ("yes",), "Q8_2": ("0",), "Q8_3": ("0",)}, row_count=1
        )
        with pytest.raises(TransformationError, match="unrecognized value"):
            MultiResponseExpansionTransformer().apply(table, codebook)

    def test_partial_indicator_columns_not_expanded(self) -> None:
        # Only Q8_1 and Q8_2 present, Q8_3 missing - an inconsistent
        # source this transformer won't guess about; no Q8 column is
        # produced, and the partial columns are left as-is.
        codebook = Codebook([_question()])
        table = RawTable(columns={"Q8_1": ("1",), "Q8_2": ("0",)}, row_count=1)
        result = MultiResponseExpansionTransformer().apply(table, codebook)
        assert "Q8" not in result.columns
        assert result.columns["Q8_1"] == ("1",)

    def test_no_data_at_all_leaves_table_unchanged(self) -> None:
        codebook = Codebook([_question()])
        table = RawTable(columns={"OTHER": (1,)}, row_count=1)
        result = MultiResponseExpansionTransformer().apply(table, codebook)
        assert result is table


class TestMultipleQuestionsAndRows:
    def test_multiple_rows_expanded_independently(self) -> None:
        codebook = Codebook([_question()])
        table = RawTable(columns={"Q8": ("1", "2,3", None)}, row_count=3)
        result = MultiResponseExpansionTransformer().apply(table, codebook)
        assert result.columns["Q8"] == (frozenset({1}), frozenset({2, 3}), None)

    def test_non_multi_questions_ignored(self) -> None:
        from insightengine.core.codebook import NumericQuestion

        codebook = Codebook([NumericQuestion(id="AGE", label="Age")])
        table = RawTable(columns={"AGE": (25,)}, row_count=1)
        result = MultiResponseExpansionTransformer().apply(table, codebook)
        assert result is table
