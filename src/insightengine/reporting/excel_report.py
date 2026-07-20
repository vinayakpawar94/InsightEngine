"""Excel report generation.

Two sheets — "Summary" and "Details" — rather than one sheet with a
summary section followed by a details section at a computed row offset.
Two sheets is both cleaner Excel practice and avoids any fragility in
knowing where one section ends and the next begins.
"""

from __future__ import annotations

from pathlib import Path

import openpyxl

from insightengine.reporting.models import ReportData

_SUMMARY_HEADER = ("Rule", "Severity", "Count")
_DETAILS_HEADER = ("Rule", "Severity", "Message", "Row", "Variables")


class ExcelReportGenerator:
    """Renders a :class:`~insightengine.reporting.models.ReportData` as
    an ``.xlsx`` workbook with a Summary sheet and a Details sheet.
    """

    def build(self, data: ReportData, path: Path) -> Path:
        workbook = openpyxl.Workbook()

        summary_sheet = workbook.active
        assert summary_sheet is not None  # a freshly-created Workbook always has an active sheet
        summary_sheet.title = "Summary"
        summary_sheet.append(["Generated at", data.generated_at])
        summary_sheet.append(["Total findings", len(data.results)])
        summary_sheet.append([])
        summary_sheet.append(list(_SUMMARY_HEADER))
        for rs in data.by_rule:
            summary_sheet.append([rs.rule_id, rs.severity.value, rs.count])

        details_sheet = workbook.create_sheet("Details")
        details_sheet.append(list(_DETAILS_HEADER))
        for r in data.results:
            details_sheet.append(
                [r.rule_id, r.severity.value, r.message, r.row_index, ", ".join(r.variables)]
            )

        path.parent.mkdir(parents=True, exist_ok=True)
        workbook.save(str(path))
        return path
