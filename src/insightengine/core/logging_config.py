"""Logging setup for the insightengine framework.

Uses the standard library's :mod:`logging` module exclusively — no
third-party structured-logging dependency is introduced speculatively.
If structured/queryable logs become a real requirement later, that's an
explicit, justified addition to make then, not a default to bake in now.
"""

from __future__ import annotations

import logging
import logging.config
from typing import Any

from insightengine.core.config import LoggingConfig

_LOGGER_NAME: str = "insightengine"


def build_dict_config(config: LoggingConfig) -> dict[str, Any]:
    """Build a :func:`logging.config.dictConfig`-compatible dictionary
    from a validated :class:`LoggingConfig`.

    Kept as a separate, pure function (rather than inlined into
    :func:`configure_logging`) so tests can assert on the produced
    structure without needing to touch global logging state.
    """
    handlers: dict[str, Any] = {
        "console": {
            "class": "logging.StreamHandler",
            "level": config.level,
            "formatter": "standard",
        }
    }
    handler_names = ["console"]

    if config.log_file is not None:
        handlers["file"] = {
            "class": "logging.FileHandler",
            "level": config.level,
            "formatter": "standard",
            "filename": str(config.log_file),
            "encoding": "utf-8",
        }
        handler_names.append("file")

    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "standard": {
                "format": (
                    "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
                ),
            },
        },
        "handlers": handlers,
        "loggers": {
            _LOGGER_NAME: {
                "handlers": handler_names,
                "level": config.level,
                "propagate": False,
            },
        },
    }


def configure_logging(config: LoggingConfig) -> None:
    """Apply logging configuration process-wide.

    Args:
        config: Validated logging configuration, typically
            ``AppConfig.logging`` from :func:`insightengine.core.config.load_config`.
    """
    if config.log_file is not None:
        config.log_file.parent.mkdir(parents=True, exist_ok=True)
    logging.config.dictConfig(build_dict_config(config))


def get_logger(name: str | None = None) -> logging.Logger:
    """Return a logger under the ``insightengine`` namespace.

    Args:
        name: Optional sub-name, e.g. passing ``"metadata"`` returns the
            ``insightengine.metadata`` logger. If omitted, returns the root
            ``insightengine`` logger.
    """
    full_name = _LOGGER_NAME if name is None else f"{_LOGGER_NAME}.{name}"
    return logging.getLogger(full_name)
