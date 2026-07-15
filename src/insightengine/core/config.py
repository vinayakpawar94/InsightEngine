"""Application configuration: typed models and a YAML loader.

Configuration is validated eagerly, at load time, via pydantic — a
malformed ``settings.yaml`` fails immediately with a clear error instead
of surfacing as a confusing ``KeyError`` three stages into a pipeline run.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Final

import yaml
from pydantic import BaseModel, Field, ValidationError

from insightengine.core.exceptions import InvalidSettingsError

_DEFAULT_LOG_LEVEL: Final[str] = "INFO"


class PathsConfig(BaseModel):
    """Filesystem locations the framework reads from and writes to."""

    projects_root: Path = Field(
        description="Root directory under which individual survey projects live."
    )
    plugins_root: Path | None = Field(
        default=None,
        description=(
            "Optional local directory to scan for plugin modules, in "
            "addition to installed-package entry points (see Phase 10)."
        ),
    )


class LoggingConfig(BaseModel):
    """Logging behavior configuration."""

    level: str = Field(
        default=_DEFAULT_LOG_LEVEL,
        description="Root log level, e.g. 'DEBUG', 'INFO', 'WARNING'.",
    )
    log_file: Path | None = Field(
        default=None,
        description="If set, log records are also written to this file.",
    )


class AppConfig(BaseModel):
    """Top-level, validated application configuration.

    Construct this via :func:`load_config` rather than directly, so that
    malformed YAML is translated into :class:`InvalidSettingsError`
    consistently, regardless of which pydantic error it originated from.
    """

    paths: PathsConfig
    logging: LoggingConfig = Field(default_factory=LoggingConfig)

    model_config = {"frozen": True}


def load_config(path: Path) -> AppConfig:
    """Load and validate application configuration from a YAML file.

    Args:
        path: Path to a YAML settings file.

    Returns:
        A validated, immutable :class:`AppConfig`.

    Raises:
        InvalidSettingsError: If the file does not exist, is not valid
            YAML, is not a mapping at the top level, or fails schema
            validation.
    """
    if not path.is_file():
        raise InvalidSettingsError(f"Configuration file not found: {path}")

    try:
        raw_text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise InvalidSettingsError(f"Could not read configuration file {path}: {exc}") from exc

    try:
        data: Any = yaml.safe_load(raw_text)
    except yaml.YAMLError as exc:
        raise InvalidSettingsError(f"Configuration file {path} is not valid YAML: {exc}") from exc

    if not isinstance(data, dict):
        raise InvalidSettingsError(
            f"Configuration file {path} must contain a top-level mapping, "
            f"got {type(data).__name__}."
        )

    try:
        return AppConfig.model_validate(data)
    except ValidationError as exc:
        raise InvalidSettingsError(f"Configuration file {path} failed validation:\n{exc}") from exc
