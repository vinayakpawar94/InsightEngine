"""Multi-response expansion: converting a
:class:`~insightengine.core.codebook.MultiQuestion` answer from whatever
raw shape a data source provides into the canonical in-memory
representation Phase 6's validation executor already assumed —
a collection of selected category codes, or ``None`` if unanswered.

Two real-world raw shapes are supported, since both are genuinely common
and neither should be assumed away:

1. **A delimited string in one column** — e.g. a CSV cell
   ``"1,3,5"`` under a single column named after the question id
   (``Q8``). The natural shape for CSV-sourced data, since Phase 3's CSV
   loader only ever produces one column per header.
2. **Binary indicator columns** — one column per category code
   (``Q8_1``, ``Q8_2``, ``Q8_3``, each holding a truthy/falsy value).
   This is the actual legacy Dimensions convention confirmed earlier in
   this project (the ``MultiPunch``/``AnswerCount()`` pattern) — real
   data exported from a Dimensions-based system is likely to already be
   in this shape, not the delimited-string one.

A column already holding real collections (``list``/``tuple``/``set``/
``frozenset``) is left untouched — this transformer is idempotent on
already-clean data.
"""

from __future__ import annotations

from insightengine.cleaning.transformer import Transformer
from insightengine.core.codebook import Codebook, MultiQuestion
from insightengine.core.exceptions import TransformationError
from insightengine.data.base import RawTable

_TRUTHY_INDICATOR_VALUES = frozenset({"1", 1, True})
_FALSY_INDICATOR_VALUES = frozenset({"0", 0, False, "", None})


class MultiResponseExpansionTransformer(Transformer):
    """Expands every :class:`~insightengine.core.codebook.MultiQuestion`
    in the codebook into the canonical selection-collection shape.

    Args:
        delimiter: The separator used when parsing a delimited-string
            column. Only used for questions found in that shape.
    """

    def __init__(self, *, delimiter: str = ",") -> None:
        self._delimiter = delimiter

    def apply(self, table: RawTable, codebook: Codebook) -> RawTable:
        columns = dict(table.columns)
        changed = False

        for question in codebook.questions:
            if not isinstance(question, MultiQuestion):
                continue

            if question.id in columns:
                if _already_expanded(columns[question.id]):
                    continue
                columns[question.id] = self._expand_delimited_column(
                    question, columns[question.id]
                )
                changed = True
                continue

            indicator_columns = _indicator_column_names(question, columns)
            if indicator_columns is not None:
                columns[question.id] = _merge_indicator_columns(
                    question, indicator_columns, columns, table.row_count
                )
                for name in indicator_columns.values():
                    del columns[name]
                changed = True

        if not changed:
            return table
        return RawTable(columns=columns, row_count=table.row_count)

    def _expand_delimited_column(
        self, question: MultiQuestion, values: tuple[object, ...]
    ) -> tuple[object, ...]:
        return tuple(self._parse_delimited(question, value) for value in values)

    def _parse_delimited(self, question: MultiQuestion, value: object) -> object:
        if value is None:
            return None
        if not isinstance(value, str):
            raise TransformationError(
                f"MultiQuestion {question.id!r}: expected a delimited string or "
                f"None, got {type(value).__name__} ({value!r})."
            )
        stripped = value.strip()
        if not stripped:
            return None

        codes: set[object] = set()
        for token in stripped.split(self._delimiter):
            token = token.strip()
            if not token:
                continue
            try:
                codes.add(int(token))
            except ValueError as exc:
                raise TransformationError(
                    f"MultiQuestion {question.id!r}: could not parse {token!r} "
                    f"as a category code in value {value!r}."
                ) from exc
        return frozenset(codes)


def _already_expanded(values: tuple[object, ...]) -> bool:
    return all(v is None or isinstance(v, (list, tuple, set, frozenset)) for v in values)


def _indicator_column_names(
    question: MultiQuestion, columns: dict[str, tuple[object, ...]]
) -> dict[int, str] | None:
    """If every category of ``question`` has a corresponding
    ``<question.id>_<code>`` column present in ``columns``, return the
    code-to-column-name mapping. Otherwise return ``None`` — either no
    indicator columns exist at all (nothing to expand, the question
    simply has no data yet) or only some do (an inconsistent/partial
    data source this transformer won't guess about).
    """
    names = {category.code: f"{question.id}_{category.code}" for category in question.categories}
    if all(name in columns for name in names.values()):
        return names
    return None


def _merge_indicator_columns(
    question: MultiQuestion,
    indicator_columns: dict[int, str],
    columns: dict[str, tuple[object, ...]],
    row_count: int,
) -> tuple[object, ...]:
    merged: list[object] = []
    for row_index in range(row_count):
        selected: set[int] = set()
        any_present = False
        for code, column_name in indicator_columns.items():
            raw_value = columns[column_name][row_index]
            selected_flag = _parse_indicator_value(question, column_name, row_index, raw_value)
            if selected_flag is not None:
                any_present = True
                if selected_flag:
                    selected.add(code)
        merged.append(frozenset(selected) if any_present else None)
    return tuple(merged)


def _parse_indicator_value(
    question: MultiQuestion, column_name: str, row_index: int, value: object
) -> bool | None:
    if value in _FALSY_INDICATOR_VALUES:
        return None if value is None or value == "" else False
    if value in _TRUTHY_INDICATOR_VALUES:
        return True
    raise TransformationError(
        f"MultiQuestion {question.id!r}: indicator column {column_name!r} has "
        f"an unrecognized value {value!r} in row {row_index}. Expected a "
        f"truthy/falsy indicator (0/1/True/False/empty)."
    )
