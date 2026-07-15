"""Unit tests for insightengine.plugins.registry.

Entry-point discovery (:meth:`PluginRegistry.discover_entry_points`) is
exercised against this test's own package metadata rather than mocked,
using a real dummy entry point declared for the ``insightengine`` test
package itself — see ``test_discover_entry_points`` below, which
monkeypatches ``importlib.metadata.entry_points`` with a real
``EntryPoint`` object pointing at a real, importable function, rather
than a bare mock, so the test exercises the actual ``.load()`` codepath.
"""

from __future__ import annotations

from importlib.metadata import EntryPoint

import pytest

from insightengine.core.exceptions import DuplicatePluginError, PluginNotFoundError
from insightengine.plugins.registry import PluginRegistry


def _dummy_plugin_function() -> str:
    """A real, importable function used as a fake plugin target in tests."""
    return "dummy-plugin-result"


class TestManualRegistration:
    def test_register_and_get(self) -> None:
        registry: PluginRegistry[str] = PluginRegistry(group="insightengine.test_plugins")
        registry.register("upper", "UPPER_IMPL")
        assert registry.get("upper") == "UPPER_IMPL"

    def test_get_missing_raises_plugin_not_found_error(self) -> None:
        registry: PluginRegistry[str] = PluginRegistry(group="insightengine.test_plugins")
        with pytest.raises(PluginNotFoundError, match="csv"):
            registry.get("csv")

    def test_duplicate_registration_without_overwrite_raises(self) -> None:
        registry: PluginRegistry[str] = PluginRegistry(group="insightengine.test_plugins")
        registry.register("csv", "first")
        with pytest.raises(DuplicatePluginError):
            registry.register("csv", "second")
        assert registry.get("csv") == "first"

    def test_duplicate_registration_with_overwrite_replaces(self) -> None:
        registry: PluginRegistry[str] = PluginRegistry(group="insightengine.test_plugins")
        registry.register("csv", "first")
        registry.register("csv", "second", overwrite=True)
        assert registry.get("csv") == "second"

    def test_names_returns_sorted_registered_names(self) -> None:
        registry: PluginRegistry[str] = PluginRegistry(group="insightengine.test_plugins")
        registry.register("zebra", "z")
        registry.register("apple", "a")
        assert registry.names() == ["apple", "zebra"]

    def test_contains_and_len(self) -> None:
        registry: PluginRegistry[str] = PluginRegistry(group="insightengine.test_plugins")
        assert "csv" not in registry
        assert len(registry) == 0
        registry.register("csv", "impl")
        assert "csv" in registry
        assert len(registry) == 1


class TestEntryPointDiscovery:
    def test_discover_entry_points(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake_entry_point = EntryPoint(
            name="dummy",
            value=f"{__name__}:_dummy_plugin_function",
            group="insightengine.test_plugins",
        )

        def fake_entry_points(*, group: str) -> list[EntryPoint]:
            assert group == "insightengine.test_plugins"
            return [fake_entry_point]

        monkeypatch.setattr(
            "insightengine.plugins.registry.entry_points", fake_entry_points
        )

        registry: PluginRegistry[object] = PluginRegistry(group="insightengine.test_plugins")
        discovered = registry.discover_entry_points()

        assert discovered == ["dummy"]
        assert registry.get("dummy") is _dummy_plugin_function
        assert registry.get("dummy")() == "dummy-plugin-result"

    def test_discover_entry_points_overwrites_existing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        fake_entry_point = EntryPoint(
            name="dummy",
            value=f"{__name__}:_dummy_plugin_function",
            group="insightengine.test_plugins",
        )
        monkeypatch.setattr(
            "insightengine.plugins.registry.entry_points",
            lambda *, group: [fake_entry_point],
        )

        registry: PluginRegistry[object] = PluginRegistry(group="insightengine.test_plugins")
        registry.register("dummy", "placeholder-before-discovery")
        registry.discover_entry_points()

        assert registry.get("dummy") is _dummy_plugin_function

    def test_discover_entry_points_empty_group_returns_empty_list(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "insightengine.plugins.registry.entry_points", lambda *, group: []
        )
        registry: PluginRegistry[object] = PluginRegistry(group="insightengine.nonexistent_group")
        assert registry.discover_entry_points() == []
        assert len(registry) == 0
