"""Unit tests for insightengine.execution.hooks."""

from __future__ import annotations

from insightengine.execution.hooks import HookRegistry


class TestHookRegistry:
    def test_on_start_fires_all_registered_hooks(self) -> None:
        calls: list[str] = []
        registry = HookRegistry()
        registry.register_on_start(lambda: calls.append("a"))
        registry.register_on_start(lambda: calls.append("b"))
        registry.fire_on_start()
        assert calls == ["a", "b"]

    def test_on_case_receives_row_index(self) -> None:
        seen: list[int] = []
        registry = HookRegistry()
        registry.register_on_case(seen.append)
        registry.fire_on_case(0)
        registry.fire_on_case(1)
        assert seen == [0, 1]

    def test_on_end_receives_success_flag(self) -> None:
        seen: list[bool] = []
        registry = HookRegistry()
        registry.register_on_end(seen.append)
        registry.fire_on_end(succeeded=True)
        registry.fire_on_end(succeeded=False)
        assert seen == [True, False]

    def test_no_hooks_registered_fires_safely(self) -> None:
        registry = HookRegistry()
        registry.fire_on_start()
        registry.fire_on_case(0)
        registry.fire_on_end(succeeded=True)  # no exception

    def test_multiple_on_case_hooks_all_fire_per_call(self) -> None:
        calls: list[str] = []
        registry = HookRegistry()
        registry.register_on_case(lambda i: calls.append(f"first-{i}"))
        registry.register_on_case(lambda i: calls.append(f"second-{i}"))
        registry.fire_on_case(5)
        assert calls == ["first-5", "second-5"]
