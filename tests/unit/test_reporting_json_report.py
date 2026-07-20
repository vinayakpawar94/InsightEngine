"""Unit tests for insightengine.reporting.json_report."""

from __future__ import annotations

import json
from pathlib import Path

from insightengine.core.types import Severity
from insightengine.reporting.json_report import JSONReportGenerator
from insightengine.reporting.models import build_report_data
from insightengine.validation.results import ValidationResult


class TestJSONReportGenerator:
    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        data = build_report_data([])
        path = tmp_path / "nested" / "report.json"
        JSONReportGenerator().build(data, path)
        assert path.is_file()

    def test_returns_the_path(self, tmp_path: Path) -> None:
        path = tmp_path / "report.json"
        result_path = JSONReportGenerator().build(build_report_data([]), path)
        assert result_path == path

    def test_summary_totals(self, tmp_path: Path) -> None:
        results = [
            ValidationResult(rule_id="r1", severity=Severity.ERROR, message="x", row_index=0),
            ValidationResult(rule_id="r1", severity=Severity.ERROR, message="x", row_index=1),
            ValidationResult(rule_id="r2", severity=Severity.WARNING, message="y", row_index=0),
        ]
        data = build_report_data(results)
        path = tmp_path / "report.json"
        JSONReportGenerator().build(data, path)

        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload["summary"]["total"] == 3
        assert payload["summary"]["by_severity"]["error"] == 2
        assert payload["summary"]["by_severity"]["warning"] == 1
        assert len(payload["results"]) == 3

    def test_result_fields_present(self, tmp_path: Path) -> None:
        results = [
            ValidationResult(
                rule_id="r1",
                severity=Severity.ERROR,
                message="bad value",
                row_index=3,
                variables=("Q1", "Q2"),
            )
        ]
        data = build_report_data(results)
        path = tmp_path / "report.json"
        JSONReportGenerator().build(data, path)

        payload = json.loads(path.read_text(encoding="utf-8"))
        entry = payload["results"][0]
        assert entry == {
            "rule_id": "r1",
            "severity": "error",
            "message": "bad value",
            "row_index": 3,
            "variables": ["Q1", "Q2"],
        }
