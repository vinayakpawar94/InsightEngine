"""Unit tests for insightengine.cleaning.grid_expansion."""

from __future__ import annotations

from insightengine.cleaning.grid_expansion import GridColumnCompletionTransformer
from insightengine.core.codebook import Category, Codebook, GridQuestion, SingleQuestion
from insightengine.data.base import RawTable


def _grid() -> GridQuestion:
    row1 = SingleQuestion(id="Q2_1", label="Price", categories=(Category(code=1, label="A"),))
    row2 = SingleQuestion(id="Q2_2", label="Quality", categories=(Category(code=1, label="A"),))
    return GridQuestion(
        id="Q2", label="Grid", rows=(row1, row2), columns=(Category(code=1, label="A"),)
    )


class TestGridColumnCompletion:
    def test_adds_missing_row_columns_as_all_none(self) -> None:
        codebook = Codebook([_grid()])
        table = RawTable(columns={}, row_count=3)
        result = GridColumnCompletionTransformer().apply(table, codebook)
        assert result.columns["Q2_1"] == (None, None, None)
        assert result.columns["Q2_2"] == (None, None, None)

    def test_existing_row_column_left_untouched(self) -> None:
        codebook = Codebook([_grid()])
        table = RawTable(columns={"Q2_1": (1, 1, 1)}, row_count=3)
        result = GridColumnCompletionTransformer().apply(table, codebook)
        assert result.columns["Q2_1"] == (1, 1, 1)
        assert result.columns["Q2_2"] == (None, None, None)

    def test_no_change_returns_the_same_table_object(self) -> None:
        codebook = Codebook([_grid()])
        table = RawTable(columns={"Q2_1": (1,), "Q2_2": (1,)}, row_count=1)
        result = GridColumnCompletionTransformer().apply(table, codebook)
        assert result is table

    def test_non_grid_questions_ignored(self) -> None:
        from insightengine.core.codebook import NumericQuestion

        codebook = Codebook([NumericQuestion(id="AGE", label="Age")])
        table = RawTable(columns={"AGE": (25,)}, row_count=1)
        result = GridColumnCompletionTransformer().apply(table, codebook)
        assert result is table

    def test_empty_codebook_no_change(self) -> None:
        codebook = Codebook([])
        table = RawTable(columns={"X": (1,)}, row_count=1)
        result = GridColumnCompletionTransformer().apply(table, codebook)
        assert result is table
