"""Unit tests for insightengine.metadata.base."""

from __future__ import annotations

from pathlib import Path

from insightengine.core.codebook import Codebook, NumericQuestion
from insightengine.metadata.base import MetadataParser


class _FakeParser:
    """A minimal MetadataParser implementation with no YAML/file dependency,
    used to prove the protocol is genuinely structural.
    """

    def parse(self, source: Path) -> Codebook:
        return Codebook([NumericQuestion(id="AGE", label="Age")])


def test_fake_parser_satisfies_protocol() -> None:
    assert isinstance(_FakeParser(), MetadataParser)


def test_fake_parser_produces_a_usable_codebook() -> None:
    codebook = _FakeParser().parse(Path("ignored.yaml"))
    assert "AGE" in codebook
