"""A :class:`~insightengine.data.base.DataBackend` implementation backed
by :class:`pandas.DataFrame`.

This is the one concrete engine implementation in this phase. Everything
in :mod:`insightengine.data.base`, :mod:`insightengine.data.loader`, and
:mod:`insightengine.data.csv_loader` is written against the
``DataBackend``/``DataHandle`` protocols and has no import of ``pandas``
at all — this module is the only place in the Data Engine that does.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

import pandas as pd

from insightengine.core.exceptions import UnknownColumnError
from insightengine.data.base import RawTable


def _denormalize_missing(value: object) -> object:
    """Map pandas' internal missing-value representation back to ``None``.

    pandas silently converts ``None`` in an object-dtype column to
    ``float('nan')`` when a column mixes strings and ``None`` (confirmed
    empirically while testing this backend — not a documented guarantee
    to rely on blindly). The ``DataHandle`` contract promises ``None``
    for missing values, matching what :mod:`insightengine.data.csv_loader`
    actually produces, so every read path in this module normalizes
    through this function rather than exposing pandas' internal
    representation to callers.

    Scoped deliberately to the float-NaN case: today's loaders only ever
    produce ``str`` or ``None`` values, so a plain ``isinstance(value,
    float)`` check (true for both Python ``float`` and numpy's
    ``float64``, which subclasses it) covers every missing-value case
    pandas can actually produce here. ``pandas.NaT``/``pandas.NA`` (from
    datetime or nullable-integer dtypes) aren't handled — there is no
    loader yet that produces those dtypes, and adding speculative
    handling for them now would be exactly the kind of untested,
    unjustified code this project avoids. Revisit this function if a
    future format loader introduces such a dtype.
    """
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    return value


class PandasDataHandle:
    """A :class:`~insightengine.data.base.DataHandle` backed by a pandas
    :class:`~pandas.DataFrame`.

    Not constructed directly by callers outside this module — obtained
    via :meth:`PandasBackend.load`.
    """

    def __init__(self, dataframe: pd.DataFrame) -> None:
        self._df = dataframe

    @property
    def row_count(self) -> int:
        return len(self._df)

    @property
    def column_names(self) -> tuple[str, ...]:
        return tuple(str(name) for name in self._df.columns)

    def column(self, name: str) -> Sequence[object]:
        if name not in self._df.columns:
            raise UnknownColumnError(
                f"No column named {name!r}. Available columns: "
                f"{', '.join(self.column_names)}."
            )
        raw_values: list[object] = self._df[name].tolist()
        return tuple(_denormalize_missing(v) for v in raw_values)

    def to_records(self) -> list[dict[str, object]]:
        raw_records: list[dict[str, object]] = self._df.to_dict(orient="records")  # type: ignore[assignment]
        return [
            {key: _denormalize_missing(value) for key, value in record.items()}
            for record in raw_records
        ]


class PandasBackend:
    """A :class:`~insightengine.data.base.DataBackend` that loads data
    into an in-memory :class:`pandas.DataFrame`.
    """

    def load(self, table: RawTable) -> PandasDataHandle:
        """Build a :class:`PandasDataHandle` from ``table``.

        An explicit empty-columns case is handled directly rather than
        left to :class:`pandas.DataFrame`'s own defaults: a zero-column
        ``RawTable`` with a non-zero ``row_count`` (no columns, N empty
        rows) is a legitimate, if unusual, table shape that
        ``pd.DataFrame({})`` alone cannot represent, since an empty
        column mapping gives pandas no way to infer a row count.
        """
        if not table.columns:
            dataframe = pd.DataFrame(index=range(table.row_count))
        else:
            dataframe = pd.DataFrame(
                {name: list(values) for name, values in table.columns.items()}
            )
        return PandasDataHandle(dataframe)
