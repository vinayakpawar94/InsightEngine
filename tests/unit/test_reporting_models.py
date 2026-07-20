"""Unit tests for insightengine.reporting.models."""

from __future__ import annotations

import pytest

from insightengine.core.exceptions import InconsistentRuleSeverityError
from insightengine.core.types import Severity
from insightengine.reporting.models import build_report_data
from insightengine.validation.results import ValidationResult


def _result(rule_id: str, severity: Severity, row_index: int = 0) -> ValidationResult:
    return ValidationResult(rule_id=rule_id, severity=severity, message="x", row_index=row_index)


class TestBuildReportData:
    def test_empty_results(self) -> None:
        data = build_report_data([])
        assert data.results == ()
        assert data.by_rule == ()
        assert all(count == 0 for count in data.counts_by_severity.values())

    def test_generated_at_is_set(self) -> None:
        data = build_report_data([])
        assert data.generated_at  # non-empty

    def test_by_rule_grouping_and_counts(self) -> None:
        data = build_report_data(
            [
                _result("r1", Severity.ERROR, row_index=0),
                _result("r1", Severity.ERROR, row_index=1),
                _result("r2", Severity.WARNING, row_index=0),
            ]
        )
        by_rule = {rs.rule_id: rs for rs in data.by_rule}
        assert by_rule["r1"].count == 2
        assert by_rule["r1"].severity is Severity.ERROR
        assert by_rule["r2"].count == 1
        assert by_rule["r2"].severity is Severity.WARNING

    def test_by_rule_sorted_by_rule_id(self) -> None:
        data = build_report_data(
            [_result("zebra", Severity.ERROR), _result("apple", Severity.ERROR)]
        )
        assert [rs.rule_id for rs in data.by_rule] == ["apple", "zebra"]

    def test_counts_by_severity(self) -> None:
        data = build_report_data(
            [
                _result("r1", Severity.ERROR),
                _result("r2", Severity.ERROR),
                _result("r3", Severity.WARNING),
                _result("r4", Severity.INFO),
            ]
        )
        assert data.counts_by_severity[Severity.ERROR] == 2
        assert data.counts_by_severity[Severity.WARNING] == 1
        assert data.counts_by_severity[Severity.INFO] == 1

    def test_all_severities_present_even_with_zero_count(self) -> None:
        data = build_report_data([_result("r1", Severity.ERROR)])
        assert data.counts_by_severity[Severity.WARNING] == 0
        assert data.counts_by_severity[Severity.INFO] == 0

    def test_inconsistent_severity_for_same_rule_id_raises(self) -> None:
        with pytest.raises(InconsistentRuleSeverityError, match="'r1'"):
            build_report_data(
                [_result("r1", Severity.ERROR), _result("r1", Severity.WARNING)]
            )

    def test_total_count_matches_input_length(self) -> None:
        results = [_result("r1", Severity.ERROR, row_index=i) for i in range(5)]
        data = build_report_data(results)
        assert len(data.results) == 5
