"""Unit tests for insightengine.validation.collector."""

from __future__ import annotations

from insightengine.core.types import Severity
from insightengine.validation.collector import ErrorCollector
from insightengine.validation.results import ValidationResult


def _result(rule_id: str, severity: Severity, row_index: int = 0) -> ValidationResult:
    return ValidationResult(rule_id=rule_id, severity=severity, message="x", row_index=row_index)


class TestErrorCollector:
    def test_starts_empty(self) -> None:
        collector = ErrorCollector()
        assert len(collector) == 0
        assert collector.results == ()
        assert collector.has_errors() is False

    def test_add(self) -> None:
        collector = ErrorCollector()
        collector.add(_result("r1", Severity.ERROR))
        assert len(collector) == 1
        assert collector.results[0].rule_id == "r1"

    def test_extend(self) -> None:
        collector = ErrorCollector()
        collector.extend([_result("r1", Severity.ERROR), _result("r2", Severity.WARNING)])
        assert len(collector) == 2

    def test_by_severity(self) -> None:
        collector = ErrorCollector()
        collector.extend(
            [
                _result("r1", Severity.ERROR),
                _result("r2", Severity.WARNING),
                _result("r3", Severity.ERROR),
            ]
        )
        errors = collector.by_severity(Severity.ERROR)
        assert len(errors) == 2
        assert {r.rule_id for r in errors} == {"r1", "r3"}

    def test_by_rule(self) -> None:
        collector = ErrorCollector()
        collector.extend(
            [
                _result("r1", Severity.ERROR, row_index=0),
                _result("r1", Severity.ERROR, row_index=1),
                _result("r2", Severity.ERROR, row_index=0),
            ]
        )
        r1_results = collector.by_rule("r1")
        assert len(r1_results) == 2
        assert all(r.rule_id == "r1" for r in r1_results)

    def test_has_errors_true_only_for_error_severity(self) -> None:
        collector = ErrorCollector()
        collector.add(_result("r1", Severity.WARNING))
        assert collector.has_errors() is False
        collector.add(_result("r2", Severity.ERROR))
        assert collector.has_errors() is True

    def test_iteration(self) -> None:
        collector = ErrorCollector()
        collector.extend([_result("r1", Severity.ERROR), _result("r2", Severity.ERROR)])
        assert [r.rule_id for r in collector] == ["r1", "r2"]
