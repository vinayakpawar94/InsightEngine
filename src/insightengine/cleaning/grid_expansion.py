"""Grid row column completion.

Unlike the legacy Dimensions workflow this project studied (where a
grid's structure had to be *reconstructed* from variable-naming
conventions — the fragile ``crGrid`` pattern found in the real
production script reviewed earlier in this project), a
:class:`~insightengine.core.codebook.GridQuestion`'s rows are already
individually declared, addressable questions from the moment a codebook
is authored (Phase 2/4) — there is no structure to *discover* here.

What this transformer actually does: if a declared grid row has no
corresponding column in the data at all, add one filled with ``None``
for every row. This isn't invented busywork — without it, Phase 6's
validation silently skips a grid row's domain/required checks entirely
whenever its column is simply absent (a deliberate Phase 6 design
choice, since an absent column there was assumed to mean "not computed
yet," not "genuinely missing"). Completing the column here means a grid
row that's truly missing from a dataset gets a real, visible
"required but missing" finding in Phase 6, instead of silently vanishing
from validation.
"""

from __future__ import annotations

from insightengine.core.codebook import Codebook, GridQuestion
from insightengine.data.base import RawTable
from insightengine.cleaning.transformer import Transformer


class GridColumnCompletionTransformer(Transformer):
    """Adds an all-``None`` column for any declared grid row missing
    from the data entirely.
    """

    def apply(self, table: RawTable, codebook: Codebook) -> RawTable:
        columns = dict(table.columns)
        added_any = False

        for question in codebook.questions:
            if not isinstance(question, GridQuestion):
                continue
            for row in question.rows:
                if row.id not in columns:
                    columns[row.id] = (None,) * table.row_count
                    added_any = True

        if not added_any:
            return table
        return RawTable(columns=columns, row_count=table.row_count)
