"""Format detection and the top-level "load any recognized file" entry point.

:func:`sniff_format` recognizes every format named in the platform
architecture document's requirements (CSV, Excel, JSON, Parquet) now, so
this enum never needs a breaking change when a later phase adds the
Excel/JSON/Parquet loaders themselves. :func:`load_file` is honest about
the gap between "recognized" and "implemented": only CSV actually loads
in this phase. Asking it to load an Excel file raises a clear
:class:`UnsupportedFormatError` naming exactly what's missing, rather
than a placeholder function that silently returns nothing useful.
"""

from __future__ import annotations

from enum import StrEnum, unique
from pathlib import Path

from insightengine.core.exceptions import UnsupportedFormatError
from insightengine.data.base import DataBackend, DataHandle
from insightengine.data.csv_loader import load_csv


@unique
class DataFormat(StrEnum):
    """A tabular data file format the Data Engine can recognize.

    Membership here means "recognized by extension," not "loadable" —
    see the module docstring. Check :func:`load_file`'s exception if a
    given format isn't implemented yet.
    """

    CSV = "csv"
    EXCEL = "excel"
    JSON = "json"
    PARQUET = "parquet"


_EXTENSION_TO_FORMAT: dict[str, DataFormat] = {
    ".csv": DataFormat.CSV,
    ".xlsx": DataFormat.EXCEL,
    ".xls": DataFormat.EXCEL,
    ".json": DataFormat.JSON,
    ".parquet": DataFormat.PARQUET,
}


def sniff_format(path: Path) -> DataFormat:
    """Determine a file's :class:`DataFormat` from its extension.

    Args:
        path: The file path to inspect. Only the suffix is examined —
            the file need not exist yet.

    Raises:
        UnsupportedFormatError: If ``path``'s extension isn't one of the
            recognized formats.
    """
    suffix = path.suffix.lower()
    try:
        return _EXTENSION_TO_FORMAT[suffix]
    except KeyError as exc:
        supported = ", ".join(sorted(_EXTENSION_TO_FORMAT))
        raise UnsupportedFormatError(
            f"No recognized data format for extension {suffix!r} (file: {path}). "
            f"Supported extensions: {supported}."
        ) from exc


def load_file(path: Path, backend: DataBackend) -> DataHandle:
    """Load a file into a :class:`DataHandle` via ``backend``.

    Args:
        path: Path to the data file.
        backend: The :class:`~insightengine.data.base.DataBackend` to
            load the file's data into. Can be
            :class:`~insightengine.data.backends.pandas_backend.PandasBackend`
            or any other object matching the ``DataBackend`` protocol —
            including a test fake.

    Raises:
        UnsupportedFormatError: If the file's format is recognized but
            this phase does not implement loading it yet (Excel, JSON,
            Parquet), or if the extension isn't recognized at all.
        DataLoadError: If the file is a recognized, implemented format
            but fails to load (missing file, malformed content, etc.).
    """
    data_format = sniff_format(path)

    if data_format is DataFormat.CSV:
        table = load_csv(path)
        return backend.load(table)

    raise UnsupportedFormatError(
        f"{data_format.value!r} is a recognized format but is not yet "
        f"implemented. Supported in this phase: 'csv'."
    )
