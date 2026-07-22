"""Unit tests for insightengine.cli.main.

Uses ``typer.testing.CliRunner`` to invoke the actual CLI app object —
not the underlying Python functions directly — so these tests exercise
real argument parsing, exit codes, and stdout/stderr, the same way a
real invocation of the console script would.

``TestAcceptanceCriterion`` is the phase's actual acceptance test: each
of the five commands run end-to-end against a fixture project.
"""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from insightengine.cli.main import app

runner = CliRunner()


def _write_fixture_project(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Writes a small, real, valid fixture project - a data file, a
    native YAML questionnaire, and a rules file - returning their paths.

    Deliberately uses a text field, not a numeric one: CSV-sourced data
    is never type-coerced (a Phase 3 decision — every CSV value is a
    plain string), and there is no coercion step anywhere in the built
    pipeline. A NumericQuestion against CSV string data will always
    surface a domain-check error (the value "isn't numeric"), and a
    numeric-comparison rule against it will always raise
    RuleEvaluationError — neither is a CLI bug, but neither is
    achievable "success" either. A text field with a string-comparison
    rule sidesteps that gap entirely, and is what an honestly-designed
    "does the CLI mechanism work" fixture actually needs.
    """
    data_path = tmp_path / "data.csv"
    data_path.write_text("RESPONSE\nYes\nNo\nMaybe\n", encoding="utf-8")

    metadata_path = tmp_path / "questionnaire.yaml"
    metadata_path.write_text(
        """
questions:
  - id: RESPONSE
    type: text
    label: "Response"
""",
        encoding="utf-8",
    )

    rules_path = tmp_path / "rules.yaml"
    rules_path.write_text(
        """
rules:
  - id: response_maybe
    type: range
    when: "RESPONSE == 'Maybe'"
    severity: warning
    message: "Response was Maybe, follow up"
""",
        encoding="utf-8",
    )

    return data_path, metadata_path, rules_path


def _write_error_triggering_fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    """A fixture deliberately using a NumericQuestion against CSV string
    data, to reliably trigger an ERROR-severity domain-check finding —
    for tests that specifically want to confirm error-exit-code behavior,
    as distinct from tests confirming the CLI's basic mechanics work.
    """
    data_path = tmp_path / "data.csv"
    data_path.write_text("AGE\n15\n30\n150\n", encoding="utf-8")

    metadata_path = tmp_path / "questionnaire.yaml"
    metadata_path.write_text(
        """
questions:
  - id: AGE
    type: numeric
    label: "Age"
""",
        encoding="utf-8",
    )

    rules_path = tmp_path / "rules.yaml"
    rules_path.write_text("rules: []\n", encoding="utf-8")

    return data_path, metadata_path, rules_path


class TestInitCommand:
    def test_creates_expected_directory_structure(self, tmp_path: Path) -> None:
        project_dir = tmp_path / "myproject"
        result = runner.invoke(app, ["init", str(project_dir)])

        assert result.exit_code == 0
        for subdir in ("metadata", "rules", "datasets/raw", "datasets/processed", "reports", "logs"):
            assert (project_dir / subdir).is_dir()

    def test_starter_files_are_real_and_loadable(self, tmp_path: Path) -> None:
        project_dir = tmp_path / "myproject"
        runner.invoke(app, ["init", str(project_dir)])

        from insightengine.metadata.parsers.yaml_native import load
        from insightengine.rules.dsl import load_rules

        codebook = load(project_dir / "metadata" / "questionnaire.yaml")
        assert len(codebook) > 0

        rules = load_rules(project_dir / "rules" / "validation.yaml")
        assert len(rules) > 0

    def test_running_init_twice_does_not_overwrite_edited_files(self, tmp_path: Path) -> None:
        project_dir = tmp_path / "myproject"
        runner.invoke(app, ["init", str(project_dir)])

        questionnaire_path = project_dir / "metadata" / "questionnaire.yaml"
        questionnaire_path.write_text("questions: []\n", encoding="utf-8")

        runner.invoke(app, ["init", str(project_dir)])
        assert questionnaire_path.read_text(encoding="utf-8") == "questions: []\n"


class TestValidateCommand:
    def test_successful_validation_exits_zero_and_prints_summary(self, tmp_path: Path) -> None:
        data_path, metadata_path, rules_path = _write_fixture_project(tmp_path)
        result = runner.invoke(
            app,
            [
                "validate",
                "--data", str(data_path),
                "--metadata", str(metadata_path),
                "--rules", str(rules_path),
                "--run-dir", str(tmp_path / "run"),
            ],
        )
        assert result.exit_code == 0
        assert "Total findings" in result.stdout

    def test_error_severity_finding_causes_nonzero_exit(self, tmp_path: Path) -> None:
        # Uses the dedicated error-triggering fixture (NumericQuestion
        # against CSV string data), which reliably produces an
        # ERROR-severity domain-check finding.
        data_path, metadata_path, rules_path = _write_error_triggering_fixture(tmp_path)
        result = runner.invoke(
            app,
            [
                "validate",
                "--data", str(data_path),
                "--metadata", str(metadata_path),
                "--rules", str(rules_path),
                "--run-dir", str(tmp_path / "run"),
            ],
        )
        assert result.exit_code == 1

    def test_missing_data_file_produces_clean_error_not_a_traceback(self, tmp_path: Path) -> None:
        _, metadata_path, rules_path = _write_fixture_project(tmp_path)
        result = runner.invoke(
            app,
            [
                "validate",
                "--data", str(tmp_path / "does_not_exist.csv"),
                "--metadata", str(metadata_path),
                "--rules", str(rules_path),
                "--run-dir", str(tmp_path / "run"),
            ],
        )
        assert result.exit_code == 1
        assert "Error:" in result.output
        assert "Traceback" not in result.output

    def test_unknown_backend_name_fails_cleanly(self, tmp_path: Path) -> None:
        data_path, metadata_path, rules_path = _write_fixture_project(tmp_path)
        result = runner.invoke(
            app,
            [
                "validate",
                "--data", str(data_path),
                "--metadata", str(metadata_path),
                "--rules", str(rules_path),
                "--run-dir", str(tmp_path / "run"),
                "--backend", "does-not-exist",
            ],
        )
        assert result.exit_code != 0


class TestCleanCommand:
    def test_writes_cleaned_data_and_reports_path(self, tmp_path: Path) -> None:
        data_path, metadata_path, _ = _write_fixture_project(tmp_path)
        run_dir = tmp_path / "run"
        result = runner.invoke(
            app,
            [
                "clean",
                "--data", str(data_path),
                "--metadata", str(metadata_path),
                "--run-dir", str(run_dir),
            ],
        )
        assert result.exit_code == 0
        assert (run_dir / "cleaned_data.json").is_file()
        assert str(run_dir / "cleaned_data.json") in result.stdout

    def test_also_produces_validation_results_as_a_documented_side_effect(
        self, tmp_path: Path
    ) -> None:
        data_path, metadata_path, _ = _write_fixture_project(tmp_path)
        run_dir = tmp_path / "run"
        runner.invoke(
            app,
            [
                "clean",
                "--data", str(data_path),
                "--metadata", str(metadata_path),
                "--run-dir", str(run_dir),
            ],
        )
        assert (run_dir / "validation_results.json").is_file()

    def test_failure_produces_clean_error_not_a_traceback(self, tmp_path: Path) -> None:
        _, metadata_path, _ = _write_fixture_project(tmp_path)
        result = runner.invoke(
            app,
            [
                "clean",
                "--data", str(tmp_path / "does_not_exist.csv"),
                "--metadata", str(metadata_path),
                "--run-dir", str(tmp_path / "run"),
            ],
        )
        assert result.exit_code == 1
        assert "Traceback" not in result.output


class TestReportCommand:
    def test_generates_report_from_a_completed_run(self, tmp_path: Path) -> None:
        data_path, metadata_path, rules_path = _write_fixture_project(tmp_path)
        run_dir = tmp_path / "run"
        runner.invoke(
            app,
            [
                "validate",
                "--data", str(data_path),
                "--metadata", str(metadata_path),
                "--rules", str(rules_path),
                "--run-dir", str(run_dir),
            ],
        )

        output_path = tmp_path / "report.json"
        result = runner.invoke(
            app,
            ["report", "--run-dir", str(run_dir), "--format", "json", "--output", str(output_path)],
        )
        assert result.exit_code == 0
        assert output_path.is_file()
        payload = json.loads(output_path.read_text(encoding="utf-8"))
        assert "summary" in payload

    def test_report_before_any_run_fails_cleanly(self, tmp_path: Path) -> None:
        result = runner.invoke(
            app,
            [
                "report",
                "--run-dir", str(tmp_path / "never_run"),
                "--format", "json",
                "--output", str(tmp_path / "report.json"),
            ],
        )
        assert result.exit_code == 1
        assert "Traceback" not in result.output

    def test_report_when_manifest_exists_but_validation_incomplete_fails_cleanly(
        self, tmp_path: Path
    ) -> None:
        # A run that fails partway through Validating (a rule referencing
        # an unknown variable) leaves a manifest where Cleaning completed
        # but Validating did not - exercises the specific
        # "run exists but hasn't reached Validating" branch, distinct
        # from "no manifest at all."
        data_path, metadata_path, _ = _write_fixture_project(tmp_path)
        bad_rules_path = tmp_path / "bad_rules.yaml"
        bad_rules_path.write_text(
            "rules:\n  - {id: bad, type: required, variable: DOES_NOT_EXIST}\n",
            encoding="utf-8",
        )
        run_dir = tmp_path / "run"

        interrupted = runner.invoke(
            app,
            [
                "validate",
                "--data", str(data_path),
                "--metadata", str(metadata_path),
                "--rules", str(bad_rules_path),
                "--run-dir", str(run_dir),
            ],
        )
        assert interrupted.exit_code == 1

        result = runner.invoke(
            app,
            [
                "report",
                "--run-dir", str(run_dir),
                "--format", "json",
                "--output", str(tmp_path / "report.json"),
            ],
        )
        assert result.exit_code == 1
        assert "has not completed validation yet" in result.output


class TestExportCommand:
    def test_produces_both_cleaned_data_and_report(self, tmp_path: Path) -> None:
        data_path, metadata_path, rules_path = _write_fixture_project(tmp_path)
        run_dir = tmp_path / "run"
        report_output = tmp_path / "report.html"

        result = runner.invoke(
            app,
            [
                "export",
                "--data", str(data_path),
                "--metadata", str(metadata_path),
                "--rules", str(rules_path),
                "--run-dir", str(run_dir),
                "--report-output", str(report_output),
                "--report-format", "html",
            ],
        )

        assert result.exit_code == 0
        assert (run_dir / "cleaned_data.json").is_file()
        assert report_output.is_file()
        assert "Total findings" in result.stdout

    def test_failure_produces_clean_error_not_a_traceback(self, tmp_path: Path) -> None:
        _, metadata_path, rules_path = _write_fixture_project(tmp_path)
        result = runner.invoke(
            app,
            [
                "export",
                "--data", str(tmp_path / "does_not_exist.csv"),
                "--metadata", str(metadata_path),
                "--rules", str(rules_path),
                "--run-dir", str(tmp_path / "run"),
                "--report-output", str(tmp_path / "report.html"),
            ],
        )
        assert result.exit_code == 1
        assert "Traceback" not in result.output


class TestResumeAcrossCliInvocations:
    def test_resume_flag_skips_already_completed_cleaning(self, tmp_path: Path) -> None:
        from insightengine.execution.manifest import Stage, load_manifest

        data_path, metadata_path, rules_path = _write_error_triggering_fixture(tmp_path)
        run_dir = tmp_path / "run"

        # First invocation completes but with an ERROR-severity domain
        # finding (deliberate, from the fixture) - exit code 1.
        first = runner.invoke(
            app,
            [
                "validate",
                "--data", str(data_path),
                "--metadata", str(metadata_path),
                "--rules", str(rules_path),
                "--run-dir", str(run_dir),
            ],
        )
        assert first.exit_code == 1

        manifest = load_manifest(run_dir / "manifest.json")
        assert Stage.CLEANING in manifest.completed_stages

        # Second invocation, resumed - should still work and reach the
        # same conclusion without erroring on already-existing artifacts.
        second = runner.invoke(
            app,
            [
                "validate",
                "--data", str(data_path),
                "--metadata", str(metadata_path),
                "--rules", str(rules_path),
                "--run-dir", str(run_dir),
                "--resume",
            ],
        )
        assert second.exit_code == 1
        assert "Total findings" in second.stdout


class TestAcceptanceCriterion:
    """Each command runs end-to-end against one shared fixture project."""

    def test_all_five_commands_run_end_to_end(self, tmp_path: Path) -> None:
        project_dir = tmp_path / "project"
        init_result = runner.invoke(app, ["init", str(project_dir)])
        assert init_result.exit_code == 0

        data_path = project_dir / "datasets" / "raw" / "data.csv"
        data_path.write_text("EXAMPLE_RESPONSE\nHello\n\n", encoding="utf-8")
        metadata_path = project_dir / "metadata" / "questionnaire.yaml"
        rules_path = project_dir / "rules" / "validation.yaml"
        run_dir = project_dir / "run"

        validate_result = runner.invoke(
            app,
            [
                "validate",
                "--data", str(data_path),
                "--metadata", str(metadata_path),
                "--rules", str(rules_path),
                "--run-dir", str(run_dir / "validate"),
            ],
        )
        assert validate_result.exit_code == 0

        clean_result = runner.invoke(
            app,
            [
                "clean",
                "--data", str(data_path),
                "--metadata", str(metadata_path),
                "--run-dir", str(run_dir / "clean"),
            ],
        )
        assert clean_result.exit_code == 0

        report_result = runner.invoke(
            app,
            [
                "report",
                "--run-dir", str(run_dir / "clean"),
                "--format", "csv",
                "--output", str(project_dir / "reports" / "report.csv"),
            ],
        )
        assert report_result.exit_code == 0
        assert (project_dir / "reports" / "report.csv").is_file()

        export_result = runner.invoke(
            app,
            [
                "export",
                "--data", str(data_path),
                "--metadata", str(metadata_path),
                "--rules", str(rules_path),
                "--run-dir", str(run_dir / "export"),
                "--report-output", str(project_dir / "reports" / "export_report.html"),
            ],
        )
        assert export_result.exit_code == 0
        assert (project_dir / "reports" / "export_report.html").is_file()
