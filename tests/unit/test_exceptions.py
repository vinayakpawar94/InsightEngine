"""Unit tests for insightengine.core.exceptions.

These tests assert the *shape* of the hierarchy (every leaf is a subclass
of InsightEngineError, grouped correctly under its base), since that
structural contract is the entire point of this module — a caller doing
``except InsightEngineError`` must reliably catch everything the framework
raises.
"""

from __future__ import annotations

import insightengine.core.exceptions as exc_module
from insightengine.core.exceptions import (
    CircularDependencyError,
    CodebookError,
    ConfigurationError,
    DataBackendError,
    DataLoadError,
    DuplicatePluginError,
    DuplicateQuestionIdError,
    ExecutionError,
    InvalidSettingsError,
    InsightEngineError,
    PluginError,
    PluginNotFoundError,
    RuleEngineError,
    RuleParseError,
    UnknownVariableError,
    UnsafeExpressionError,
    UnsupportedFormatError,
)

_BASE_CLASSES = [
    ConfigurationError,
    CodebookError,
    DataBackendError,
    RuleEngineError,
    PluginError,
    ExecutionError,
]

_LEAF_TO_BASE = {
    InvalidSettingsError: ConfigurationError,
    DuplicateQuestionIdError: CodebookError,
    CircularDependencyError: CodebookError,
    UnknownVariableError: CodebookError,
    UnsupportedFormatError: DataBackendError,
    DataLoadError: DataBackendError,
    RuleParseError: RuleEngineError,
    UnsafeExpressionError: RuleEngineError,
    PluginNotFoundError: PluginError,
    DuplicatePluginError: PluginError,
}


def test_every_base_class_derives_from_insightengine_error() -> None:
    for base in _BASE_CLASSES:
        assert issubclass(base, InsightEngineError)


def test_every_leaf_derives_from_its_documented_base() -> None:
    for leaf, base in _LEAF_TO_BASE.items():
        assert issubclass(leaf, base)
        assert issubclass(leaf, InsightEngineError)


def test_insightengine_error_derives_from_exception_only() -> None:
    assert issubclass(InsightEngineError, Exception)


def test_catching_insightengine_error_catches_every_public_exception() -> None:
    public_exceptions = [
        obj
        for name, obj in vars(exc_module).items()
        if isinstance(obj, type)
        and issubclass(obj, Exception)
        and not name.startswith("_")
    ]
    assert InsightEngineError in public_exceptions
    for exc_class in public_exceptions:
        try:
            raise exc_class("test message")
        except InsightEngineError as caught:
            assert isinstance(caught, exc_class)
        else:
            raise AssertionError(f"{exc_class.__name__} was not caught by InsightEngineError")


def test_exception_message_is_preserved() -> None:
    try:
        raise DataLoadError("could not parse the file")
    except DataBackendError as caught:
        assert str(caught) == "could not parse the file"
