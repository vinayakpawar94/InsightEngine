"""``on_start``/``on_case``/``on_end`` hook registration and firing.

**Scope, stated plainly:** ``on_case`` fires once per row over the
*cleaned* dataset, purely for observability (progress reporting, custom
logging) — it does not fire from inside actual rule evaluation. Phase 6's
``validate()`` is a frozen, atomic operation with no hook-injection
points of its own, and reopening it isn't in scope here. If per-rule,
per-row hooks into validation itself are wanted later, that's a
deliberate revision of Phase 6, not something this registry can retrofit
from the outside.
"""

from __future__ import annotations

from collections.abc import Callable

OnStartHook = Callable[[], None]
OnCaseHook = Callable[[int], None]
OnEndHook = Callable[[bool], None]
"""``OnEndHook`` receives whether the run succeeded."""


class HookRegistry:
    """A registry of callbacks fired at three points in an Orchestrator run."""

    def __init__(self) -> None:
        self._on_start: list[OnStartHook] = []
        self._on_case: list[OnCaseHook] = []
        self._on_end: list[OnEndHook] = []

    def register_on_start(self, hook: OnStartHook) -> None:
        self._on_start.append(hook)

    def register_on_case(self, hook: OnCaseHook) -> None:
        self._on_case.append(hook)

    def register_on_end(self, hook: OnEndHook) -> None:
        self._on_end.append(hook)

    def fire_on_start(self) -> None:
        for hook in self._on_start:
            hook()

    def fire_on_case(self, row_index: int) -> None:
        for hook in self._on_case:
            hook(row_index)

    def fire_on_end(self, *, succeeded: bool) -> None:
        for hook in self._on_end:
            hook(succeeded)
