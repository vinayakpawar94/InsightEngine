"""JSON report generation."""

from __future__ import annotations

import json
from pathlib import Path

from insightengine.reporting.models import ReportData


class JSONReportGenerator:
    """Renders a :class:`~insightengine.reporting.models.ReportData` as
    a single JSON document with ``summary`` and ``results`` sections.
    """

    def build(self, data: ReportData, path: Path) -> Path:
        payload = {
            "generated_at": data.generated_at,
            "summary": {
                "total": len(data.results),
                "by_severity": {
                    severity.value: count for severity, count in data.counts_by_severity.items()
                },
                "by_rule": [
                    {"rule_id": rs.rule_id, "severity": rs.severity.value, "count": rs.count}
                    for rs in data.by_rule
                ],
            },
            "results": [
                {
                    "rule_id": r.rule_id,
                    "severity": r.severity.value,
                    "message": r.message,
                    "row_index": r.row_index,
                    "variables": list(r.variables),
                }
                for r in data.results
            ],
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return path
