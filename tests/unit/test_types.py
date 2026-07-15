"""Unit tests for insightengine.core.types."""

from __future__ import annotations

import pytest

from insightengine.core.types import DataType, QuestionType, Severity


class TestQuestionType:
    def test_values_are_lowercase_strings(self) -> None:
        for member in QuestionType:
            assert member.value == member.value.lower()

    def test_parses_from_raw_string_like_yaml_would_produce(self) -> None:
        assert QuestionType("single") is QuestionType.SINGLE
        assert QuestionType("grid") is QuestionType.GRID
        assert QuestionType("derived") is QuestionType.DERIVED

    def test_invalid_value_raises_value_error(self) -> None:
        with pytest.raises(ValueError):
            QuestionType("not_a_real_type")

    def test_all_expected_members_present(self) -> None:
        expected = {
            "single",
            "multi",
            "grid",
            "ranking",
            "numeric",
            "text",
            "derived",
        }
        assert {m.value for m in QuestionType} == expected


class TestDataType:
    def test_all_expected_members_present(self) -> None:
        expected = {"integer", "float", "categorical", "string", "boolean"}
        assert {m.value for m in DataType} == expected


class TestSeverity:
    def test_all_expected_members_present(self) -> None:
        assert {m.value for m in Severity} == {"info", "warning", "error"}

    def test_members_are_distinct(self) -> None:
        assert len({Severity.INFO, Severity.WARNING, Severity.ERROR}) == 3
