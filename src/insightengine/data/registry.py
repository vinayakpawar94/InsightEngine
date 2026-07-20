"""The plugin registry for :class:`~insightengine.data.base.DataBackend`
implementations.

A new sibling file, not an edit to the frozen
:mod:`insightengine.data.backends.pandas_backend` module.
"""

from __future__ import annotations

from insightengine.data.backends.pandas_backend import PandasBackend
from insightengine.data.base import DataBackend
from insightengine.plugins.registry import PluginRegistry

GROUP = "insightengine.data_backends"

data_backend_registry: PluginRegistry[DataBackend] = PluginRegistry(group=GROUP)
data_backend_registry.register("pandas", PandasBackend())
