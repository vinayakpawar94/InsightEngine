"""Shared enumerations used across the insightengine framework.

These enums are intentionally the only "vocabulary" shared between the
Metadata Engine, Rule Engine, and Reporting Engine. Keeping them in one
place (rather than letting each subsystem define its own overlapping
notion of, say, "severity") is what lets those subsystems stay decoupled
from one another while still agreeing on shared concepts.
"""

from __future__ import annotations

from enum import StrEnum, unique


@unique
class QuestionType(StrEnum):
    """The kind of question a :class:`~insightengine.metadata.Question` represents.

    Values are lowercase strings deliberately, so a native YAML codebook can
    write ``type: single`` and have it parse directly into this enum without
    a separate string-to-enum mapping table.
    """

    SINGLE = "single"
    """Single-response categorical question (pick one)."""

    MULTI = "multi"
    """Multiple-response categorical question (pick many)."""

    GRID = "grid"
    """A grid/matrix question: a set of row sub-questions sharing one column scale."""

    RANKING = "ranking"
    """A ranking question: respondent orders a set of items."""

    NUMERIC = "numeric"
    """A free-entry numeric question, optionally bounded."""

    TEXT = "text"
    """A free-entry text (open-end) question."""

    DERIVED = "derived"
    """A variable computed from other variables rather than collected directly."""


@unique
class DataType(StrEnum):
    """The underlying storage/comparison type of a variable's values.

    Distinct from :class:`QuestionType`: a ``NUMERIC`` question and a
    ``DERIVED`` variable can both ultimately hold ``DataType.FLOAT`` values.
    ``QuestionType`` describes how data was collected; ``DataType`` describes
    how it is stored and compared.
    """

    INTEGER = "integer"
    FLOAT = "float"
    CATEGORICAL = "categorical"
    STRING = "string"
    BOOLEAN = "boolean"


@unique
class Severity(StrEnum):
    """Severity of a validation finding, used by the (future) Rule Engine
    and Reporting Engine to classify a :class:`ValidationResult`.

    Ordered loosely by ascending urgency: ``INFO`` < ``WARNING`` < ``ERROR``.
    Deliberately does not include a "fatal"/"critical" tier — per the
    project's rule-migration analysis, findings that would warrant halting
    a run entirely are represented as exceptions (see
    :mod:`insightengine.core.exceptions`), not as a validation severity level.
    """

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
