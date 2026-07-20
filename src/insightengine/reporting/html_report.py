"""HTML report generation.

Self-contained (inline CSS, no external assets) so the output can be
emailed as an attachment or opened directly with no dependencies.
Generated with plain string formatting rather than a templating engine
(Jinja2) — at this scope (one summary table, one details table) a
templating dependency isn't justified; see the reporting package's
design notes. Every piece of data-derived text is passed through
``html.escape`` — a validation message or variable name is data, not
trusted markup, and must never be interpolated raw.
"""

from __future__ import annotations

import html
from pathlib import Path

from insightengine.reporting.models import ReportData, RuleSummary
from insightengine.validation.results import ValidationResult

_STYLE = """
body { font-family: -apple-system, Segoe UI, Helvetica, Arial, sans-serif; margin: 2rem; color: #1a1a1a; }
h1 { font-size: 1.4rem; }
h2 { font-size: 1.1rem; margin-top: 2rem; }
table { border-collapse: collapse; width: 100%; margin-top: 0.5rem; }
th, td { border: 1px solid #ddd; padding: 0.4rem 0.6rem; text-align: left; font-size: 0.9rem; }
th { background: #f4f4f4; }
.severity-error { color: #b00020; font-weight: 600; }
.severity-warning { color: #9a6700; font-weight: 600; }
.severity-info { color: #555; }
"""

_SEVERITY_CLASS = {
    "error": "severity-error",
    "warning": "severity-warning",
    "info": "severity-info",
}


class HTMLReportGenerator:
    """Renders a :class:`~insightengine.reporting.models.ReportData` as
    a single, self-contained HTML page.
    """

    def build(self, data: ReportData, path: Path) -> Path:
        content = (
            "<!DOCTYPE html>\n"
            "<html><head><meta charset=\"utf-8\">"
            "<title>Validation Report</title>"
            f"<style>{_STYLE}</style></head><body>"
            "<h1>Validation Report</h1>"
            f"<p>Generated at {html.escape(data.generated_at)}</p>"
            f"<p>Total findings: {len(data.results)}</p>"
            "<h2>Summary by rule</h2>"
            "<table><thead><tr><th>Rule</th><th>Severity</th><th>Count</th></tr></thead>"
            f"<tbody>{self._render_summary_rows(data.by_rule)}</tbody></table>"
            "<h2>Details</h2>"
            "<table><thead><tr><th>Rule</th><th>Severity</th><th>Message</th>"
            "<th>Row</th><th>Variables</th></tr></thead>"
            f"<tbody>{self._render_result_rows(data.results)}</tbody></table>"
            "</body></html>"
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def _render_summary_rows(self, summaries: tuple[RuleSummary, ...]) -> str:
        return "\n".join(
            f'<tr class="summary-row">'
            f"<td>{html.escape(rs.rule_id)}</td>"
            f'<td class="{_SEVERITY_CLASS[rs.severity.value]}">{html.escape(rs.severity.value)}</td>'
            f"<td>{rs.count}</td>"
            f"</tr>"
            for rs in summaries
        )

    def _render_result_rows(self, results: tuple[ValidationResult, ...]) -> str:
        return "\n".join(
            f'<tr class="result-row">'
            f"<td>{html.escape(r.rule_id)}</td>"
            f'<td class="{_SEVERITY_CLASS[r.severity.value]}">{html.escape(r.severity.value)}</td>'
            f"<td>{html.escape(r.message)}</td>"
            f"<td>{r.row_index}</td>"
            f"<td>{html.escape(', '.join(r.variables))}</td>"
            f"</tr>"
            for r in results
        )
