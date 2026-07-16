"""Unit tests for insightengine.data.backends.pandas_backend."""

from __future__ import annotations

import pytest

from insightengine.core.exceptions import UnknownColumnError
from insightengine.data.backends.pandas_backend import PandasBackend, PandasDataHandle
from insightengine.data.base import DataBackend, DataHandle, RawTable


class TestPandasBackendSatisfiesProtocols:
    def test_backend_satisfies_data_backend_protocol(self) -> None:
        assert isinstance(PandasBackend(), DataBackend)

    def test_handle_satisfies_data_handle_protocol(self) -> None:
        table = RawTable(columns={"A": (1,)}, row_count=1)
        handle = PandasBackend().load(table)
        assert isinstance(handle, DataHandle)


class TestPandasBackendLoad:
    def test_basic_table(self) -> None:
        table = RawTable(
            columns={"AGE": (25, 30, 45), "GENDER": ("Male", "Female", "Male")},
            row_count=3,
        )
        handle = PandasBackend().load(table)

        assert handle.row_count == 3
        assert handle.column_names == ("AGE", "GENDER")
        assert handle.column("AGE") == (25, 30, 45)
        assert handle.column("GENDER") == ("Male", "Female", "Male")

    def test_zero_row_table(self) -> None:
        table = RawTable(columns={"AGE": ()}, row_count=0)
        handle = PandasBackend().load(table)
        assert handle.row_count == 0
        assert handle.column("AGE") == ()

    def test_zero_column_nonzero_row_table(self) -> None:
        """A RawTable with no columns but a declared row count is a real,
        if unusual, shape (e.g. a dataset with no variables selected yet)
        that plain pd.DataFrame({}) can't represent on its own.
        """
        table = RawTable(columns={}, row_count=5)
        handle = PandasBackend().load(table)
        assert handle.row_count == 5
        assert handle.column_names == ()

    def test_values_with_none_are_preserved(self) -> None:
        table = RawTable(columns={"CITY": ("NYC", None, "LA")}, row_count=3)
        handle = PandasBackend().load(table)
        assert handle.column("CITY") == ("NYC", None, "LA")

    def test_unknown_column_raises(self) -> None:
        table = RawTable(columns={"AGE": (25,)}, row_count=1)
        handle = PandasBackend().load(table)
        with pytest.raises(UnknownColumnError, match="GENDER"):
            handle.column("GENDER")

    def test_to_records(self) -> None:
        table = RawTable(
            columns={"AGE": (25, 30), "GENDER": ("Male", "Female")}, row_count=2
        )
        handle = PandasBackend().load(table)
        assert handle.to_records() == [
            {"AGE": 25, "GENDER": "Male"},
            {"AGE": 30, "GENDER": "Female"},
        ]


class TestDenormalizeMissing:
    """Direct tests of the internal NaN/None normalization helper.

    Tested in isolation, rather than relying only on end-to-end pandas
    behavior, because whether pandas actually produces a raw ``None``
    (vs. converting it to float NaN) for a given column depends on
    pandas' own dtype-inference rules, which aren't a contract this test
    suite should depend on to exercise every branch of this function.
    """

    def test_none_passes_through_as_none(self) -> None:
        from insightengine.data.backends.pandas_backend import _denormalize_missing

        assert _denormalize_missing(None) is None

    def test_float_nan_becomes_none(self) -> None:
        from insightengine.data.backends.pandas_backend import _denormalize_missing

        assert _denormalize_missing(float("nan")) is None

    def test_ordinary_string_passes_through_unchanged(self) -> None:
        from insightengine.data.backends.pandas_backend import _denormalize_missing

        assert _denormalize_missing("hello") == "hello"

    def test_ordinary_number_passes_through_unchanged(self) -> None:
        from insightengine.data.backends.pandas_backend import _denormalize_missing

        assert _denormalize_missing(42) == 42
        assert _denormalize_missing(3.14) == 3.14
    def test_column_names_are_strings(self) -> None:
        import pandas as pd

        df = pd.DataFrame({1: [1, 2], "b": [3, 4]})
        handle = PandasDataHandle(df)
        assert handle.column_names == ("1", "b")
