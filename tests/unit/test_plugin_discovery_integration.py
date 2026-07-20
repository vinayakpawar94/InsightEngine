"""The phase's actual acceptance test: a genuinely out-of-tree,
pip-installed plugin is discovered and used, with zero changes to
insightengine's own code.

This does not monkeypatch ``importlib.metadata.entry_points`` (Phase 1's
own registry tests already did that, which proves the registry's
internal logic is correct but not that real package installation and
discovery actually connects end-to-end). This test does the real thing:
``pip install -e`` a separate package
(``tests/fixtures/dummy_plugin_package``, which imports nothing from
insightengine — see that package's own docstring) into the actual
running environment, then calls
:meth:`~insightengine.plugins.registry.PluginRegistry.discover_entry_points`
against fresh registries using the same group names insightengine's own
built-in registries use, and confirms the plugin is found and callable.

No network access is required — this is a local editable install with
no dependencies, verified to work offline in this project's own sandbox
before being wired into this test.
"""

from __future__ import annotations

import importlib
import site
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

from insightengine.data.registry import GROUP as DATA_BACKEND_GROUP
from insightengine.metadata.registry import GROUP as METADATA_PARSER_GROUP
from insightengine.plugins.registry import PluginRegistry
from insightengine.reporting.registry import GROUP as REPORT_GENERATOR_GROUP

_PACKAGE_DIR = Path(__file__).parent.parent / "fixtures" / "dummy_plugin_package"
_DISTRIBUTION_NAME = "insightengine-dummy-plugin"


def _pip(*args: str) -> None:
    subprocess.run(
        [sys.executable, "-m", "pip", *args, "--break-system-packages", "--quiet"],
        check=True,
    )
    _refresh_import_system()


def _refresh_import_system() -> None:
    """Make a package installed by the ``pip`` subprocess above actually
    importable in this already-running process.

    Two separate caches need clearing, confirmed by hitting each failure
    in turn while building this test:

    1. ``importlib.invalidate_caches()`` — the standard, documented step,
       but not sufficient on its own.
    2. Modern editable installs (PEP 660, setuptools' default mechanism)
       register a custom ``MetaPathFinder`` via a ``.pth`` file. ``.pth``
       files are normally only processed by the ``site`` module once, at
       interpreter startup — a ``.pth`` file that appears *after* startup
       is invisible until something re-runs that processing.
       ``site.addsitedir()`` on the relevant site-packages directories
       does exactly that, registering the new finder onto
       ``sys.meta_path`` for the rest of this process.
    """
    importlib.invalidate_caches()
    for directory in (*site.getsitepackages(), site.getusersitepackages()):
        site.addsitedir(directory)


@pytest.fixture
def installed_dummy_plugin() -> Iterator[None]:
    """Installs the real out-of-tree dummy plugin package for the
    duration of one test, and always uninstalls it afterward — even if
    the test fails — so no test run leaves the environment mutated for
    any other.
    """
    _pip("install", "-e", str(_PACKAGE_DIR))
    try:
        yield
    finally:
        _pip("uninstall", _DISTRIBUTION_NAME, "-y")


class TestAcceptanceCriterion:
    def test_dummy_metadata_parser_is_discovered_and_usable(
        self, installed_dummy_plugin: None
    ) -> None:
        registry: PluginRegistry[object] = PluginRegistry(group=METADATA_PARSER_GROUP)
        discovered = registry.discover_entry_points()

        assert "dummy" in discovered
        parser = registry.get("dummy")

        # "used", not just "found" - actually call it and check the result.
        result = parser.parse("some/source/path")  # type: ignore[attr-defined]
        assert result == {"dummy_parser_called_with": "some/source/path"}

    def test_dummy_report_generator_is_discovered_and_usable(
        self, installed_dummy_plugin: None, tmp_path: Path
    ) -> None:
        registry: PluginRegistry[object] = PluginRegistry(group=REPORT_GENERATOR_GROUP)
        discovered = registry.discover_entry_points()

        assert "dummy" in discovered
        generator = registry.get("dummy")

        output_path = tmp_path / "dummy_report.txt"
        result_path = generator.build(None, output_path)  # type: ignore[attr-defined]

        assert result_path == output_path
        assert output_path.read_text(encoding="utf-8") == "dummy report"

    def test_a_group_the_plugin_does_not_register_finds_nothing(
        self, installed_dummy_plugin: None
    ) -> None:
        # The dummy plugin only declares metadata_parsers and
        # report_generators entry points - confirms discovery is
        # correctly scoped per group, not "anything installed matches."
        registry: PluginRegistry[object] = PluginRegistry(group=DATA_BACKEND_GROUP)
        discovered = registry.discover_entry_points()
        assert "dummy" not in discovered

    def test_teardown_actually_uninstalls_the_plugin(self) -> None:
        # Self-contained: installs, confirms discovery works, tears down
        # manually (not via the fixture, to avoid depending on any
        # implicit ordering relative to other tests), then re-checks that
        # discovery finds nothing - proving teardown genuinely removes
        # the package rather than just no longer being asked about it.
        registry: PluginRegistry[object] = PluginRegistry(group=METADATA_PARSER_GROUP)

        _pip("install", "-e", str(_PACKAGE_DIR))
        try:
            assert "dummy" in registry.discover_entry_points()
        finally:
            _pip("uninstall", _DISTRIBUTION_NAME, "-y")

        fresh_registry: PluginRegistry[object] = PluginRegistry(group=METADATA_PARSER_GROUP)
        assert "dummy" not in fresh_registry.discover_entry_points()
