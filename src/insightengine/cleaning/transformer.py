"""``Transformer``, the composable pipeline, and the bridge to a live
:class:`~insightengine.data.base.DataHandle`.

``Transformer`` is a real ``abc.ABC``, not a structural ``Protocol`` like
:class:`~insightengine.data.base.DataBackend` or
:class:`~insightengine.metadata.base.MetadataParser`. That's a
deliberate difference: those two each have exactly one interchangeable
implementation and exist purely to let a caller swap engines.
Transformers are meant to be written, subclassed, and composed into a
pipeline — a concrete shared base is the right tool for that, not a
purely structural contract.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence

from insightengine.core.codebook import Codebook
from insightengine.data.base import DataBackend, DataHandle, RawTable


class Transformer(ABC):
    """A single, named transformation from one :class:`RawTable` to another."""

    @abstractmethod
    def apply(self, table: RawTable, codebook: Codebook) -> RawTable:
        """Return a new :class:`RawTable` with this transformation applied.

        Must not mutate ``table`` — ``RawTable`` is frozen, so this is
        enforced by the type itself, not just a convention: build and
        return a new instance.
        """
        raise NotImplementedError  # pragma: no cover


class TransformerPipeline:
    """Runs a sequence of :class:`Transformer` instances in order,
    threading the table through each one.
    """

    def __init__(self, transformers: Sequence[Transformer]) -> None:
        self._transformers = tuple(transformers)

    @property
    def transformers(self) -> tuple[Transformer, ...]:
        """The transformers this pipeline runs, in order."""
        return self._transformers

    def run(self, table: RawTable, codebook: Codebook) -> RawTable:
        """Apply every transformer in order, returning the final table."""
        for transformer in self._transformers:
            table = transformer.apply(table, codebook)
        return table

    def run_against_handle(
        self, data: DataHandle, codebook: Codebook, backend: DataBackend
    ) -> DataHandle:
        """Extract ``data`` into a :class:`RawTable`, run the pipeline,
        and reload the result through ``backend``.

        This is the actual end-to-end path from a live dataset to a
        cleaned live dataset: :func:`to_raw_table` extracts, :meth:`run`
        transforms, ``backend.load`` reloads.
        """
        table = to_raw_table(data)
        cleaned = self.run(table, codebook)
        return backend.load(cleaned)


def to_raw_table(data: DataHandle) -> RawTable:
    """Extract a live :class:`~insightengine.data.base.DataHandle` into a
    backend-neutral :class:`RawTable`.

    Pulls each column exactly once via
    :meth:`~insightengine.data.base.DataHandle.column` — not
    :meth:`~insightengine.data.base.DataHandle.to_records`, which Phase 3
    explicitly documents as unsuitable for anything but small/debug use.
    """
    columns = {name: tuple(data.column(name)) for name in data.column_names}
    return RawTable(columns=columns, row_count=data.row_count)
