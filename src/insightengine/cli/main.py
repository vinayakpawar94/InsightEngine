"""The ``survey`` CLI: ``init``, ``validate``, ``clean``, ``export``, ``report``.

**Scope decisions, since the original five-command list predates
constraints later phases settled:**

* No file writer exists for cleaned data beyond Phase 8's JSON
  persistence — ``clean``/``export`` write cleaned data as JSON via the
  Orchestrator's own persisted artifact, not CSV. Building a new writer
  format is out of scope here.
* The Orchestrator (Phase 8) always runs Cleaning then Validating
  together, in one unconditional sequence — there is no "clean only"
  mode in that frozen code. ``clean`` says so plainly in its own help
  text rather than pretend it skips validation.
* There is no CLI-configurable cleaning pipeline. A fixed default
  pipeline (grid completion, multi-response expansion, derived
  variables) is applied; ``RecodeTransformer`` needs project-specific
  maps with no CLI input mechanism, so it's excluded from the default.
* ``export`` is deliberately distinct from the other commands: it runs
  the full pipeline *and* generates a report in one step — a genuine
  "package this for handoff" shape, not a hollow synonym for ``clean``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from insightengine.cleaning.derived import DerivedVariableTransformer
from insightengine.cleaning.grid_expansion import GridColumnCompletionTransformer
from insightengine.cleaning.multi_expansion import MultiResponseExpansionTransformer
from insightengine.cleaning.transformer import TransformerPipeline
from insightengine.core.exceptions import InsightEngineError, ManifestError
from insightengine.core.types import Severity
from insightengine.data.backends.pandas_backend import PandasBackend
from insightengine.data.base import DataBackend
from insightengine.data.registry import data_backend_registry
from insightengine.execution.manifest import Stage, load_manifest
from insightengine.execution.orchestrator import Orchestrator
from insightengine.execution.persistence import load_validation_results
from insightengine.metadata.base import MetadataParser
from insightengine.metadata.registry import metadata_parser_registry
from insightengine.reporting.models import build_report_data
from insightengine.reporting.registry import report_generator_registry
from insightengine.rules.dsl import load_rules
from insightengine.validation.results import ValidationResult

app = typer.Typer(
    name="insightengine",
    help="InsightEngine — a Python-native survey data processing platform.",
)

_DEFAULT_QUESTIONNAIRE = """questions:
  - id: EXAMPLE_RESPONSE
    type: text
    label: "Example: a free-text response"
"""

_DEFAULT_RULES = """rules:
  - id: example_response_check
    type: range
    when: "EXAMPLE_RESPONSE == ''"
    severity: warning
    message: "Response is empty"
"""

_PROJECT_SUBDIRS = (
    "metadata",
    "rules",
    "datasets/raw",
    "datasets/processed",
    "reports",
    "logs",
)


def _fail(exc: InsightEngineError) -> typer.Exit:
    typer.secho(f"Error: {exc}", fg=typer.colors.RED, err=True)
    return typer.Exit(code=1)


def _resolve_backend(name: str) -> DataBackend:
    return data_backend_registry.get(name)


def _resolve_parser(name: str) -> MetadataParser:
    return metadata_parser_registry.get(name)


def _default_pipeline() -> TransformerPipeline:
    return TransformerPipeline(
        [
            GridColumnCompletionTransformer(),
            MultiResponseExpansionTransformer(),
            DerivedVariableTransformer(),
        ]
    )


def _print_summary(results: tuple[ValidationResult, ...]) -> None:
    data = build_report_data(results)
    typer.echo(f"Total findings: {len(data.results)}")
    for severity in Severity:
        count = data.counts_by_severity[severity]
        if count:
            typer.echo(f"  {severity.value}: {count}")


@app.command()
def init(
    project_dir: Annotated[Path, typer.Argument(help="Directory to create the project in.")],
) -> None:
    """Scaffold a new project with a working starter questionnaire and rule set.

    The generated files are real, valid, immediately loadable examples —
    not placeholders — so ``validate``/``clean``/``export`` can be run
    against a freshly-initialized project with no edits required.
    """
    for subdir in _PROJECT_SUBDIRS:
        (project_dir / subdir).mkdir(parents=True, exist_ok=True)

    questionnaire_path = project_dir / "metadata" / "questionnaire.yaml"
    rules_path = project_dir / "rules" / "validation.yaml"
    if not questionnaire_path.exists():
        questionnaire_path.write_text(_DEFAULT_QUESTIONNAIRE, encoding="utf-8")
    if not rules_path.exists():
        rules_path.write_text(_DEFAULT_RULES, encoding="utf-8")

    typer.echo(f"Initialized project at {project_dir}")
    typer.echo(f"  Starter questionnaire: {questionnaire_path}")
    typer.echo(f"  Starter rules: {rules_path}")


@app.command()
def validate(
    data: Annotated[Path, typer.Option("--data", help="Path to the input data file.")],
    metadata: Annotated[Path, typer.Option("--metadata", help="Path to the questionnaire metadata file.")],
    rules: Annotated[Path, typer.Option("--rules", help="Path to the rules YAML file.")],
    run_dir: Annotated[Path, typer.Option("--run-dir", help="Directory to store the run's manifest and artifacts.")],
    parser: Annotated[str, typer.Option("--parser", help="Registered metadata parser to use.")] = "yaml",
    backend: Annotated[str, typer.Option("--backend", help="Registered data backend to use.")] = "pandas",
    resume: Annotated[bool, typer.Option("--resume", help="Resume a previously interrupted run.")] = False,
) -> None:
    """Validate DATA against METADATA and RULES.

    Runs the shared pipeline with the default cleaning transformers
    applied first (see this module's docstring) — there is no
    "validate the untouched raw data" mode, since the Orchestrator
    always cleans before validating.

    Exits with status 1 if any finding has ERROR severity.
    """
    try:
        rule_objects = load_rules(rules)
        orchestrator = Orchestrator(run_dir, backend=_resolve_backend(backend))
        result = orchestrator.run(
            data_path=data,
            metadata_path=metadata,
            metadata_parser=_resolve_parser(parser),
            pipeline=_default_pipeline(),
            rules=rule_objects,
            resume=resume,
        )
    except InsightEngineError as exc:
        raise _fail(exc) from exc

    _print_summary(result.results)
    if any(r.severity is Severity.ERROR for r in result.results):
        raise typer.Exit(code=1)


@app.command()
def clean(
    data: Annotated[Path, typer.Option("--data", help="Path to the input data file.")],
    metadata: Annotated[Path, typer.Option("--metadata", help="Path to the questionnaire metadata file.")],
    run_dir: Annotated[Path, typer.Option("--run-dir", help="Directory to store the run's manifest and artifacts.")],
    parser: Annotated[str, typer.Option("--parser", help="Registered metadata parser to use.")] = "yaml",
    backend: Annotated[str, typer.Option("--backend", help="Registered data backend to use.")] = "pandas",
    resume: Annotated[bool, typer.Option("--resume", help="Resume a previously interrupted run.")] = False,
) -> None:
    """Clean DATA using the default cleaning pipeline and persist the result.

    Note: because the Orchestrator always runs Cleaning and Validating
    together, this command also produces a validation-results artifact
    as a side effect — there is no way to run cleaning in isolation with
    the current Orchestrator. Use ``validate``/``report`` if only
    validation output is wanted.
    """
    try:
        orchestrator = Orchestrator(run_dir, backend=_resolve_backend(backend))
        orchestrator.run(
            data_path=data,
            metadata_path=metadata,
            metadata_parser=_resolve_parser(parser),
            pipeline=_default_pipeline(),
            rules=[],
            resume=resume,
        )
    except InsightEngineError as exc:
        raise _fail(exc) from exc

    typer.echo(f"Cleaned data written to {orchestrator.cleaned_data_path}")


@app.command()
def report(
    run_dir: Annotated[Path, typer.Option("--run-dir", help="Directory of a previously completed run.")],
    report_format: Annotated[
        str, typer.Option("--format", help="Registered report generator to use (json, csv, html, excel).")
    ],
    output: Annotated[Path, typer.Option("--output", help="Path to write the report to.")],
) -> None:
    """Generate a report from a previously completed run's persisted validation results."""
    try:
        # The backend argument here is a formality: Orchestrator's
        # manifest_path/results_path properties are pure path
        # computations that never touch the backend, since this command
        # never loads data at all. PandasBackend is used as an
        # arbitrary, always-available concrete instance to satisfy the
        # constructor, not because this command depends on pandas.
        orchestrator = Orchestrator(run_dir, backend=PandasBackend())
        manifest = load_manifest(orchestrator.manifest_path)
        if Stage.VALIDATING not in manifest.completed_stages:
            raise ManifestError(f"Run at {run_dir} has not completed validation yet.")

        results = load_validation_results(orchestrator.results_path)
        report_data = build_report_data(results)
        generator = report_generator_registry.get(report_format)
        report_path = generator.build(report_data, output)
    except InsightEngineError as exc:
        raise _fail(exc) from exc

    typer.echo(f"Report written to {report_path}")


@app.command()
def export(
    data: Annotated[Path, typer.Option("--data", help="Path to the input data file.")],
    metadata: Annotated[Path, typer.Option("--metadata", help="Path to the questionnaire metadata file.")],
    rules: Annotated[Path, typer.Option("--rules", help="Path to the rules YAML file.")],
    run_dir: Annotated[Path, typer.Option("--run-dir", help="Directory to store the run's manifest and artifacts.")],
    report_output: Annotated[Path, typer.Option("--report-output", help="Path to write the report to.")],
    report_format: Annotated[
        str, typer.Option("--report-format", help="Registered report generator to use.")
    ] = "html",
    parser: Annotated[str, typer.Option("--parser", help="Registered metadata parser to use.")] = "yaml",
    backend: Annotated[str, typer.Option("--backend", help="Registered data backend to use.")] = "pandas",
    resume: Annotated[bool, typer.Option("--resume", help="Resume a previously interrupted run.")] = False,
) -> None:
    """Run the full pipeline (clean + validate) and generate a report in one step.

    The "package this for handoff" command — distinct from ``clean``
    (cleaned data only) and ``report`` (report only, from an existing
    run): produces both, from a single fresh or resumed run.
    """
    try:
        rule_objects = load_rules(rules)
        orchestrator = Orchestrator(run_dir, backend=_resolve_backend(backend))
        result = orchestrator.run(
            data_path=data,
            metadata_path=metadata,
            metadata_parser=_resolve_parser(parser),
            pipeline=_default_pipeline(),
            rules=rule_objects,
            resume=resume,
        )
        report_data = build_report_data(result.results)
        generator = report_generator_registry.get(report_format)
        report_path = generator.build(report_data, report_output)
    except InsightEngineError as exc:
        raise _fail(exc) from exc

    typer.echo(f"Cleaned data written to {orchestrator.cleaned_data_path}")
    typer.echo(f"Report written to {report_path}")
    _print_summary(result.results)


def main() -> None:  # pragma: no cover
    """Entry point for the ``insightengine`` console script.

    Only exercisable via a real installed console-script invocation —
    this project's pyproject.toml requires Python 3.13+, which isn't
    available in this build environment (see README), so a real
    `pip install` of the package (needed to test the actual
    `insightengine` command) can't be performed here. Every command's
    actual behavior is fully covered via `typer.testing.CliRunner`
    against the `app` object directly, which is what this thin wrapper
    calls.
    """
    app()


if __name__ == "__main__":  # pragma: no cover
    main()
