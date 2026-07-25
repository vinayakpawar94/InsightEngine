"""Parsing IBM Dimensions' legacy QA output files.

**This module is grounded in real evidence, not speculation:** the exact
format below was confirmed earlier in this project by reading the
actual production ``_QAedit.dms`` template directly (not a generic IBM
sample) — see this project's Dimensions knowledge base, Chapter 9. That
review found:

* ``<JOBNUMBER>_ErrorLog.txt`` — a header line (``"<JOBNUMBER> List of
  Errors"``), then tab-delimited ``<error key>\\t<count>`` lines, a
  blank line, then ``Total completes : N`` / ``Total rejects   : N``.
* ``<JOBNUMBER>_QAout2.txt`` — free-text, one line per flagged
  respondent, shaped ``"<serial>: <message> |"``.

Both formats are implemented and tested against real-shaped fixture
text matching exactly what that earlier review confirmed — this is the
one part of the migration bridge that rests on solid ground, unlike
:mod:`insightengine.migration.sav_legacy`'s MRSET handling.
"""

from __future__ import annotations

from dataclasses import dataclass

from insightengine.core.exceptions import MetadataParseError

_HEADER_SUFFIX = " List of Errors"
_COMPLETES_PREFIX = "Total completes"
_REJECTS_PREFIX = "Total rejects"


@dataclass(frozen=True, slots=True)
class LegacyErrorLogEntry:
    """One tab-delimited ``<key>\\t<count>`` line from a legacy ErrorLog."""

    key: str
    count: int


@dataclass(frozen=True, slots=True)
class LegacyErrorLog:
    """A parsed legacy ``<JOBNUMBER>_ErrorLog.txt`` file."""

    job_number: str
    entries: tuple[LegacyErrorLogEntry, ...]
    total_completes: int | None
    total_rejects: int | None


@dataclass(frozen=True, slots=True)
class LegacyCaseNote:
    """One free-text ``"<serial>: <message>"`` line from a legacy QAout2 file."""

    serial: str
    message: str


def parse_legacy_error_log(text: str) -> LegacyErrorLog:
    """Parse a legacy ``<JOBNUMBER>_ErrorLog.txt`` file's contents.

    Raises:
        MetadataParseError: If the header line doesn't match the
            confirmed ``"<JOBNUMBER> List of Errors"`` shape, or a
            count value isn't a valid integer.
    """
    lines = text.splitlines()
    if not lines or not lines[0].endswith(_HEADER_SUFFIX):
        raise MetadataParseError(
            f"Legacy error log does not start with the expected "
            f"'<JOBNUMBER>{_HEADER_SUFFIX}' header line."
        )
    job_number = lines[0][: -len(_HEADER_SUFFIX)]

    entries: list[LegacyErrorLogEntry] = []
    total_completes: int | None = None
    total_rejects: int | None = None

    for line in lines[1:]:
        if not line.strip():
            continue
        if line.startswith(_COMPLETES_PREFIX):
            total_completes = _parse_total(line, _COMPLETES_PREFIX)
        elif line.startswith(_REJECTS_PREFIX):
            total_rejects = _parse_total(line, _REJECTS_PREFIX)
        elif "\t" in line:
            key, _, count_text = line.partition("\t")
            entries.append(LegacyErrorLogEntry(key=key, count=_parse_count(count_text, line)))
        # Any other line (blank already skipped above) is left
        # unrecognized rather than rejected outright - real legacy logs
        # may contain incidental formatting this project has no evidence
        # about one way or the other; being lenient here doesn't lose
        # any confirmed information, since every line shape this module
        # actually knows about is still parsed correctly.

    return LegacyErrorLog(
        job_number=job_number,
        entries=tuple(entries),
        total_completes=total_completes,
        total_rejects=total_rejects,
    )


def _parse_total(line: str, prefix: str) -> int:
    _, _, value_text = line.partition(":")
    try:
        return int(value_text.strip())
    except ValueError as exc:
        raise MetadataParseError(f"Could not parse {prefix!r} line as an integer: {line!r}") from exc


def _parse_count(count_text: str, line: str) -> int:
    try:
        return int(count_text.strip())
    except ValueError as exc:
        raise MetadataParseError(f"Could not parse error count in line: {line!r}") from exc


def parse_legacy_case_notes(text: str) -> tuple[LegacyCaseNote, ...]:
    """Parse a legacy ``<JOBNUMBER>_QAout2.txt`` file's contents.

    Raises:
        MetadataParseError: If a non-blank line doesn't contain the
            confirmed ``"<serial>: <message>"`` separator.
    """
    notes: list[LegacyCaseNote] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        serial, separator, message = line.partition(": ")
        if not separator:
            raise MetadataParseError(
                f"Legacy case note line does not match the expected "
                f"'<serial>: <message>' shape: {line!r}"
            )
        notes.append(LegacyCaseNote(serial=serial, message=message))
    return tuple(notes)
