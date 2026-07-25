"""Unit tests for insightengine.migration.legacy_log.

Fixture text matches exactly the format confirmed earlier in this
project by reading the real production `_QAedit.dms` template - not an
invented format.
"""

from __future__ import annotations

import pytest

from insightengine.core.exceptions import MetadataParseError
from insightengine.migration.legacy_log import (
    LegacyErrorLogEntry,
    parse_legacy_case_notes,
    parse_legacy_error_log,
)


class TestParseLegacyErrorLog:
    def test_full_real_shaped_log(self) -> None:
        text = (
            "CP4210 List of Errors\n"
            "respid is invalid\t3\n"
            "s4 vs s1 mismatch\t1\n"
            "\n"
            "Total completes : 250\n"
            "Total rejects   : 12\n"
        )
        log = parse_legacy_error_log(text)
        assert log.job_number == "CP4210"
        assert log.entries == (
            LegacyErrorLogEntry(key="respid is invalid", count=3),
            LegacyErrorLogEntry(key="s4 vs s1 mismatch", count=1),
        )
        assert log.total_completes == 250
        assert log.total_rejects == 12

    def test_no_totals_present(self) -> None:
        text = "CP4210 List of Errors\nsome error\t2\n"
        log = parse_legacy_error_log(text)
        assert log.total_completes is None
        assert log.total_rejects is None
        assert len(log.entries) == 1

    def test_no_entries_only_totals(self) -> None:
        text = "CP4210 List of Errors\n\nTotal completes : 100\nTotal rejects   : 0\n"
        log = parse_legacy_error_log(text)
        assert log.entries == ()
        assert log.total_completes == 100

    def test_missing_header_raises(self) -> None:
        with pytest.raises(MetadataParseError, match="header"):
            parse_legacy_error_log("not a real header\nsome error\t2\n")

    def test_empty_text_raises(self) -> None:
        with pytest.raises(MetadataParseError, match="header"):
            parse_legacy_error_log("")

    def test_malformed_count_raises(self) -> None:
        text = "CP4210 List of Errors\nsome error\tnot_a_number\n"
        with pytest.raises(MetadataParseError, match="Could not parse error count"):
            parse_legacy_error_log(text)

    def test_malformed_total_completes_raises(self) -> None:
        text = "CP4210 List of Errors\nTotal completes : oops\n"
        with pytest.raises(MetadataParseError, match="Could not parse"):
            parse_legacy_error_log(text)

    def test_unrecognized_line_shape_is_tolerated(self) -> None:
        # A line that's neither tab-delimited nor a totals line - the
        # module is deliberately lenient about content it has no
        # confirmed evidence about, per its own docstring.
        text = "CP4210 List of Errors\nsome unstructured note\nreal error\t1\n"
        log = parse_legacy_error_log(text)
        assert len(log.entries) == 1
        assert log.entries[0].key == "real error"


class TestParseLegacyCaseNotes:
    def test_real_shaped_notes(self) -> None:
        text = (
            "1001: respid is invalid |\n"
            "1002: age out of range |\n"
        )
        notes = parse_legacy_case_notes(text)
        assert len(notes) == 2
        assert notes[0].serial == "1001"
        assert notes[0].message == "respid is invalid |"
        assert notes[1].serial == "1002"

    def test_blank_lines_skipped(self) -> None:
        text = "1001: some message |\n\n\n1002: another |\n"
        notes = parse_legacy_case_notes(text)
        assert len(notes) == 2

    def test_empty_text_returns_empty_tuple(self) -> None:
        assert parse_legacy_case_notes("") == ()

    def test_malformed_line_raises(self) -> None:
        with pytest.raises(MetadataParseError, match="does not match"):
            parse_legacy_case_notes("this line has no colon-space separator\n")
