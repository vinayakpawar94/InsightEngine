"""Unit tests for insightengine.cleaning.transformer."""

from __future__ import annotations

import pytest

from insightengine.cleaning.transformer import Transformer, TransformerPipeline, to_raw_table
from insightengine.core.codebook import Codebook, NumericQuestion
from insightengine.data.backends.pandas_backend import PandasBackend
from insightengine.data.base import RawTable


class _AddOneTransformer(Transformer):
    def __init__(self, variable: str) -> None:
        self._variable = variable

    def apply(self, table: RawTable, codebook: Codebook) -> RawTable:
        columns = dict(table.columns)
        columns[self._variable] = tuple(
            (v + 1 if v is not None else None) for v in columns[self._variable]
        )
        return RawTable(columns=columns, row_count=table.row_count)


class _RecordingTransformer(Transformer):
    """Records the table it received, to prove ordering in a pipeline."""

    def __init__(self) -> None:
        self.seen: list[tuple[object, ...]] = []

    def apply(self, table: RawTable, codebook: Codebook) -> RawTable:
        self.seen.append(table.columns["AGE"])
        return table


class TestTransformerCannotBeInstantiatedDirectly:
    def test_abstract_base_raises(self) -> None:
        with pytest.raises(TypeError):
            Transformer()  # type: ignore[abstract]


class TestTransformerPipeline:
    def test_empty_pipeline_returns_table_unchanged(self) -> None:
        codebook = Codebook([])
        table = RawTable(columns={"AGE": (25,)}, row_count=1)
        pipeline = TransformerPipeline([])
        result = pipeline.run(table, codebook)
        assert result == table

    def test_single_transformer(self) -> None:
        codebook = Codebook([])
        table = RawTable(columns={"AGE": (25, 30)}, row_count=2)
        pipeline = TransformerPipeline([_AddOneTransformer("AGE")])
        result = pipeline.run(table, codebook)
        assert result.columns["AGE"] == (26, 31)

    def test_transformers_apply_in_order(self) -> None:
        codebook = Codebook([])
        table = RawTable(columns={"AGE": (25,)}, row_count=1)
        recorder = _RecordingTransformer()
        pipeline = TransformerPipeline(
            [_AddOneTransformer("AGE"), recorder, _AddOneTransformer("AGE")]
        )
        result = pipeline.run(table, codebook)
        assert recorder.seen == [(26,)]  # saw the value after the first +1, before the second
        assert result.columns["AGE"] == (27,)

    def test_transformers_property_returns_configured_sequence(self) -> None:
        t1 = _AddOneTransformer("AGE")
        pipeline = TransformerPipeline([t1])
        assert pipeline.transformers == (t1,)


class TestToRawTable:
    def test_extracts_pandas_handle_correctly(self) -> None:
        table = RawTable(columns={"AGE": (25, 30), "GENDER": ("Male", "Female")}, row_count=2)
        handle = PandasBackend().load(table)
        extracted = to_raw_table(handle)
        assert extracted.row_count == 2
        assert extracted.column_names == ("AGE", "GENDER")
        assert extracted.columns["AGE"] == (25, 30)

    def test_round_trip_preserves_none_values(self) -> None:
        table = RawTable(columns={"CITY": ("NYC", None, "LA")}, row_count=3)
        handle = PandasBackend().load(table)
        extracted = to_raw_table(handle)
        assert extracted.columns["CITY"] == ("NYC", None, "LA")


class TestRunAgainstHandle:
    def test_end_to_end_extract_transform_reload(self) -> None:
        codebook = Codebook([NumericQuestion(id="AGE", label="Age")])
        table = RawTable(columns={"AGE": (25, 30)}, row_count=2)
        backend = PandasBackend()
        handle = backend.load(table)

        pipeline = TransformerPipeline([_AddOneTransformer("AGE")])
        result_handle = pipeline.run_against_handle(handle, codebook, backend)

        assert result_handle.column("AGE") == (26, 31)
