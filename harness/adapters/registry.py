"""The arm roster: adapters by name, and the cross-arm computations that need the whole list.

The registry is where ``forbidden_prefixes`` are filled: each arm is forbidden every other
arm's tool prefixes, so cross-arm contamination is checked mechanically by the gate rather
than by anyone remembering to.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from ..gate import AdmissionSignal, with_forbidden_prefixes
from .base import MemoryAdapter


class AdapterRegistry:
    def __init__(self) -> None:
        self._adapters: dict[str, MemoryAdapter] = {}

    def register(self, adapter: MemoryAdapter) -> MemoryAdapter:
        name = adapter.name
        if not name:
            raise ValueError("adapter has no name")
        if name in self._adapters:
            raise ValueError(f"adapter {name!r} is already registered")
        self._adapters[name] = adapter
        return adapter

    def get(self, name: str) -> MemoryAdapter:
        try:
            return self._adapters[name]
        except KeyError:
            raise KeyError(
                f"no adapter named {name!r}; registered: {sorted(self._adapters)}"
            ) from None

    def names(self) -> tuple[str, ...]:
        return tuple(self._adapters)

    def signals(self, arms: Iterable[str] | None = None) -> Mapping[str, AdmissionSignal]:
        """Admission signals for the given arms, with forbidden prefixes filled.

        Forbidden prefixes are computed over the arms **in this run**, not every adapter ever
        registered: an arm cannot be contaminated by a product that was never wired in.
        """

        selected = tuple(arms) if arms is not None else self.names()
        raw = {name: self.get(name).admission_signal() for name in selected}
        return with_forbidden_prefixes(raw)
