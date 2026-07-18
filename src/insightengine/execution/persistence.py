"""JSON persistence for the two artifact types a resumed run needs to
reload without recomputing: a :class:`~insightengine.data.base.RawTable`
(the cleaned data) and a sequence of
:class:`~insightengine.validation.results.ValidationResult` (validation
findings).

``ValidationResult`` is fully JSON-native (str/int/enum-as-string
fields) and needs no special handling. ``RawTable`` is not — Phase 7's
canonical multi-response representation is ``frozenset[int]``, which
JSON has no native concept of, so it's round-tripped through an
explicit tagged encoding (``{"__frozenset__": [...]}"``) rather than
silently degraded to a plain list, which would lose the "this is a
multi-response selection, not just an ordered list" distinction on load.
"""

from __future__ import annotations

import json
from pathlib import Path

from insightengine.core.exceptions import TransformationError
from insightengine.core.types import Severity
from insightengine.data.base import RawTable
from insightengine.execution.manifest import atomic_write_text
from insightengine.validation.results import ValidationResult

_FROZENSET_TAG = "__frozenset__"


def _encode_value(value: object) -> object:
    if isinstance(value, frozenset):
        return {_FROZENSET_TAG: sorted(value, key=repr)}
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    raise TransformationError(
        f"Cannot persist a value of type {type(value).__name__} ({value!r}) — "
        f"only None, bool, int, float, str, and frozenset are supported."
    )


def _decode_value(value: object) -> object:
    if isinstance(value, dict) and set(value) == {_FROZENSET_TAG}:
        return frozenset(value[_FROZENSET_TAG])
    return value


def save_raw_table(table: RawTable, path: Path) -> None:
    """Persist ``table`` to ``path`` as JSON, atomically."""
    payload = {
        "row_count": table.row_count,
        "columns": {
            name: [_encode_value(v) for v in values] for name, values in table.columns.items()
        },
    }
    atomic_write_text(path, json.dumps(payload, indent=2))


def load_raw_table(path: Path) -> RawTable:
    """Load a :class:`RawTable` previously written by :func:`save_raw_table`.

    Raises:
        TransformationError: If ``path``'s contents don't match the
            expected shape.
    """
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        columns = {
            name: tuple(_decode_value(v) for v in values)
            for name, values in raw["columns"].items()
        }
        return RawTable(columns=columns, row_count=raw["row_count"])
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise TransformationError(f"Could not load persisted table from {path}: {exc}") from exc


def save_validation_results(results: tuple[ValidationResult, ...], path: Path) -> None:
    """Persist ``results`` to ``path`` as JSON, atomically."""
    payload = [
        {
            "rule_id": r.rule_id,
            "severity": r.severity.value,
            "message": r.message,
            "row_index": r.row_index,
            "variables": list(r.variables),
        }
        for r in results
    ]
    atomic_write_text(path, json.dumps(payload, indent=2))


def load_validation_results(path: Path) -> tuple[ValidationResult, ...]:
    """Load results previously written by :func:`save_validation_results`.

    Raises:
        TransformationError: If ``path``'s contents don't match the
            expected shape.
    """
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return tuple(
            ValidationResult(
                rule_id=item["rule_id"],
                severity=Severity(item["severity"]),
                message=item["message"],
                row_index=item["row_index"],
                variables=tuple(item["variables"]),
            )
            for item in raw
        )
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise TransformationError(
            f"Could not load persisted validation results from {path}: {exc}"
        ) from exc
