"""A generic, typed plugin registry backed by ``importlib.metadata`` entry points.

Design notes:

* One :class:`PluginRegistry` instance per extension point (one for
  metadata parsers, a separate one for report generators, etc.) — never
  a single global registry for everything. This keeps a bug in, say,
  report-generator registration from being able to corrupt the rule-type
  registry, and lets each subsystem define its own plugin ``Protocol``.
* Manual registration (:meth:`register`) and entry-point discovery
  (:meth:`discover_entry_points`) are separate, explicit operations.
  Nothing is discovered automatically at import time — a registry starts
  empty until something asks it to populate itself. Implicit discovery
  at import time is a common source of surprising, hard-to-test plugin
  behavior, and this registry deliberately avoids it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from importlib.metadata import entry_points
from typing import Generic, TypeVar

from insightengine.core.exceptions import DuplicatePluginError, PluginNotFoundError

T = TypeVar("T")


@dataclass
class PluginRegistry(Generic[T]):
    """A name-keyed registry of plugin implementations of type ``T``.

    Args:
        group: The ``importlib.metadata`` entry-point group this registry
            corresponds to, e.g. ``"insightengine.metadata_parsers"``. Used
            only by :meth:`discover_entry_points`; manual registration via
            :meth:`register` does not require a group to be meaningful.
    """

    group: str
    _plugins: dict[str, T] = field(default_factory=dict, init=False, repr=False)

    def register(self, name: str, plugin: T, *, overwrite: bool = False) -> None:
        """Register a plugin implementation under ``name``.

        Args:
            name: The name other code will use to look this plugin up.
            plugin: The plugin implementation itself.
            overwrite: If ``False`` (the default) and ``name`` is already
                registered, raises :class:`DuplicatePluginError` rather
                than silently replacing it — a silent overwrite is a
                common source of "which plugin actually ran" confusion.

        Raises:
            DuplicatePluginError: If ``name`` is already registered and
                ``overwrite`` is ``False``.
        """
        if not overwrite and name in self._plugins:
            raise DuplicatePluginError(
                f"A plugin named {name!r} is already registered in the "
                f"{self.group!r} registry. Pass overwrite=True if this is "
                f"intentional."
            )
        self._plugins[name] = plugin

    def get(self, name: str) -> T:
        """Retrieve a registered plugin by name.

        Raises:
            PluginNotFoundError: If no plugin is registered under ``name``.
        """
        try:
            return self._plugins[name]
        except KeyError as exc:
            available = ", ".join(sorted(self._plugins)) or "(none registered)"
            raise PluginNotFoundError(
                f"No plugin named {name!r} registered in the {self.group!r} "
                f"registry. Available: {available}"
            ) from exc

    def names(self) -> list[str]:
        """Return the sorted names of all currently registered plugins."""
        return sorted(self._plugins)

    def __contains__(self, name: str) -> bool:
        return name in self._plugins

    def __len__(self) -> int:
        return len(self._plugins)

    def discover_entry_points(self) -> list[str]:
        """Load and register every installed package's entry point in
        this registry's :attr:`group`.

        Each discovered entry point is loaded (via its own ``.load()``,
        which imports the target module) and registered under the entry
        point's declared name, with ``overwrite=True`` — a second
        discovery call is expected to refresh existing registrations
        rather than error on them.

        Returns:
            The names of the entry points that were discovered and
            registered, in the order ``importlib.metadata`` returned them.
        """
        discovered: list[str] = []
        for ep in entry_points(group=self.group):
            plugin = ep.load()
            self.register(ep.name, plugin, overwrite=True)
            discovered.append(ep.name)
        return discovered
