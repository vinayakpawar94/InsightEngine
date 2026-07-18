"""Computing :class:`~insightengine.core.codebook.DerivedVariable` values.

**Circular-dependency detection is not this module's job.**
:class:`~insightengine.core.codebook.Codebook` (Phase 2) already raises
:class:`~insightengine.core.exceptions.CircularDependencyError` at
construction time — before a ``Codebook`` object exists at all, let
alone reaches this transformer. This module's only responsibility is
correctly *consuming* the already-validated topological order that
:meth:`~insightengine.core.codebook.Codebook.derived_variables` provides,
computing each derived variable's values via the same restricted
expression evaluator the Rule Engine uses (Phase 5), and making each
computed column available to any later derived variable that depends on it.
"""

from __future__ import annotations

from insightengine.cleaning.transformer import Transformer
from insightengine.core.codebook import Codebook
from insightengine.core.exceptions import TransformationError, UnknownVariableError
from insightengine.data.base import RawTable
from insightengine.rules.evaluator import compile_expression


class DerivedVariableTransformer(Transformer):
    """Computes every derived variable in the codebook, in dependency order."""

    def apply(self, table: RawTable, codebook: Codebook) -> RawTable:
        columns: dict[str, tuple[object, ...]] = dict(table.columns)

        for variable in codebook.derived_variables():
            compiled = compile_expression(variable.expression)
            computed: list[object] = []
            for row_index in range(table.row_count):
                row_variables = {name: values[row_index] for name, values in columns.items()}
                try:
                    computed.append(compiled.evaluate(row_variables))
                except UnknownVariableError as exc:
                    raise TransformationError(
                        f"DerivedVariable {variable.id!r} at row {row_index}: {exc}"
                    ) from exc
            columns[variable.id] = tuple(computed)

        return RawTable(columns=columns, row_count=table.row_count)
