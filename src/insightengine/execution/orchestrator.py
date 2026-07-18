"""The Orchestrator: runs Data Engine -> Cleaning Engine -> Validation
Execution end-to-end, checkpointing progress to a manifest so a run can
be resumed without redoing expensive work.

**Stage cost model, and why some stages are always redone while others
are genuinely skipped:** loading the raw input file and re-parsing the
codebook are cheap and always safe to redo — they're re-executed on
every call to :meth:`Orchestrator.run`, resumed or not, but only
recorded in the manifest once. Cleaning and validation are the stages
actually worth skipping: on a resumed run, if the manifest shows them
already complete, their *persisted results* (see
:mod:`insightengine.execution.persistence`) are loaded from disk instead
of recomputing anything.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from insightengine.core.codebook import Codebook
from insightengine.data.base import DataBackend, RawTable
from insightengine.data.loader import load_file
from insightengine.cleaning.transformer import TransformerPipeline, to_raw_table
from insightengine.execution.hooks import HookRegistry
from insightengine.execution.manifest import (
    Manifest,
    Stage,
    load_manifest,
    new_manifest,
    save_manifest,
)
from insightengine.execution.persistence import (
    load_raw_table,
    load_validation_results,
    save_raw_table,
    save_validation_results,
)
from insightengine.metadata.base import MetadataParser
from insightengine.rules.dsl import Rule
from insightengine.validation.context import ValidationContext
from insightengine.validation.executor import validate
from insightengine.validation.results import ValidationResult


@dataclass(frozen=True, slots=True)
class OrchestratorResult:
    """Everything produced by one completed :meth:`Orchestrator.run` call."""

    manifest: Manifest
    codebook: Codebook
    cleaned_table: RawTable
    results: tuple[ValidationResult, ...]


class Orchestrator:
    """Runs one survey project's data through the full pipeline.

    Args:
        run_dir: Where this run's manifest and persisted artifacts live.
            One directory per run — running two different datasets
            through the same ``run_dir`` will confuse resumability, since
            the manifest has no way to know the inputs changed.
        backend: The :class:`~insightengine.data.base.DataBackend` used
            both to load the original input and to reload cleaned data
            before validation.
        hooks: Optional :class:`~insightengine.execution.hooks.HookRegistry`.
            A fresh, empty one is created if omitted.
    """

    def __init__(
        self, run_dir: Path, *, backend: DataBackend, hooks: HookRegistry | None = None
    ) -> None:
        self._run_dir = run_dir
        self._backend = backend
        self._hooks = hooks if hooks is not None else HookRegistry()

    @property
    def manifest_path(self) -> Path:
        return self._run_dir / "manifest.json"

    @property
    def cleaned_data_path(self) -> Path:
        return self._run_dir / "cleaned_data.json"

    @property
    def results_path(self) -> Path:
        return self._run_dir / "validation_results.json"

    def run(
        self,
        *,
        data_path: Path,
        metadata_path: Path,
        metadata_parser: MetadataParser,
        pipeline: TransformerPipeline,
        rules: Sequence[Rule],
        resume: bool = False,
    ) -> OrchestratorResult:
        """Run the full pipeline, or resume a previously interrupted one.

        Raises:
            ManifestError: If ``resume=True`` but no manifest exists at
                ``run_dir``, or an existing manifest is malformed.
            (Any exception a stage itself can raise also propagates,
            after being recorded — unaltered — in the manifest's
            ``error`` field. This method does not wrap or reclassify
            failures; it only records that one happened.)
        """
        manifest = self._start_or_resume_manifest(resume)
        already_completed = manifest.completed_stages
        self._hooks.fire_on_start()

        try:
            data_handle = load_file(data_path, self._backend)
            raw_table = to_raw_table(data_handle)
            if Stage.LOADING_DATA not in already_completed:
                manifest = manifest.with_completed_stage(Stage.LOADING_DATA)
                save_manifest(manifest, self.manifest_path)

            codebook = metadata_parser.parse(metadata_path)
            if Stage.LOADING_CODEBOOK not in already_completed:
                manifest = manifest.with_completed_stage(Stage.LOADING_CODEBOOK)
                save_manifest(manifest, self.manifest_path)

            if Stage.CLEANING in already_completed:
                cleaned_table = load_raw_table(self.cleaned_data_path)
            else:
                cleaned_table = pipeline.run(raw_table, codebook)
                save_raw_table(cleaned_table, self.cleaned_data_path)
                manifest = manifest.with_completed_stage(
                    Stage.CLEANING, artifact=self.cleaned_data_path.name
                )
                save_manifest(manifest, self.manifest_path)

            for row_index in range(cleaned_table.row_count):
                self._hooks.fire_on_case(row_index)

            if Stage.VALIDATING in already_completed:
                results = load_validation_results(self.results_path)
            else:
                cleaned_handle = self._backend.load(cleaned_table)
                context = ValidationContext(codebook=codebook, data=cleaned_handle)
                collector = validate(context, rules)
                results = collector.results
                save_validation_results(results, self.results_path)
                manifest = manifest.with_completed_stage(
                    Stage.VALIDATING, artifact=self.results_path.name
                )
                save_manifest(manifest, self.manifest_path)

            if Stage.COMPLETE not in already_completed:
                manifest = manifest.with_completed_stage(Stage.COMPLETE)
                save_manifest(manifest, self.manifest_path)

        except Exception as exc:
            save_manifest(manifest.with_error(str(exc)), self.manifest_path)
            self._hooks.fire_on_end(succeeded=False)
            raise

        self._hooks.fire_on_end(succeeded=True)
        return OrchestratorResult(
            manifest=manifest, codebook=codebook, cleaned_table=cleaned_table, results=results
        )

    def _start_or_resume_manifest(self, resume: bool) -> Manifest:
        if resume:
            return load_manifest(self.manifest_path)
        manifest = new_manifest()
        save_manifest(manifest, self.manifest_path)
        return manifest
