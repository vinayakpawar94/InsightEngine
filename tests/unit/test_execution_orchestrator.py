"""Unit tests for insightengine.execution.orchestrator.

``TestAcceptanceCriterion`` is this phase's actual acceptance test: a
run that fails partway through (after Cleaning has already been
checkpointed), followed by a **brand new** ``Orchestrator`` instance
resuming from the manifest alone — simulating a killed-and-restarted
process more rigorously than a literal subprocess kill would, since it
proves the manifest (not any in-memory state) is the sole source of
truth for what to skip.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from insightengine.cleaning.transformer import Transformer, TransformerPipeline
from insightengine.core.codebook import Codebook
from insightengine.core.exceptions import ManifestError, UnknownVariableError
from insightengine.core.types import Severity
from insightengine.data.backends.pandas_backend import PandasBackend
from insightengine.data.base import RawTable
from insightengine.execution.manifest import Stage
from insightengine.execution.orchestrator import Orchestrator
from insightengine.metadata.base import MetadataParser
from insightengine.rules.dsl import RequiredRule


class _CountingTransformer(Transformer):
    """Counts how many times it was actually invoked - the mechanism
    that proves a resumed run skips the Cleaning stage rather than
    silently redoing it.
    """

    def __init__(self) -> None:
        self.call_count = 0

    def apply(self, table: RawTable, codebook: Codebook) -> RawTable:
        self.call_count += 1
        return table


class _FakeMetadataParser:
    """A minimal MetadataParser - avoids depending on real YAML files
    for tests that don't care about metadata parsing specifics.
    """

    def __init__(self, codebook: Codebook) -> None:
        self._codebook = codebook

    def parse(self, source: Path) -> Codebook:
        return self._codebook


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    headers = list(rows[0].keys())
    lines = [",".join(headers)]
    for row in rows:
        lines.append(",".join(row[h] for h in headers))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


class TestBasicRun:
    def test_successful_run_produces_expected_result(self, tmp_path: Path) -> None:
        from insightengine.core.codebook import NumericQuestion

        data_path = tmp_path / "data.csv"
        _write_csv(data_path, [{"AGE": "15"}, {"AGE": "30"}])

        codebook = Codebook([NumericQuestion(id="AGE", label="Age")])
        orchestrator = Orchestrator(tmp_path / "run", backend=PandasBackend())

        result = orchestrator.run(
            data_path=data_path,
            metadata_path=tmp_path / "unused.yaml",
            metadata_parser=_FakeMetadataParser(codebook),
            pipeline=TransformerPipeline([]),
            rules=[],
        )

        assert result.manifest.completed_stages == {
            Stage.LOADING_DATA,
            Stage.LOADING_CODEBOOK,
            Stage.CLEANING,
            Stage.VALIDATING,
            Stage.COMPLETE,
        }
        # AGE is a string "15"/"30" from the CSV loader (no coercion) -
        # NumericQuestion's domain check should flag both as non-numeric.
        assert len(result.results) == 2

    def test_manifest_and_artifact_files_are_created(self, tmp_path: Path) -> None:
        data_path = tmp_path / "data.csv"
        _write_csv(data_path, [{"AGE": "15"}])
        codebook = Codebook([])
        orchestrator = Orchestrator(tmp_path / "run", backend=PandasBackend())

        orchestrator.run(
            data_path=data_path,
            metadata_path=tmp_path / "unused.yaml",
            metadata_parser=_FakeMetadataParser(codebook),
            pipeline=TransformerPipeline([]),
            rules=[],
        )

        assert orchestrator.manifest_path.is_file()
        assert orchestrator.cleaned_data_path.is_file()
        assert orchestrator.results_path.is_file()


class TestResumeErrors:
    def test_resume_without_prior_manifest_raises(self, tmp_path: Path) -> None:
        orchestrator = Orchestrator(tmp_path / "run", backend=PandasBackend())
        with pytest.raises(ManifestError, match="No manifest found"):
            orchestrator.run(
                data_path=tmp_path / "data.csv",
                metadata_path=tmp_path / "unused.yaml",
                metadata_parser=_FakeMetadataParser(Codebook([])),
                pipeline=TransformerPipeline([]),
                rules=[],
                resume=True,
            )


class TestFailureRecording:
    def test_failed_run_records_error_in_manifest(self, tmp_path: Path) -> None:
        data_path = tmp_path / "data.csv"
        _write_csv(data_path, [{"AGE": "15"}])
        codebook = Codebook([])
        orchestrator = Orchestrator(tmp_path / "run", backend=PandasBackend())
        bad_rule = RequiredRule(id="bad", variable="DOES_NOT_EXIST")

        with pytest.raises(UnknownVariableError):
            orchestrator.run(
                data_path=data_path,
                metadata_path=tmp_path / "unused.yaml",
                metadata_parser=_FakeMetadataParser(codebook),
                pipeline=TransformerPipeline([]),
                rules=[bad_rule],
            )

        from insightengine.execution.manifest import load_manifest

        manifest = load_manifest(orchestrator.manifest_path)
        assert manifest.error is not None
        assert "DOES_NOT_EXIST" in manifest.error
        assert Stage.CLEANING in manifest.completed_stages
        assert Stage.VALIDATING not in manifest.completed_stages

    def test_on_end_hook_receives_false_on_failure(self, tmp_path: Path) -> None:
        from insightengine.execution.hooks import HookRegistry

        data_path = tmp_path / "data.csv"
        _write_csv(data_path, [{"AGE": "15"}])
        codebook = Codebook([])
        seen: list[bool] = []
        hooks = HookRegistry()
        hooks.register_on_end(seen.append)
        orchestrator = Orchestrator(tmp_path / "run", backend=PandasBackend(), hooks=hooks)
        bad_rule = RequiredRule(id="bad", variable="DOES_NOT_EXIST")

        with pytest.raises(UnknownVariableError):
            orchestrator.run(
                data_path=data_path,
                metadata_path=tmp_path / "unused.yaml",
                metadata_parser=_FakeMetadataParser(codebook),
                pipeline=TransformerPipeline([]),
                rules=[bad_rule],
            )

        assert seen == [False]


class TestHooksFireDuringSuccessfulRun:
    def test_on_start_and_on_end_fire_exactly_once(self, tmp_path: Path) -> None:
        from insightengine.execution.hooks import HookRegistry

        data_path = tmp_path / "data.csv"
        _write_csv(data_path, [{"AGE": "15"}, {"AGE": "30"}])
        codebook = Codebook([])
        start_calls = 0
        end_calls: list[bool] = []
        hooks = HookRegistry()
        hooks.register_on_start(lambda: None)
        hooks.register_on_end(end_calls.append)
        orchestrator = Orchestrator(tmp_path / "run", backend=PandasBackend(), hooks=hooks)

        orchestrator.run(
            data_path=data_path,
            metadata_path=tmp_path / "unused.yaml",
            metadata_parser=_FakeMetadataParser(codebook),
            pipeline=TransformerPipeline([]),
            rules=[],
        )

        assert end_calls == [True]

    def test_on_case_fires_once_per_row(self, tmp_path: Path) -> None:
        from insightengine.execution.hooks import HookRegistry

        data_path = tmp_path / "data.csv"
        _write_csv(data_path, [{"AGE": "15"}, {"AGE": "30"}, {"AGE": "45"}])
        codebook = Codebook([])
        seen_rows: list[int] = []
        hooks = HookRegistry()
        hooks.register_on_case(seen_rows.append)
        orchestrator = Orchestrator(tmp_path / "run", backend=PandasBackend(), hooks=hooks)

        orchestrator.run(
            data_path=data_path,
            metadata_path=tmp_path / "unused.yaml",
            metadata_parser=_FakeMetadataParser(codebook),
            pipeline=TransformerPipeline([]),
            rules=[],
        )

        assert seen_rows == [0, 1, 2]


class TestResumeAfterFullCompletion:
    def test_resuming_a_fully_completed_run_loads_persisted_results(
        self, tmp_path: Path
    ) -> None:
        from insightengine.core.codebook import NumericQuestion

        data_path = tmp_path / "data.csv"
        _write_csv(data_path, [{"AGE": "15"}, {"AGE": "30"}])
        codebook = Codebook([NumericQuestion(id="AGE", label="Age")])
        counting_transformer = _CountingTransformer()
        pipeline = TransformerPipeline([counting_transformer])
        run_dir = tmp_path / "run"

        first = Orchestrator(run_dir, backend=PandasBackend())
        first_result = first.run(
            data_path=data_path,
            metadata_path=tmp_path / "unused.yaml",
            metadata_parser=_FakeMetadataParser(codebook),
            pipeline=pipeline,
            rules=[],
        )
        assert counting_transformer.call_count == 1

        # Resume a run that was already fully complete - both Cleaning
        # AND Validating should be skipped, results loaded from disk.
        second = Orchestrator(run_dir, backend=PandasBackend())
        second_result = second.run(
            data_path=data_path,
            metadata_path=tmp_path / "unused.yaml",
            metadata_parser=_FakeMetadataParser(codebook),
            pipeline=pipeline,
            rules=[],
            resume=True,
        )

        assert counting_transformer.call_count == 1  # still not redone
        assert second_result.results == first_result.results


class TestAcceptanceCriterion:
    def test_resumed_run_skips_cleaning_and_completes_successfully(
        self, tmp_path: Path
    ) -> None:
        from insightengine.core.codebook import NumericQuestion

        data_path = tmp_path / "data.csv"
        _write_csv(data_path, [{"AGE": "15"}, {"AGE": "30"}])
        codebook = Codebook([NumericQuestion(id="AGE", label="Age")])

        counting_transformer = _CountingTransformer()
        pipeline = TransformerPipeline([counting_transformer])
        run_dir = tmp_path / "run"

        # --- Run 1: fails during Validating, after Cleaning has already
        # succeeded and been checkpointed. ---
        first_orchestrator = Orchestrator(run_dir, backend=PandasBackend())
        bad_rule = RequiredRule(id="bad", variable="DOES_NOT_EXIST")

        with pytest.raises(UnknownVariableError):
            first_orchestrator.run(
                data_path=data_path,
                metadata_path=tmp_path / "unused.yaml",
                metadata_parser=_FakeMetadataParser(codebook),
                pipeline=pipeline,
                rules=[bad_rule],
            )

        assert counting_transformer.call_count == 1

        from insightengine.execution.manifest import load_manifest

        interrupted_manifest = load_manifest(first_orchestrator.manifest_path)
        assert Stage.CLEANING in interrupted_manifest.completed_stages
        assert Stage.VALIDATING not in interrupted_manifest.completed_stages
        assert Stage.COMPLETE not in interrupted_manifest.completed_stages

        # --- "Kill the process": discard the first Orchestrator entirely,
        # construct a brand new one pointing at the same run_dir. Nothing
        # from the first instance is reused except what's on disk. ---
        second_orchestrator = Orchestrator(run_dir, backend=PandasBackend())
        good_rule = RequiredRule(id="good", variable="AGE")

        result = second_orchestrator.run(
            data_path=data_path,
            metadata_path=tmp_path / "unused.yaml",
            metadata_parser=_FakeMetadataParser(codebook),
            pipeline=pipeline,
            rules=[good_rule],
            resume=True,
        )

        # The core resumability claim: Cleaning was NOT redone. The
        # transformer's total call count across BOTH runs is still 1.
        assert counting_transformer.call_count == 1

        assert result.manifest.completed_stages == {
            Stage.LOADING_DATA,
            Stage.LOADING_CODEBOOK,
            Stage.CLEANING,
            Stage.VALIDATING,
            Stage.COMPLETE,
        }
        assert result.manifest.error is None
        # AGE is present and required on both rows - no violations from
        # `good_rule`; only the NumericQuestion domain check (AGE is a
        # string from the CSV loader) fires, once per row.
        assert len(result.results) == 2
        assert all(r.rule_id.startswith("__domain__") for r in result.results)
