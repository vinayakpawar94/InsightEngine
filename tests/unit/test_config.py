"""Unit tests for insightengine.core.config."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from insightengine.core.config import AppConfig, load_config
from insightengine.core.exceptions import InvalidSettingsError


def _write(tmp_path: Path, text: str, filename: str = "settings.yaml") -> Path:
    path = tmp_path / filename
    path.write_text(text, encoding="utf-8")
    return path


class TestLoadConfigSuccess:
    def test_minimal_valid_config(self, tmp_path: Path) -> None:
        config_path = _write(
            tmp_path,
            f"paths:\n  projects_root: {tmp_path / 'projects'}\n",
        )
        config = load_config(config_path)
        assert isinstance(config, AppConfig)
        assert config.paths.projects_root == tmp_path / "projects"
        assert config.logging.level == "INFO"
        assert config.logging.log_file is None

    def test_full_config_with_logging_overrides(self, tmp_path: Path) -> None:
        config_path = _write(
            tmp_path,
            f"""
paths:
  projects_root: {tmp_path / 'projects'}
  plugins_root: {tmp_path / 'plugins'}
logging:
  level: DEBUG
  log_file: {tmp_path / 'logs' / 'run.log'}
""",
        )
        config = load_config(config_path)
        assert config.logging.level == "DEBUG"
        assert config.logging.log_file == tmp_path / "logs" / "run.log"
        assert config.paths.plugins_root == tmp_path / "plugins"

    def test_config_is_immutable(self, tmp_path: Path) -> None:
        config_path = _write(tmp_path, f"paths:\n  projects_root: {tmp_path}\n")
        config = load_config(config_path)
        with pytest.raises(Exception):
            config.logging = config.logging.model_copy(update={"level": "DEBUG"})  # type: ignore[misc]


class TestLoadConfigFailures:
    def test_missing_file_raises_invalid_settings_error(self, tmp_path: Path) -> None:
        with pytest.raises(InvalidSettingsError, match="not found"):
            load_config(tmp_path / "does_not_exist.yaml")

    def test_unreadable_file_raises_invalid_settings_error(self, tmp_path: Path) -> None:
        config_path = _write(tmp_path, f"paths:\n  projects_root: {tmp_path}\n")
        config_path.chmod(0o000)
        try:
            if os.access(config_path, os.R_OK):
                pytest.skip("running as a user that bypasses file permissions (e.g. root)")
            with pytest.raises(InvalidSettingsError, match="Could not read"):
                load_config(config_path)
        finally:
            config_path.chmod(0o644)

    def test_malformed_yaml_raises_invalid_settings_error(self, tmp_path: Path) -> None:
        config_path = _write(tmp_path, "paths: [this, is, not, a, mapping\n")
        with pytest.raises(InvalidSettingsError, match="not valid YAML"):
            load_config(config_path)

    def test_non_mapping_top_level_raises_invalid_settings_error(self, tmp_path: Path) -> None:
        config_path = _write(tmp_path, "- just\n- a\n- list\n")
        with pytest.raises(InvalidSettingsError, match="top-level mapping"):
            load_config(config_path)

    def test_missing_required_field_raises_invalid_settings_error(self, tmp_path: Path) -> None:
        config_path = _write(tmp_path, "logging:\n  level: DEBUG\n")
        with pytest.raises(InvalidSettingsError, match="failed validation"):
            load_config(config_path)

    def test_wrong_type_for_field_raises_invalid_settings_error(self, tmp_path: Path) -> None:
        config_path = _write(
            tmp_path,
            "paths:\n  projects_root: /tmp/x\nlogging:\n  level: [not, a, string]\n",
        )
        with pytest.raises(InvalidSettingsError, match="failed validation"):
            load_config(config_path)
