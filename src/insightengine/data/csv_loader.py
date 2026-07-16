"""CSV file loading: turns a ``.csv`` file into a backend-neutral :class:`RawTable`.

Scope decision, stated explicitly: this loader performs **no type
coercion**. Every value is either the raw string from the file or
``None`` for a missing field. Guessing that a column is numeric without
a :class:`~insightengine.core.codebook.Codebook` to check against would
mean inventing fragile heuristics (is "007" a string or an int? is "1.0"
a float or a categorical code?) — that decision belongs to whichever
later phase wires the Data Engine up to actual questionnaire metadata,
not to a format-agnostic file reader that has no metadata to consult.

Encoding defaults to ``utf-8-sig`` rather than plain ``utf-8``,
deliberately: it transparently strips a leading UTF-8 byte-order-mark if
one is present (extremely common in CSVs exported from Excel) and
behaves identically to ``utf-8`` when no BOM exists. Plain ``utf-8``
would silently leave the BOM attached to the first header name,
producing a header that looks right when printed but never matches an
expected column name in an equality check — exactly the kind of
encoding pitfall this project has hit before, in a different system.
"""

from __future__ import annotations

import csv
from pathlib import Path

from insightengine.core.exceptions import DataLoadError
from insightengine.data.base import RawTable


def load_csv(path: Path, *, encoding: str = "utf-8-sig") -> RawTable:
    """Load a CSV file into a :class:`RawTable`.

    Args:
        path: Path to the CSV file. Must have a header row.
        encoding: Text encoding to decode the file with.

    Returns:
        A :class:`RawTable` with one column per header entry, all values
        either ``str`` or ``None`` (for a row with a missing trailing
        field).

    Raises:
        DataLoadError: If the file does not exist, has no header row,
            has duplicate header names, cannot be decoded with
            ``encoding``, or is otherwise malformed CSV.
    """
    if not path.is_file():
        raise DataLoadError(f"CSV file not found: {path}")

    try:
        with path.open("r", encoding=encoding, newline="") as handle:
            reader = csv.DictReader(handle)

            if reader.fieldnames is None:
                raise DataLoadError(f"CSV file {path} has no header row.")

            fieldnames = list(reader.fieldnames)
            _require_unique_headers(fieldnames, path)

            columns: dict[str, list[object]] = {name: [] for name in fieldnames}
            row_count = 0
            for row in reader:
                for name in fieldnames:
                    columns[name].append(row.get(name))
                row_count += 1
    except UnicodeDecodeError as exc:
        raise DataLoadError(
            f"CSV file {path} could not be decoded as {encoding!r}: {exc}"
        ) from exc
    except csv.Error as exc:
        raise DataLoadError(f"CSV file {path} is malformed: {exc}") from exc

    return RawTable(
        columns={name: tuple(values) for name, values in columns.items()},
        row_count=row_count,
    )


def _require_unique_headers(fieldnames: list[str], path: Path) -> None:
    """Raise :class:`DataLoadError` if ``fieldnames`` contains a duplicate.

    A duplicate header name is a silent-data-loss trap with
    :class:`csv.DictReader`: two columns sharing a name collapse into one
    dict key per row, and everything but the last occurrence's value is
    lost without any error. Rejecting it outright is safer than silently
    keeping only the last column.
    """
    seen: set[str] = set()
    for name in fieldnames:
        if name in seen:
            raise DataLoadError(
                f"CSV file {path} has duplicate header column {name!r}."
            )
        seen.add(name)
