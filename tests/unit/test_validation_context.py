"""Unit tests for insightengine.validation.context."""

from __future__ import annotations

from insightengine.core.codebook import Codebook, NumericQuestion
from insightengine.data.backends.pandas_backend import PandasBackend
from insightengine.data.base import RawTable
from insightengine.validation.context import ValidationContext


class TestValidationContext:
    def test_construction(self) -> None:
        codebook = Codebook([NumericQuestion(id="AGE", label="Age")])
        table = RawTable(columns={"AGE": (25, 30)}, row_count=2)
        data = PandasBackend().load(table)

        context = ValidationContext(codebook=codebook, data=data)
        assert context.codebook is codebook
        assert context.data is data

    def test_does_not_require_every_question_to_have_a_column(self) -> None:
        # A DerivedVariable legitimately has no data column yet - this
        # must not raise at construction time.
        from insightengine.core.codebook import DerivedVariable

        codebook = Codebook(
            [
                NumericQuestion(id="AGE", label="Age"),
                DerivedVariable(
                    id="AGE_BAND", label="Age band", expression="f(AGE)", depends_on=("AGE",)
                ),
            ]
        )
        table = RawTable(columns={"AGE": (25,)}, row_count=1)
        data = PandasBackend().load(table)

        context = ValidationContext(codebook=codebook, data=data)
        assert "AGE_BAND" not in context.data.column_names
