---
sidebar_position: 8
---

# Mods, hooks and events

Every mod is a module or package with a literal `MOD_INFO`. The framework loads
mods in dependency order, runs an optional `initialize()`, and owns everything a
mod registers so unloading cannot leave stale callbacks behind.

```python
MOD_INFO = {"id": "my_mod", "dependencies": ["dcmod"]}

from dcmod import events
from modcore import HookContext, hook
from stubs.pr import Game

@events.game_update.listen(priority=10)
def on_update(game: Game) -> None:
    ...

@hook(Game.update)
def wrap_update(context: HookContext[[Game], None], game: Game) -> None:
    context.call_next(game)   # run the remaining hooks, then the original
```

Hooks compose: several mods may hook the same function, highest priority first,
then registration order. `call_next` continues the chain, `call_original`
deliberately skips the rest of it. A hook that raises propagates a catchable HL
exception with the Python traceback, the function index and the owning mod; the
original never runs twice. `register_hook` returns a `Registration` that can be
closed, and unloading a mod removes its hooks and subscriptions automatically.

Game core libraries publish their own events, so other mods never need to know
which native function produces them:

```python
# In a core library such as dcmod.
from modcore import Event
game_update: Event[[Game]] = Event("dcmod.game_update")

@hook(Game.update)
def publish(context: HookContext[[Game], None], game: Game) -> None:
    context.call_next(game)
    game_update.emit(game)
```

`emit` dispatches over the snapshot taken when it starts, so subscribing or
unsubscribing during a dispatch takes effect on the next one. A subscriber that
raises `Exception` is logged with its owning mod and the remaining subscribers
still run; `BaseException` propagates.

`load_mod`, `unload_mod` and `reload_mod` manage mods at runtime. Reloading
replaces Python state, but native objects that are still alive keep the class
and closures they were created with; hlmod never frees them early.
