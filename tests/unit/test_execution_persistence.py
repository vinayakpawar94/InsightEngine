"""Unit tests for insightengine.execution.persistence."""

from __future__ import annotations

from pathlib import Path

import pytest

from insightengine.core.exceptions import TransformationError
from insightengine.core.types import Severity
from insightengine.data.base import RawTable
from insightengine.execution.persistence import (
    load_raw_table,
    load_validation_results,
    save_raw_table,
    save_validation_results,
)
from insightengine.validation.results import ValidationResult


class TestRawTablePersistence:
    def test_round_trip_scalars(self, tmp_path: Path) -> None:
        table = RawTable(
            columns={"AGE": (25, 30, None), "NAME": ("Alice", "Bob", None)}, row_count=3
        )
        path = tmp_path / "table.json"
        save_raw_table(table, path)
        loaded = load_raw_table(path)
        assert loaded == table

    def test_round_trip_frozenset_values(self, tmp_path: Path) -> None:
        table = RawTable(columns={"Q8": (frozenset({1, 2}), None, frozenset())}, row_count=3)
        path = tmp_path / "table.json"
        save_raw_table(table, path)
        loaded = load_raw_table(path)
        assert loaded.columns["Q8"] == (frozenset({1, 2}), None, frozenset())
        assert isinstance(loaded.columns["Q8"][0], frozenset)

    def test_round_trip_float_and_bool(self, tmp_path: Path) -> None:
        table = RawTable(columns={"X": (1.5, True, False)}, row_count=3)
        path = tmp_path / "table.json"
        save_raw_table(table, path)
        loaded = load_raw_table(path)
        assert loaded.columns["X"] == (1.5, True, False)

    def test_unsupported_value_type_raises_on_save(self, tmp_path: Path) -> None:
        table = RawTable(columns={"X": ([1, 2],)}, row_count=1)  # plain list, not frozenset
        path = tmp_path / "table.json"
        with pytest.raises(TransformationError, match="Cannot persist"):
            save_raw_table(table, path)

    def test_load_malformed_file_raises(self, tmp_path: Path) -> None:
        path = tmp_path / "table.json"
        path.write_text("not json{{{", encoding="utf-8")
        with pytest.raises(TransformationError, match="Could not load"):
            load_raw_table(path)

    def test_load_missing_columns_key_raises(self, tmp_path: Path) -> None:
        path = tmp_path / "table.json"
        path.write_text('{"row_count": 1}', encoding="utf-8")
        with pytest.raises(TransformationError, match="Could not load"):
            load_raw_table(path)


class TestValidationResultPersistence:
    def test_round_trip(self, tmp_path: Path) -> None:
        results = (
            ValidationResult(
                rule_id="r1",
                severity=Severity.ERROR,
                message="bad",
                row_index=0,
                variables=("Q1",),
            ),
            ValidationResult(
                rule_id="r2", severity=Severity.WARNING, message="hmm", row_index=1
            ),
        )
        path = tmp_path / "results.json"
        save_validation_results(results, path)
        loaded = load_validation_results(path)
        assert loaded == results

    def test_round_trip_empty(self, tmp_path: Path) -> None:
        path = tmp_path / "results.json"
        save_validation_results((), path)
        assert load_validation_results(path) == ()

    def test_load_malformed_file_raises(self, tmp_path: Path) -> None:
        path = tmp_path / "results.json"
        path.write_text("not json{{{", encoding="utf-8")
        with pytest.raises(TransformationError, match="Could not load"):
            load_validation_results(path)

    def test_load_missing_field_raises(self, tmp_path: Path) -> None:
        path = tmp_path / "results.json"
        path.write_text('[{"rule_id": "r1"}]', encoding="utf-8")
        with pytest.raises(TransformationError, match="Could not load"):
            load_validation_results(path)

    def test_load_invalid_severity_raises(self, tmp_path: Path) -> None:
        path = tmp_path / "results.json"
        path.write_text(
            '[{"rule_id": "r1", "severity": "bogus", "message": "x", '
            '"row_index": 0, "variables": []}]',
            encoding="utf-8",
        )
        with pytest.raises(TransformationError, match="Could not load"):
            load_validation_results(path)
