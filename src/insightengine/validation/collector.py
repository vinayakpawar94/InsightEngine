"""Accumulates :class:`~insightengine.validation.results.ValidationResult`
objects produced during a validation run and offers basic grouping.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator

from insightengine.core.types import Severity
from insightengine.validation.results import ValidationResult


class ErrorCollector:
    """A mutable accumulator of validation results.

    Not thread-safe and not meant to be — one collector per validation
    run, used synchronously.
    """

    def __init__(self) -> None:
        self._results: list[ValidationResult] = []

    def add(self, result: ValidationResult) -> None:
        """Record a single result."""
        self._results.append(result)

    def extend(self, results: Iterable[ValidationResult]) -> None:
        """Record every result in ``results``, in order."""
        self._results.extend(results)

    @property
    def results(self) -> tuple[ValidationResult, ...]:
        """Every result recorded so far, in the order it was added."""
        return tuple(self._results)

    def by_severity(self, severity: Severity) -> tuple[ValidationResult, ...]:
        """Every result with exactly this severity."""
        return tuple(r for r in self._results if r.severity is severity)

    def by_rule(self, rule_id: str) -> tuple[ValidationResult, ...]:
        """Every result produced by the rule (or synthetic domain-check
        id) named ``rule_id``.
        """
        return tuple(r for r in self._results if r.rule_id == rule_id)

    def has_errors(self) -> bool:
        """Whether any recorded result has :class:`Severity.ERROR`."""
        return any(r.severity is Severity.ERROR for r in self._results)

    def __len__(self) -> int:
        return len(self._results)

    def __iter__(self) -> Iterator[ValidationResult]:
        return iter(self._results)
