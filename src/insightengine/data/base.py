"""The backend-agnostic contract of the Data Engine.

Three things live here, and deliberately nothing else:

* :class:`RawTable` — a neutral, columnar, in-memory representation
  produced by format loaders (:mod:`insightengine.data.csv_loader` today;
  Excel/JSON/Parquet loaders in a later phase). A format loader's only
  job is turning a file into a ``RawTable``; it never touches pandas or
  any other backend-specific type.
* :class:`DataHandle` — a read-only view onto loaded tabular data.
  Implemented by :class:`insightengine.data.backends.pandas_backend.PandasDataHandle`
  today, and by whatever a future DuckDB/Parquet backend produces.
* :class:`DataBackend` — turns a :class:`RawTable` into a
  :class:`DataHandle`. This is the seam a caller swaps to change engines.

Both protocols are declared with :func:`typing.runtime_checkable` and are
structural (``Protocol``), not ``ABC`` — a test fake needs only to match
the shape, not inherit from anything in this module. That's deliberate:
the Phase 3 acceptance criterion is that a backend can be swapped for a
fake in tests, and an ABC subclassing requirement would work against
that, not for it.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from insightengine.core.exceptions import DataLoadError


@dataclass(frozen=True, slots=True)
class RawTable:
    """A backend-neutral, columnar in-memory table.

    Args:
        columns: Column name to a tuple of that column's values, in row
            order. Every column must have exactly :attr:`row_count`
            values — validated eagerly, not left as a caller's assumption.
        row_count: The number of rows in the table. Stored explicitly
            (rather than derived from the first column) so a zero-column
            table can still declare how many empty rows it has, and so
            validation catches a mismatched column before anything
            downstream does.
    """

    columns: Mapping[str, tuple[object, ...]]
    row_count: int

    def __post_init__(self) -> None:
        if self.row_count < 0:
            raise DataLoadError(f"row_count cannot be negative, got {self.row_count}.")
        for name, values in self.columns.items():
            if len(values) != self.row_count:
                raise DataLoadError(
                    f"Column {name!r} has {len(values)} values but the table "
                    f"declares row_count={self.row_count}."
                )

    @property
    def column_names(self) -> tuple[str, ...]:
        """Column names in declaration order."""
        return tuple(self.columns)


@runtime_checkable
class DataHandle(Protocol):
    """A read-only, queryable view onto a loaded tabular dataset."""

    @property
    def row_count(self) -> int:
        """Number of rows in this dataset."""
        ...

    @property
    def column_names(self) -> tuple[str, ...]:
        """Column names, in a stable, backend-defined order."""
        ...

    def column(self, name: str) -> Sequence[object]:
        """Return every value in column ``name``, in row order.

        Raises:
            UnknownColumnError: If ``name`` is not a column in this dataset.
        """
        ...

    def to_records(self) -> list[dict[str, object]]:
        """Return the whole dataset as a list of row dictionaries.

        Intended for small datasets, debugging, and tests — bulk
        row-by-row materialization defeats the purpose of a vectorized
        backend for anything but small data, and later phases (Phase 6's
        vectorized rule execution) should prefer :meth:`column` or a
        backend-specific bulk-query facility instead of this method.
        """
        ...


@runtime_checkable
class DataBackend(Protocol):
    """Something that can turn a :class:`RawTable` into a :class:`DataHandle`."""

    def load(self, table: RawTable) -> DataHandle:
        """Build a :class:`DataHandle` from a backend-neutral :class:`RawTable`."""
        ...
