"""Unit tests for insightengine.data.loader."""

from __future__ import annotations

from pathlib import Path

import pytest

from insightengine.core.exceptions import UnsupportedFormatError
from insightengine.data.base import RawTable
from insightengine.data.loader import DataFormat, load_file, sniff_format


class TestSniffFormat:
    @pytest.mark.parametrize(
        ("filename", "expected"),
        [
            ("data.csv", DataFormat.CSV),
            ("data.CSV", DataFormat.CSV),
            ("data.xlsx", DataFormat.EXCEL),
            ("data.xls", DataFormat.EXCEL),
            ("data.json", DataFormat.JSON),
            ("data.parquet", DataFormat.PARQUET),
        ],
    )
    def test_recognizes_known_extensions(self, filename: str, expected: DataFormat) -> None:
        assert sniff_format(Path(filename)) is expected

    def test_unknown_extension_raises(self) -> None:
        with pytest.raises(UnsupportedFormatError, match="'.sav'"):
            sniff_format(Path("data.sav"))

    def test_error_message_lists_supported_extensions(self) -> None:
        with pytest.raises(UnsupportedFormatError, match=r"\.csv"):
            sniff_format(Path("data.txt"))


class _FakeDataHandle:
    def __init__(self, table: RawTable) -> None:
        self._table = table

    @property
    def row_count(self) -> int:
        return self._table.row_count

    @property
    def column_names(self) -> tuple[str, ...]:
        return self._table.column_names

    def column(self, name: str) -> tuple[object, ...]:
        return self._table.columns[name]

    def to_records(self) -> list[dict[str, object]]:
        return [
            {name: values[i] for name, values in self._table.columns.items()}
            for i in range(self._table.row_count)
        ]


class _FakeBackend:
    def __init__(self) -> None:
        self.loaded_tables: list[RawTable] = []

    def load(self, table: RawTable) -> _FakeDataHandle:
        self.loaded_tables.append(table)
        return _FakeDataHandle(table)


class TestLoadFile:
    def test_loads_csv_through_a_fake_backend(self, tmp_path: Path) -> None:
        path = tmp_path / "data.csv"
        path.write_text("AGE,GENDER\n25,Male\n30,Female\n", encoding="utf-8")

        backend = _FakeBackend()
        handle = load_file(path, backend)

        assert handle.row_count == 2
        assert handle.column("AGE") == ("25", "30")
        assert len(backend.loaded_tables) == 1

    def test_unimplemented_recognized_format_raises_unsupported_format_error(
        self, tmp_path: Path
    ) -> None:
        path = tmp_path / "data.xlsx"
        path.write_bytes(b"not a real xlsx file, just needs the right extension")

        with pytest.raises(UnsupportedFormatError, match="not yet implemented"):
            load_file(path, _FakeBackend())

    def test_unrecognized_extension_raises_before_any_load_attempt(
        self, tmp_path: Path
    ) -> None:
        path = tmp_path / "data.sav"
        backend = _FakeBackend()
        with pytest.raises(UnsupportedFormatError):
            load_file(path, backend)
        assert backend.loaded_tables == []
