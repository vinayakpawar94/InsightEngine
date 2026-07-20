"""Unit tests for the built-in plugin registries: metadata, data, reporting.

Registry discovery via real installed packages is exercised separately
in test_plugin_discovery_integration.py — these tests only cover the
pre-populated defaults and the registries' own group names.
"""

from __future__ import annotations

from insightengine.data.backends.pandas_backend import PandasBackend
from insightengine.data.registry import GROUP as DATA_GROUP
from insightengine.data.registry import data_backend_registry
from insightengine.metadata.parsers.yaml_native import YamlMetadataParser
from insightengine.metadata.registry import GROUP as METADATA_GROUP
from insightengine.metadata.registry import metadata_parser_registry
from insightengine.reporting.registry import GROUP as REPORTING_GROUP
from insightengine.reporting.registry import report_generator_registry


class TestMetadataParserRegistry:
    def test_group_name(self) -> None:
        assert METADATA_GROUP == "insightengine.metadata_parsers"

    def test_yaml_parser_pre_registered(self) -> None:
        assert "yaml" in metadata_parser_registry
        assert isinstance(metadata_parser_registry.get("yaml"), YamlMetadataParser)


class TestDataBackendRegistry:
    def test_group_name(self) -> None:
        assert DATA_GROUP == "insightengine.data_backends"

    def test_pandas_backend_pre_registered(self) -> None:
        assert "pandas" in data_backend_registry
        assert isinstance(data_backend_registry.get("pandas"), PandasBackend)


class TestReportGeneratorRegistry:
    def test_group_name(self) -> None:
        assert REPORTING_GROUP == "insightengine.report_generators"

    def test_all_four_built_in_generators_pre_registered(self) -> None:
        assert report_generator_registry.names() == ["csv", "excel", "html", "json"]
