"""A genuinely out-of-tree insightengine plugin.

Used only in insightengine's own test suite to prove real
``entry_points`` discovery works end-to-end — installed via
``pip install -e`` from a location outside insightengine's own source
tree, at test time, in
``tests/unit/test_plugin_discovery_integration.py``.

Deliberately imports nothing from ``insightengine``: this proves a
third-party plugin author can implement insightengine's Protocol-based
extension points purely by structural conformance, without
``insightengine`` being a dependency of the plugin package at all. A
plugin author who *did* want to build real ``Codebook``/``RawTable``
objects would naturally depend on ``insightengine`` for that — this
package simply doesn't need to, since it exists only to prove discovery
and invocation work, not to be a functionally complete implementation.
"""

from __future__ import annotations


class DummyMetadataParser:
    """A structurally-valid MetadataParser that never touches a real file.

    Returns a recognizable sentinel rather than a real ``Codebook`` —
    good enough to prove the plugin was actually found and called.
    """

    def parse(self, source: object) -> dict[str, str]:
        return {"dummy_parser_called_with": str(source)}


class DummyReportGenerator:
    """A structurally-valid ReportGenerator that writes a small marker file."""

    def build(self, data: object, path: object) -> object:
        from pathlib import Path

        assert isinstance(path, Path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("dummy report", encoding="utf-8")
        return path


# Entry points reference these ready instances, not the bare classes -
# matching the convention insightengine's own built-in registries use
# (e.g. metadata_parser_registry.register("yaml", YamlMetadataParser())
# registers an instance). An entry point target is just an attribute
# reference: pointing it at a class would make ep.load() return the
# class itself, not something immediately callable the same way as
# every other registered plugin.
dummy_metadata_parser = DummyMetadataParser()
dummy_report_generator = DummyReportGenerator()
