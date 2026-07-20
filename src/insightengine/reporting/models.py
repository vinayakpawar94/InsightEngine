"""The shared result model every report generator consumes.

Built once, via :func:`build_report_data`, from the same
:class:`~insightengine.validation.results.ValidationResult` tuple every
format renders — this is what guarantees the phase's acceptance
criterion (consistent counts across all four formats) by construction:
there is exactly one place totals and per-rule/per-severity breakdowns
get computed, not four.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from insightengine.core.exceptions import InconsistentRuleSeverityError
from insightengine.core.types import Severity
from insightengine.validation.results import ValidationResult


@dataclass(frozen=True, slots=True)
class RuleSummary:
    """How many findings a single rule (or synthetic domain-check id)
    produced in one validation run, and at what severity.
    """

    rule_id: str
    severity: Severity
    count: int


@dataclass(frozen=True, slots=True)
class ReportData:
    """Everything a report generator needs: the raw results plus
    pre-computed summaries, so no generator needs to recompute counts
    itself.
    """

    results: tuple[ValidationResult, ...]
    generated_at: str
    by_rule: tuple[RuleSummary, ...]
    counts_by_severity: Mapping[Severity, int]


def build_report_data(results: Sequence[ValidationResult]) -> ReportData:
    """Build a :class:`ReportData` from a sequence of validation results.

    Raises:
        InconsistentRuleSeverityError: If two results share a ``rule_id``
            but disagree on severity — see that exception's docstring for
            why this is treated as a hard error rather than resolved
            silently.
    """
    results = tuple(results)

    grouped: dict[str, list[ValidationResult]] = {}
    for result in results:
        grouped.setdefault(result.rule_id, []).append(result)

    by_rule: list[RuleSummary] = []
    for rule_id, items in grouped.items():
        severities = {item.severity for item in items}
        if len(severities) > 1:
            raise InconsistentRuleSeverityError(
                f"Rule {rule_id!r} has results with multiple severities: "
                f"{sorted(s.value for s in severities)}."
            )
        by_rule.append(RuleSummary(rule_id=rule_id, severity=items[0].severity, count=len(items)))
    by_rule.sort(key=lambda summary: summary.rule_id)

    counts_by_severity: dict[Severity, int] = {
        severity: sum(1 for r in results if r.severity is severity) for severity in Severity
    }

    return ReportData(
        results=results,
        generated_at=datetime.now(UTC).isoformat(),
        by_rule=tuple(by_rule),
        counts_by_severity=counts_by_severity,
    )
