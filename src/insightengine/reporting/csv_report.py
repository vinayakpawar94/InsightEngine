"""CSV report generation.

Deliberately raw results only, no summary section — CSV's role here is
plain tabular data for downstream tools (spreadsheet import, further
analysis), not a human-readable report; the summary belongs in the
formats built to present it (JSON, HTML, Excel).
"""

from __future__ import annotations

import csv
from pathlib import Path

from insightengine.reporting.models import ReportData

_HEADER = ("rule_id", "severity", "message", "row_index", "variables")


class CSVReportGenerator:
    """Renders every result in a :class:`~insightengine.reporting.models.ReportData` as one CSV row."""

    def build(self, data: ReportData, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(_HEADER)
            for result in data.results:
                writer.writerow(
                    [
                        result.rule_id,
                        result.severity.value,
                        result.message,
                        result.row_index,
                        ";".join(result.variables),
                    ]
                )
        return path
