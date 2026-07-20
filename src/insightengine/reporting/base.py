"""The structural contract every report generator implements."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from insightengine.reporting.models import ReportData


@runtime_checkable
class ReportGenerator(Protocol):
    """Something that can render a :class:`~insightengine.reporting.models.ReportData` to a file."""

    def build(self, data: ReportData, path: Path) -> Path:
        """Write a report to ``path`` and return the path written.

        Creates ``path``'s parent directories if needed.
        """
        ...
