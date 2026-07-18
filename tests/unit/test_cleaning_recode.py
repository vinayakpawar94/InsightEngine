"""Unit tests for insightengine.cleaning.recode."""

from __future__ import annotations

import pytest

from insightengine.cleaning.recode import RecodeMap, RecodeTransformer
from insightengine.core.codebook import Codebook
from insightengine.core.exceptions import TransformationError, UnknownVariableError
from insightengine.data.base import RawTable


class TestRecodeMap:
    def test_empty_variable_raises(self) -> None:
        with pytest.raises(TransformationError, match="cannot be empty"):
            RecodeMap(variable="  ", mapping={1: 2})


class TestRecodeTransformer:
    def test_basic_recode(self) -> None:
        codebook = Codebook([])
        table = RawTable(columns={"Q1": (1, 2, 3)}, row_count=3)
        recode = RecodeMap(variable="Q1", mapping={1: 99})
        result = RecodeTransformer([recode]).apply(table, codebook)
        assert result.columns["Q1"] == (99, 2, 3)

    def test_unmapped_code_unchanged_when_no_default(self) -> None:
        codebook = Codebook([])
        table = RawTable(columns={"Q1": (5,)}, row_count=1)
        recode = RecodeMap(variable="Q1", mapping={1: 99})
        result = RecodeTransformer([recode]).apply(table, codebook)
        assert result.columns["Q1"] == (5,)

    def test_unmapped_code_uses_default_when_set(self) -> None:
        codebook = Codebook([])
        table = RawTable(columns={"Q1": (5,)}, row_count=1)
        recode = RecodeMap(variable="Q1", mapping={1: 99}, default=0)
        result = RecodeTransformer([recode]).apply(table, codebook)
        assert result.columns["Q1"] == (0,)

    def test_none_value_stays_none(self) -> None:
        codebook = Codebook([])
        table = RawTable(columns={"Q1": (None,)}, row_count=1)
        recode = RecodeMap(variable="Q1", mapping={1: 99}, default=0)
        result = RecodeTransformer([recode]).apply(table, codebook)
        assert result.columns["Q1"] == (None,)

    def test_whole_number_float_coerced_before_recoding(self) -> None:
        # The same pandas float-upcast reality Phase 6 had to handle.
        codebook = Codebook([])
        table = RawTable(columns={"Q1": (1.0,)}, row_count=1)
        recode = RecodeMap(variable="Q1", mapping={1: 99})
        result = RecodeTransformer([recode]).apply(table, codebook)
        assert result.columns["Q1"] == (99,)

    def test_unknown_variable_raises(self) -> None:
        codebook = Codebook([])
        table = RawTable(columns={"Q1": (1,)}, row_count=1)
        recode = RecodeMap(variable="DOES_NOT_EXIST", mapping={1: 99})
        with pytest.raises(UnknownVariableError):
            RecodeTransformer([recode]).apply(table, codebook)

    def test_non_integer_like_value_raises(self) -> None:
        codebook = Codebook([])
        table = RawTable(columns={"Q1": ("not a number",)}, row_count=1)
        recode = RecodeMap(variable="Q1", mapping={1: 99})
        with pytest.raises(TransformationError, match="non-integer-like value"):
            RecodeTransformer([recode]).apply(table, codebook)

    def test_multiple_recodes_applied_independently(self) -> None:
        codebook = Codebook([])
        table = RawTable(columns={"Q1": (1,), "Q2": (5,)}, row_count=1)
        result = RecodeTransformer(
            [
                RecodeMap(variable="Q1", mapping={1: 100}),
                RecodeMap(variable="Q2", mapping={5: 500}),
            ]
        ).apply(table, codebook)
        assert result.columns["Q1"] == (100,)
        assert result.columns["Q2"] == (500,)

    def test_bool_value_rejected_as_non_integer_like(self) -> None:
        codebook = Codebook([])
        table = RawTable(columns={"Q1": (True,)}, row_count=1)
        recode = RecodeMap(variable="Q1", mapping={1: 99})
        with pytest.raises(TransformationError, match="non-integer-like value"):
            RecodeTransformer([recode]).apply(table, codebook)

    def test_empty_recode_list_returns_equivalent_table(self) -> None:
        codebook = Codebook([])
        table = RawTable(columns={"Q1": (1,)}, row_count=1)
        result = RecodeTransformer([]).apply(table, codebook)
        assert result.columns == table.columns
