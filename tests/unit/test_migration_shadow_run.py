"""Unit tests for insightengine.migration.shadow_run."""

from __future__ import annotations

from insightengine.core.types import Severity
from insightengine.migration.legacy_log import LegacyErrorLog, LegacyErrorLogEntry
from insightengine.migration.shadow_run import compare_legacy_and_new
from insightengine.validation.results import ValidationResult


def _legacy(*entries: tuple[str, int]) -> LegacyErrorLog:
    return LegacyErrorLog(
        job_number="CP4210",
        entries=tuple(LegacyErrorLogEntry(key=k, count=c) for k, c in entries),
        total_completes=None,
        total_rejects=None,
    )


def _result(rule_id: str, row_index: int = 0) -> ValidationResult:
    return ValidationResult(rule_id=rule_id, severity=Severity.ERROR, message="x", row_index=row_index)


class TestCompareLegacyAndNew:
    def test_matching_keys_and_totals(self) -> None:
        legacy = _legacy(("respid is invalid", 2))
        new_results = (_result("respid is invalid", 0), _result("respid is invalid", 1))
        report = compare_legacy_and_new(legacy, new_results)

        assert report.legacy_total == 2
        assert report.new_total == 2
        assert report.totals_match is True
        assert report.common_keys == ("respid is invalid",)
        assert report.legacy_only_keys == ()
        assert report.new_only_rule_ids == ()
        assert report.has_unmatched_keys is False

    def test_legacy_only_key(self) -> None:
        legacy = _legacy(("old_check_no_longer_run", 1))
        report = compare_legacy_and_new(legacy, ())
        assert report.legacy_only_keys == ("old_check_no_longer_run",)
        assert report.has_unmatched_keys is True

    def test_new_only_rule_id(self) -> None:
        legacy = _legacy()
        new_results = (_result("brand_new_rule"),)
        report = compare_legacy_and_new(legacy, new_results)
        assert report.new_only_rule_ids == ("brand_new_rule",)
        assert report.has_unmatched_keys is True

    def test_totals_mismatch_even_with_matching_keys(self) -> None:
        # Same key on both sides, but different counts - a real signal
        # worth flagging even though the key itself "matched."
        legacy = _legacy(("respid is invalid", 5))
        new_results = (_result("respid is invalid", 0),)
        report = compare_legacy_and_new(legacy, new_results)
        assert report.common_keys == ("respid is invalid",)
        assert report.totals_match is False

    def test_empty_both_sides(self) -> None:
        report = compare_legacy_and_new(_legacy(), ())
        assert report.legacy_total == 0
        assert report.new_total == 0
        assert report.totals_match is True
        assert report.has_unmatched_keys is False

    def test_keys_sorted_deterministically(self) -> None:
        legacy = _legacy(("zebra_check", 1), ("apple_check", 1))
        report = compare_legacy_and_new(legacy, ())
        assert report.legacy_only_keys == ("apple_check", "zebra_check")
