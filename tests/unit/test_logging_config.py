"""Unit tests for insightengine.core.logging_config."""

from __future__ import annotations

import logging
from pathlib import Path

from insightengine.core.config import LoggingConfig
from insightengine.core.logging_config import build_dict_config, configure_logging, get_logger


class TestBuildDictConfig:
    def test_console_only_when_no_log_file(self) -> None:
        config = LoggingConfig(level="INFO")
        dict_config = build_dict_config(config)
        assert set(dict_config["handlers"]) == {"console"}
        assert dict_config["loggers"]["insightengine"]["handlers"] == ["console"]

    def test_adds_file_handler_when_log_file_set(self, tmp_path: Path) -> None:
        log_file = tmp_path / "run.log"
        config = LoggingConfig(level="DEBUG", log_file=log_file)
        dict_config = build_dict_config(config)
        assert set(dict_config["handlers"]) == {"console", "file"}
        assert dict_config["handlers"]["file"]["filename"] == str(log_file)
        assert dict_config["loggers"]["insightengine"]["handlers"] == ["console", "file"]

    def test_level_propagates_to_handlers_and_logger(self) -> None:
        config = LoggingConfig(level="WARNING")
        dict_config = build_dict_config(config)
        assert dict_config["handlers"]["console"]["level"] == "WARNING"
        assert dict_config["loggers"]["insightengine"]["level"] == "WARNING"

    def test_logger_does_not_propagate_to_root(self) -> None:
        config = LoggingConfig()
        dict_config = build_dict_config(config)
        assert dict_config["loggers"]["insightengine"]["propagate"] is False


class TestConfigureLogging:
    def test_creates_log_file_parent_directory(self, tmp_path: Path) -> None:
        log_file = tmp_path / "nested" / "dir" / "run.log"
        configure_logging(LoggingConfig(log_file=log_file))
        assert log_file.parent.is_dir()

    def test_writes_to_configured_log_file(self, tmp_path: Path) -> None:
        log_file = tmp_path / "run.log"
        configure_logging(LoggingConfig(level="INFO", log_file=log_file))
        logger = get_logger("test_writes")
        logger.info("hello from test")
        for handler in logging.getLogger("insightengine").handlers:
            handler.flush()
        assert log_file.exists()
        assert "hello from test" in log_file.read_text(encoding="utf-8")


class TestGetLogger:
    def test_root_logger_name(self) -> None:
        assert get_logger().name == "insightengine"

    def test_sub_logger_name(self) -> None:
        assert get_logger("metadata").name == "insightengine.metadata"

    def test_sub_loggers_are_children_of_root(self) -> None:
        root = get_logger()
        child = get_logger("data")
        assert child.name.startswith(root.name + ".")
