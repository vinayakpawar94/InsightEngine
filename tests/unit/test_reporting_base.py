"""Unit tests for insightengine.reporting.base."""

from __future__ import annotations

from pathlib import Path

from insightengine.reporting.base import ReportGenerator
from insightengine.reporting.models import ReportData


class _FakeGenerator:
    """Proves the protocol is genuinely structural - no inheritance needed."""

    def build(self, data: ReportData, path: Path) -> Path:
        path.write_text("fake report", encoding="utf-8")
        return path


def test_fake_generator_satisfies_protocol() -> None:
    assert isinstance(_FakeGenerator(), ReportGenerator)
