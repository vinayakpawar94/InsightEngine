"""The backend-agnostic contract every metadata parser implements.

Mirrors the pattern established in :mod:`insightengine.data.base`: a
structural ``Protocol``, not an ``ABC``, so a future parser (or a test
fake) needs only to match the shape.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from insightengine.core.codebook import Codebook


@runtime_checkable
class MetadataParser(Protocol):
    """Something that can turn a metadata source file into a :class:`~insightengine.core.codebook.Codebook`."""

    def parse(self, source: Path) -> Codebook:
        """Parse ``source`` into a validated :class:`Codebook`.

        Raises:
            MetadataParseError: If the source is structurally invalid.
            (Any exception :class:`~insightengine.core.codebook.Codebook`
            itself can raise — ``DuplicateQuestionIdError``,
            ``UnknownVariableError``, ``CircularDependencyError`` — also
            propagates, since a parser builds a real ``Codebook`` and
            doesn't re-validate what it already enforces.)
        """
        ...
