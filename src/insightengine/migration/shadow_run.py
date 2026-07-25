"""Comparing new-pipeline validation results against parsed legacy QA output.

**Scoped to aggregate comparison only, not case-level reconciliation —
and this is a real limitation, not an arbitrary simplification.** A
:class:`~insightengine.validation.results.ValidationResult` is keyed by
physical ``row_index`` (Phase 6's own documented choice — it has no
concept of a respondent/case identifier). A legacy
:class:`~insightengine.migration.legacy_log.LegacyErrorLogEntry` is
keyed by an error-type string, and
:class:`~insightengine.migration.legacy_log.LegacyCaseNote` is keyed by
respondent serial number. There is no shared identifier between the two
sides to match individual findings case-by-case — building one would
mean either persisting a serial-number column through the entire new
pipeline (not currently done anywhere) or accepting a lossy row-index
correspondence. Neither is implemented here; this module only compares
**totals and key/rule-id overlap**, which is honest about what it can
actually tell you: whether the same broad categories of problems were
found, and how their counts compare — not whether the same individual
respondents were flagged by both systems.
"""

from __future__ import annotations

from dataclasses import dataclass

from insightengine.migration.legacy_log import LegacyErrorLog
from insightengine.validation.results import ValidationResult


@dataclass(frozen=True, slots=True)
class DivergenceReport:
    """An aggregate-level comparison between legacy and new-pipeline results."""

    legacy_total: int
    new_total: int
    legacy_only_keys: tuple[str, ...]
    new_only_rule_ids: tuple[str, ...]
    common_keys: tuple[str, ...]

    @property
    def totals_match(self) -> bool:
        return self.legacy_total == self.new_total

    @property
    def has_unmatched_keys(self) -> bool:
        return bool(self.legacy_only_keys or self.new_only_rule_ids)


def compare_legacy_and_new(
    legacy: LegacyErrorLog, new_results: tuple[ValidationResult, ...]
) -> DivergenceReport:
    """Build a :class:`DivergenceReport` comparing ``legacy``'s parsed
    entries against ``new_results``.

    Key/rule-id matching is by exact string equality — a legacy key like
    ``"respid is invalid"`` will only be recognized as matching a new
    rule id if the new rule was actually named that way. Renaming rules
    during migration (a likely, reasonable thing to do) will show up
    here as unmatched keys on both sides even when the underlying check
    is equivalent; that's a limitation of exact-string matching, not a
    sign the migration is wrong — read the unmatched lists as "worth a
    human look," not "definitely broken."
    """
    legacy_keys = {entry.key for entry in legacy.entries}
    new_rule_ids = {result.rule_id for result in new_results}

    return DivergenceReport(
        legacy_total=sum(entry.count for entry in legacy.entries),
        new_total=len(new_results),
        legacy_only_keys=tuple(sorted(legacy_keys - new_rule_ids)),
        new_only_rule_ids=tuple(sorted(new_rule_ids - legacy_keys)),
        common_keys=tuple(sorted(legacy_keys & new_rule_ids)),
    )
