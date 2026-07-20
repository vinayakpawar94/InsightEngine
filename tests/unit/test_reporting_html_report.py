"""Unit tests for insightengine.reporting.html_report."""

from __future__ import annotations

from pathlib import Path

from insightengine.core.types import Severity
from insightengine.reporting.html_report import HTMLReportGenerator
from insightengine.reporting.models import build_report_data
from insightengine.validation.results import ValidationResult


class TestHTMLReportGenerator:
    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        data = build_report_data([])
        path = tmp_path / "nested" / "report.html"
        HTMLReportGenerator().build(data, path)
        assert path.is_file()

    def test_output_is_valid_looking_html(self, tmp_path: Path) -> None:
        path = tmp_path / "report.html"
        HTMLReportGenerator().build(build_report_data([]), path)
        content = path.read_text(encoding="utf-8")
        assert content.startswith("<!DOCTYPE html>")
        assert "</html>" in content

    def test_result_row_count_matches_results(self, tmp_path: Path) -> None:
        results = [
            ValidationResult(rule_id="r1", severity=Severity.ERROR, message="x", row_index=i)
            for i in range(4)
        ]
        data = build_report_data(results)
        path = tmp_path / "report.html"
        HTMLReportGenerator().build(data, path)
        content = path.read_text(encoding="utf-8")
        assert content.count('class="result-row"') == 4

    def test_message_is_html_escaped(self, tmp_path: Path) -> None:
        results = [
            ValidationResult(
                rule_id="r1",
                severity=Severity.ERROR,
                message="<script>alert('xss')</script>",
                row_index=0,
            )
        ]
        data = build_report_data(results)
        path = tmp_path / "report.html"
        HTMLReportGenerator().build(data, path)
        content = path.read_text(encoding="utf-8")
        assert "<script>alert" not in content
        assert "&lt;script&gt;" in content

    def test_variables_are_html_escaped(self, tmp_path: Path) -> None:
        results = [
            ValidationResult(
                rule_id="r1",
                severity=Severity.ERROR,
                message="x",
                row_index=0,
                variables=("<b>Q1</b>",),
            )
        ]
        data = build_report_data(results)
        path = tmp_path / "report.html"
        HTMLReportGenerator().build(data, path)
        content = path.read_text(encoding="utf-8")
        assert "<b>Q1</b>" not in content
        assert "&lt;b&gt;Q1&lt;/b&gt;" in content

    def test_rule_id_is_html_escaped(self, tmp_path: Path) -> None:
        results = [
            ValidationResult(
                rule_id="<img src=x>", severity=Severity.ERROR, message="x", row_index=0
            )
        ]
        data = build_report_data(results)
        path = tmp_path / "report.html"
        HTMLReportGenerator().build(data, path)
        content = path.read_text(encoding="utf-8")
        assert "<img src=x>" not in content

    def test_summary_row_count_matches_by_rule(self, tmp_path: Path) -> None:
        results = [
            ValidationResult(rule_id="r1", severity=Severity.ERROR, message="x", row_index=0),
            ValidationResult(rule_id="r2", severity=Severity.WARNING, message="y", row_index=0),
        ]
        data = build_report_data(results)
        path = tmp_path / "report.html"
        HTMLReportGenerator().build(data, path)
        content = path.read_text(encoding="utf-8")
        assert content.count('class="summary-row"') == 2

    def test_total_findings_displayed(self, tmp_path: Path) -> None:
        results = [
            ValidationResult(rule_id="r1", severity=Severity.ERROR, message="x", row_index=i)
            for i in range(7)
        ]
        data = build_report_data(results)
        path = tmp_path / "report.html"
        HTMLReportGenerator().build(data, path)
        content = path.read_text(encoding="utf-8")
        assert "Total findings: 7" in content
