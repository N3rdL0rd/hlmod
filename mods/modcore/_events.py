"""Shared event objects with mutation-time snapshots and owned subscriptions."""

import logging
from typing import Callable, Generic, ParamSpec

from ._lifecycle import Mod, Registration, _activate

P = ParamSpec("P")
_log = logging.getLogger("modcore.events")


class Event(Generic[P]):
    def __init__(self, name: str):
        self.name = name
        self._subscribers: tuple[tuple[int, Callable[P, None], Registration], ...] = ()

    def subscribe(self, callback: Callable[P, None], *, priority: int = 0,
                  owner: Mod | None = None) -> Registration:
        if not callable(callback):
            raise TypeError("Event subscriber must be callable")
        if not isinstance(priority, int):
            raise TypeError("Event priority must be an integer")

        def remove() -> None:
            self._subscribers = tuple(item for item in self._subscribers if item[2] is not registration)

        registration = Registration(remove, owner=owner)
        entry = (priority, callback, registration)
        subscribers = self._subscribers
        index = next((i for i, item in enumerate(subscribers) if item[0] < priority), len(subscribers))
        self._subscribers = subscribers[:index] + (entry,) + subscribers[index:]
        return registration

    def listen(self, *, priority: int = 0, owner: Mod | None = None):
        def decorator(callback: Callable[P, None]) -> Callable[P, None]:
            self.subscribe(callback, priority=priority, owner=owner)
            return callback
        return decorator

    def emit(self, *args: P.args, **kwargs: P.kwargs) -> None:
        # The tuple itself is the entry snapshot: removals never mutate it, and
        # recursive emissions see the newly published tuple immediately.
        subscribers = self._subscribers
        if not subscribers:
            return
        for _, callback, registration in subscribers:
            with _activate(registration.owner):
                try:
                    callback(*args, **kwargs)
                except Exception:
                    owner = registration.owner.id if registration.owner is not None else "<unowned>"
                    _log.exception("Event %r subscriber failed (mod %s)", self.name, owner)


mods_loaded: Event[[]] = Event("modcore.mods_loaded")
shutting_down: Event[[]] = Event("modcore.shutting_down")
