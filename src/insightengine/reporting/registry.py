"""The plugin registry for :class:`~insightengine.reporting.base.ReportGenerator`
implementations.

A new sibling file, not an edit to any of the four frozen generator
modules — this registry imports their existing classes without
modifying them.
"""

from __future__ import annotations

from insightengine.plugins.registry import PluginRegistry
from insightengine.reporting.base import ReportGenerator
from insightengine.reporting.csv_report import CSVReportGenerator
from insightengine.reporting.excel_report import ExcelReportGenerator
from insightengine.reporting.html_report import HTMLReportGenerator
from insightengine.reporting.json_report import JSONReportGenerator

GROUP = "insightengine.report_generators"

report_generator_registry: PluginRegistry[ReportGenerator] = PluginRegistry(group=GROUP)
report_generator_registry.register("json", JSONReportGenerator())
report_generator_registry.register("csv", CSVReportGenerator())
report_generator_registry.register("html", HTMLReportGenerator())
report_generator_registry.register("excel", ExcelReportGenerator())
