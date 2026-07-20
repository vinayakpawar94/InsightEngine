"""The plugin registry for :class:`~insightengine.metadata.base.MetadataParser`
implementations.

A new sibling file, not an edit to the frozen
:mod:`insightengine.metadata.parsers.yaml_native` module — this registry
imports that module's existing class without modifying it.
"""

from __future__ import annotations

from insightengine.metadata.base import MetadataParser
from insightengine.metadata.parsers.yaml_native import YamlMetadataParser
from insightengine.plugins.registry import PluginRegistry

GROUP = "insightengine.metadata_parsers"

metadata_parser_registry: PluginRegistry[MetadataParser] = PluginRegistry(group=GROUP)
metadata_parser_registry.register("yaml", YamlMetadataParser())
