"""Category recoding: remapping a single-value variable's codes.

Deliberately scoped to single-value variables (a
:class:`~insightengine.core.codebook.SingleQuestion`,
:class:`~insightengine.core.codebook.NumericQuestion`, or any other
question whose column holds one scalar per row) — recoding *within* a
multi-response selection (e.g. merging two categories inside a
:class:`~insightengine.core.codebook.MultiQuestion`'s collection of
codes) is a genuinely different operation and is not implemented here.
If that's needed later, it deserves its own considered pass, not a
bolt-on to this transformer.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from insightengine.cleaning.transformer import Transformer
from insightengine.core.codebook import Codebook
from insightengine.core.exceptions import TransformationError, UnknownVariableError
from insightengine.data.base import RawTable


@dataclass(frozen=True, slots=True)
class RecodeMap:
    """A single variable's recode rule.

    Args:
        variable: The column to recode.
        mapping: Old code to new code.
        default: What an unmapped code becomes. ``None`` means "leave
            the original value unchanged" — distinct from mapping a code
            *to* ``None``, which is an explicit, valid entry in
            ``mapping`` itself if that's genuinely intended.
    """

    variable: str
    mapping: Mapping[int, int]
    default: int | None = None

    def __post_init__(self) -> None:
        if not self.variable.strip():
            raise TransformationError("A RecodeMap's variable cannot be empty.")


class RecodeTransformer(Transformer):
    """Applies a sequence of :class:`RecodeMap` rules, one variable each."""

    def __init__(self, recodes: Sequence[RecodeMap]) -> None:
        self._recodes = tuple(recodes)

    def apply(self, table: RawTable, codebook: Codebook) -> RawTable:
        columns = dict(table.columns)
        for recode in self._recodes:
            if recode.variable not in columns:
                raise UnknownVariableError(
                    f"RecodeMap references unknown variable {recode.variable!r}."
                )
            columns[recode.variable] = tuple(
                self._recode_value(value, recode) for value in columns[recode.variable]
            )
        return RawTable(columns=columns, row_count=table.row_count)

    def _recode_value(self, value: object, recode: RecodeMap) -> object:
        if value is None:
            return None

        code = _coerce_int(value)
        if code is None:
            raise TransformationError(
                f"RecodeMap for {recode.variable!r}: cannot recode non-integer-"
                f"like value {value!r}."
            )

        if code in recode.mapping:
            return recode.mapping[code]
        if recode.default is not None:
            return recode.default
        return value


def _coerce_int(value: object) -> int | None:
    """Same tolerance as Phase 6's category-code coercion — a numeric
    column with any missing values commonly gets upcast to ``float64`` by
    pandas, so a value declared/expected as ``int`` may arrive as a
    whole-number ``float``. Deliberately re-implemented here rather than
    imported from :mod:`insightengine.validation.executor`, whose
    equivalent helper is private (leading underscore) to that module —
    reaching into another module's private name is more fragile than a
    small, self-contained duplication.
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None
