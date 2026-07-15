"""Generic plugin registration and discovery.

This is the one plugin mechanism used by every extension point in the
framework (metadata parsers, data backends, rule types, report
generators, cleaning transformers — see the architecture document's
Extension Points section). Each subsystem creates its own
:class:`~insightengine.plugins.registry.PluginRegistry` instance rather than
this module holding global mutable state, so tests can construct an
isolated registry instead of contending over a shared singleton.
"""

from __future__ import annotations

from insightengine.plugins.registry import PluginRegistry

__all__ = ["PluginRegistry"]
