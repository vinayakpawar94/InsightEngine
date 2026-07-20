"""The Reporting Engine: turns validation results into files.

Every generator (:mod:`json_report`, :mod:`csv_report`,
:mod:`html_report`, :mod:`excel_report`) consumes the same
:class:`~insightengine.reporting.models.ReportData` — built once via
:func:`~insightengine.reporting.models.build_report_data` — so adding a
new output format never requires touching how results are counted or
summarized.
"""

from __future__ import annotations
