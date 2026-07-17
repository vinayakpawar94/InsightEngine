"""Unit tests for insightengine.validation.results."""

from __future__ import annotations

import pytest

from insightengine.core.types import Severity
from insightengine.validation.results import ValidationResult


class TestValidationResult:
    def test_construction(self) -> None:
        result = ValidationResult(
            rule_id="r1", severity=Severity.ERROR, message="bad", row_index=3
        )
        assert result.rule_id == "r1"
        assert result.severity is Severity.ERROR
        assert result.row_index == 3
        assert result.variables == ()

    def test_variables_default_empty(self) -> None:
        result = ValidationResult(rule_id="r1", severity=Severity.WARNING, message="x", row_index=0)
        assert result.variables == ()

    def test_variables_explicit(self) -> None:
        result = ValidationResult(
            rule_id="r1", severity=Severity.ERROR, message="x", row_index=0, variables=("Q1", "Q2")
        )
        assert result.variables == ("Q1", "Q2")

    def test_is_frozen(self) -> None:
        result = ValidationResult(rule_id="r1", severity=Severity.ERROR, message="x", row_index=0)
        with pytest.raises(Exception):
            result.row_index = 5  # type: ignore[misc]
