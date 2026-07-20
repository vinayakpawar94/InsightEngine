"""Unit tests for insightengine.reporting.csv_report."""

from __future__ import annotations

import csv
from pathlib import Path

from insightengine.core.types import Severity
from insightengine.reporting.csv_report import CSVReportGenerator
from insightengine.reporting.models import build_report_data
from insightengine.validation.results import ValidationResult


class TestCSVReportGenerator:
    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        data = build_report_data([])
        path = tmp_path / "nested" / "report.csv"
        CSVReportGenerator().build(data, path)
        assert path.is_file()

    def test_header_row(self, tmp_path: Path) -> None:
        path = tmp_path / "report.csv"
        CSVReportGenerator().build(build_report_data([]), path)
        with path.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.reader(handle))
        assert rows[0] == ["rule_id", "severity", "message", "row_index", "variables"]

    def test_row_count_matches_results(self, tmp_path: Path) -> None:
        results = [
            ValidationResult(rule_id="r1", severity=Severity.ERROR, message="x", row_index=i)
            for i in range(3)
        ]
        data = build_report_data(results)
        path = tmp_path / "report.csv"
        CSVReportGenerator().build(data, path)
        with path.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.reader(handle))
        assert len(rows) - 1 == 3  # minus header

    def test_variables_joined_with_semicolon(self, tmp_path: Path) -> None:
        results = [
            ValidationResult(
                rule_id="r1",
                severity=Severity.ERROR,
                message="x",
                row_index=0,
                variables=("Q1", "Q2"),
            )
        ]
        data = build_report_data(results)
        path = tmp_path / "report.csv"
        CSVReportGenerator().build(data, path)
        with path.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.reader(handle))
        assert rows[1][4] == "Q1;Q2"

    def test_message_containing_comma_is_quoted_correctly(self, tmp_path: Path) -> None:
        results = [
            ValidationResult(
                rule_id="r1", severity=Severity.ERROR, message="bad, value", row_index=0
            )
        ]
        data = build_report_data(results)
        path = tmp_path / "report.csv"
        CSVReportGenerator().build(data, path)
        with path.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.reader(handle))
        assert rows[1][2] == "bad, value"
