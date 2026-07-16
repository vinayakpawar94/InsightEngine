"""Unit tests for insightengine.data.base."""

from __future__ import annotations

import pytest

from insightengine.core.exceptions import DataLoadError
from insightengine.data.base import DataBackend, DataHandle, RawTable


class TestRawTable:
    def test_valid_table(self) -> None:
        table = RawTable(columns={"A": (1, 2, 3), "B": ("x", "y", "z")}, row_count=3)
        assert table.row_count == 3
        assert table.column_names == ("A", "B")

    def test_zero_row_table_is_valid(self) -> None:
        table = RawTable(columns={"A": ()}, row_count=0)
        assert table.row_count == 0

    def test_zero_column_table_is_valid(self) -> None:
        table = RawTable(columns={}, row_count=5)
        assert table.row_count == 5
        assert table.column_names == ()

    def test_negative_row_count_raises(self) -> None:
        with pytest.raises(DataLoadError, match="cannot be negative"):
            RawTable(columns={}, row_count=-1)

    def test_mismatched_column_length_raises(self) -> None:
        with pytest.raises(DataLoadError, match="has 2 values but"):
            RawTable(columns={"A": (1, 2)}, row_count=3)

    def test_is_frozen(self) -> None:
        table = RawTable(columns={"A": (1,)}, row_count=1)
        with pytest.raises(Exception):
            table.row_count = 2  # type: ignore[misc]


class _FakeDataHandle:
    """A minimal DataHandle implementation with no pandas dependency,
    used to prove the protocol is genuinely structural.
    """

    def __init__(self, columns: dict[str, tuple[object, ...]], row_count: int) -> None:
        self._columns = columns
        self._row_count = row_count

    @property
    def row_count(self) -> int:
        return self._row_count

    @property
    def column_names(self) -> tuple[str, ...]:
        return tuple(self._columns)

    def column(self, name: str) -> tuple[object, ...]:
        return self._columns[name]

    def to_records(self) -> list[dict[str, object]]:
        return [
            {name: values[i] for name, values in self._columns.items()}
            for i in range(self._row_count)
        ]


class _FakeBackend:
    """A minimal DataBackend implementation with no pandas dependency."""

    def load(self, table: RawTable) -> _FakeDataHandle:
        return _FakeDataHandle(dict(table.columns), table.row_count)


class TestProtocolsAreStructural:
    def test_fake_data_handle_satisfies_protocol(self) -> None:
        handle = _FakeDataHandle({"A": (1, 2)}, 2)
        assert isinstance(handle, DataHandle)

    def test_fake_backend_satisfies_protocol(self) -> None:
        assert isinstance(_FakeBackend(), DataBackend)

    def test_fake_backend_round_trips_a_raw_table(self) -> None:
        table = RawTable(columns={"A": (1, 2, 3)}, row_count=3)
        handle = _FakeBackend().load(table)
        assert handle.row_count == 3
        assert handle.column("A") == (1, 2, 3)
        assert handle.to_records() == [{"A": 1}, {"A": 2}, {"A": 3}]
