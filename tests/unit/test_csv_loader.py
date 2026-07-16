"""Unit tests for insightengine.data.csv_loader."""

from __future__ import annotations

from pathlib import Path

import pytest

from insightengine.core.exceptions import DataLoadError
from insightengine.data.csv_loader import load_csv


def _write(tmp_path: Path, content: str, encoding: str = "utf-8") -> Path:
    path = tmp_path / "data.csv"
    path.write_bytes(content.encode(encoding))
    return path


class TestLoadCsvSuccess:
    def test_simple_file(self, tmp_path: Path) -> None:
        path = _write(tmp_path, "AGE,GENDER\n25,Male\n30,Female\n")
        table = load_csv(path)
        assert table.row_count == 2
        assert table.column_names == ("AGE", "GENDER")
        assert table.columns["AGE"] == ("25", "30")
        assert table.columns["GENDER"] == ("Male", "Female")

    def test_header_only_file_has_zero_rows(self, tmp_path: Path) -> None:
        path = _write(tmp_path, "AGE,GENDER\n")
        table = load_csv(path)
        assert table.row_count == 0
        assert table.columns["AGE"] == ()

    def test_missing_trailing_field_becomes_none(self, tmp_path: Path) -> None:
        path = _write(tmp_path, "AGE,GENDER,CITY\n25,Male\n")
        table = load_csv(path)
        assert table.columns["CITY"] == (None,)

    def test_bom_prefixed_utf8_file_strips_bom_from_header(self, tmp_path: Path) -> None:
        content = "AGE,GENDER\n25,Male\n"
        path = tmp_path / "bom.csv"
        path.write_bytes(b"\xef\xbb\xbf" + content.encode("utf-8"))
        table = load_csv(path)
        assert table.column_names == ("AGE", "GENDER")
        assert "\ufeffAGE" not in table.column_names

    def test_values_are_all_strings_or_none_no_type_coercion(self, tmp_path: Path) -> None:
        path = _write(tmp_path, "AGE\n25\n")
        table = load_csv(path)
        assert table.columns["AGE"] == ("25",)
        assert isinstance(table.columns["AGE"][0], str)


class TestLoadCsvFailures:
    def test_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(DataLoadError, match="not found"):
            load_csv(tmp_path / "does_not_exist.csv")

    def test_empty_file_raises(self, tmp_path: Path) -> None:
        path = _write(tmp_path, "")
        with pytest.raises(DataLoadError, match="no header row"):
            load_csv(path)

    def test_duplicate_header_raises(self, tmp_path: Path) -> None:
        path = _write(tmp_path, "AGE,AGE\n25,30\n")
        with pytest.raises(DataLoadError, match="duplicate header column 'AGE'"):
            load_csv(path)

    def test_wrong_encoding_raises_data_load_error(self, tmp_path: Path) -> None:
        path = tmp_path / "latin1.csv"
        # A byte sequence that is invalid UTF-8 but valid latin-1.
        path.write_bytes("NAME\nCaf\xe9\n".encode("latin-1"))
        with pytest.raises(DataLoadError, match="could not be decoded"):
            load_csv(path, encoding="utf-8-sig")

    def test_correct_alternate_encoding_succeeds(self, tmp_path: Path) -> None:
        path = tmp_path / "latin1.csv"
        path.write_bytes("NAME\nCaf\xe9\n".encode("latin-1"))
        table = load_csv(path, encoding="latin-1")
        assert table.columns["NAME"] == ("Caf\xe9",)

    def test_field_exceeding_csv_module_limit_raises_data_load_error(
        self, tmp_path: Path
    ) -> None:
        """Exercises the csv.Error handling branch directly, using the
        csv module's own field-size limit as a reliable, deterministic
        way to trigger a genuine csv.Error rather than guessing at a
        malformed-CSV byte sequence that may or may not raise depending
        on the csv module's (fairly lenient) parsing behavior.
        """
        import csv

        original_limit = csv.field_size_limit()
        csv.field_size_limit(10)
        try:
            path = _write(tmp_path, "NAME\nthis_value_is_longer_than_ten_chars\n")
            with pytest.raises(DataLoadError, match="is malformed"):
                load_csv(path)
        finally:
            csv.field_size_limit(original_limit)
