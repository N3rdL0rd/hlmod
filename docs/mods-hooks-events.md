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

That's the whole surface area most mods ever touch. Everything below is what's
actually happening underneath it - discovery, ordering, ownership, and the two
composition mechanisms (`hook` and `Event`) mods use to talk to the game and to
each other without stepping on one another. This page is long because it's the
one page you actually need to have read carefully; the rest of the docs mostly
assume you have.

## `MOD_INFO`

`MOD_INFO` has to be a plain, literal dictionary assigned at module scope -
`MOD_INFO = {...}` or `MOD_INFO: dict = {...}`, no function calls, no
f-strings, no referencing some other constant. That's not a style preference,
it's a hard requirement: the loader finds `MOD_INFO` by parsing your mod's
source with `ast` and evaluating that one assignment with `ast.literal_eval`,
*without importing the module*. It has to work this way, because the whole
point of `MOD_INFO.dependencies` is to tell the framework what order to import
things in - by the time your mod's top-level code actually runs, its
dependencies are guaranteed to already be loaded, which means the loader has
to know the dependency graph *before* it's safe to import anything at all.

| Key | Required | Type | Meaning |
| --- | --- | --- | --- |
| `id` | yes | non-empty `str` | Logical identifier. Used as the dependency-graph key and as the argument mods pass to `load_mod`/`unload_mod`/`reload_mod`. Doesn't have to match the file or package name. |
| `dependencies` | no (default `[]`) | list of mod ids | Other mods' `id`s that must finish loading first. Deduplicated, order-preserving. |
| `enabled` | no (default `True`) | `bool` | `False` skips the mod entirely - it's not imported, and it's not in the dependency graph, so nothing can depend on it either. |
| `name`, `description`, `version` | no | `str` | Purely descriptive. The loader doesn't read them for anything; they exist for humans (and for the mod's own code, if it wants to read its own `MOD_INFO["version"]` back later - `dcmod` does exactly this to build a version string). |

Any other keys you put in `MOD_INFO` are left alone and passed through
untouched - the loader only ever looks at `id`, `dependencies`, and `enabled`.

`modcore` itself is a completely ordinary mod as far as this system is
concerned: `mods/modcore/__init__.py` has its own `MOD_INFO = {"id":
"modcore", ..., "dependencies": []}`, sitting right there in the `mods/`
directory next to everything else. The native bootstrap imports `modcore`
directly before the mod loader ever runs (it has to - the loader itself is
Python code that lives inside `modcore`), but it still shows up in the
dependency graph, so `"dependencies": ["modcore"]` in your own `MOD_INFO`
(exactly what `dcmod` declares) is a real, meaningful ordering constraint, not
a formality.

## Discovery and load order

At startup, `mod_sorter.py` (embedded directly into the `hl` binary, so it
runs before any mod's own code does) walks the primary mods directory plus
anything listed in `HLMOD_EXTRA_MODS` (see
[Developing outside the mods directory](./external-mods.md)), skipping
anything starting with `_` and the generated `stubs/` package. For each
`*.py` file and each package directory's `__init__.py`, it looks for a
literal `MOD_INFO` the way described above. A directory's import name is its
directory name; a single-file mod's import name is the filename without
`.py`. Note that this import name is *not* the human-readable `MOD_INFO.name`
field - it's derived purely from the filesystem.

Two things fail loudly at this stage, before anything is imported:

- **Duplicate ids.** Two mods declaring the same `MOD_INFO["id"]` raises
  `ValueError: Duplicate mod ID 'whatever': first_mod and second_mod`.
- **Unmet dependencies.** A mod depending on an id nothing provides (including
  an id that exists but is `"enabled": False`) fails resolution with
  `Mod 'whatever' has an unmet dependency: 'missing_id'`.

With every enabled mod's id and dependency list known, the actual ordering is
a textbook Kahn's-algorithm topological sort: compute each mod's in-degree
(number of unresolved dependencies), seed a queue with every mod that has
none, and repeatedly pop a ready mod, append it to the load order, and
decrement the in-degree of everything that depends on it, pushing anything
that just hit zero. The queue is seeded and refilled in *discovery order*
(alphabetical per directory, primary directory before `HLMOD_EXTRA_MODS`
entries), so for a given set of mod files the resulting order is completely
deterministic - re-running the sort on the same directory always produces the
same sequence, not just *a* valid one.

If the sort finishes without placing every mod, whatever's left has a nonzero
in-degree it can never resolve - a cycle. The loader doesn't try to explain
*which* edges form the cycle, just which mods are stuck:

```python
# mods/a.py
MOD_INFO = {"id": "a", "dependencies": ["b"]}

# mods/b.py
MOD_INFO = {"id": "b", "dependencies": ["a"]}
```

Launching the game with both of those present halts with:

```
RuntimeError: Dependency cycle blocks mods: ['a', 'b']
```

printed to stderr before the process gives up on startup entirely - a mod
load failure at this stage isn't recoverable, there's no partial game to run.

That startup-time sort only governs the *initial* batch load, though.
`load_mod` (see below) is a normal runtime function any mod can call, and it
re-validates its own dependency preconditions independently rather than
trusting that some earlier sort already checked them - which matters the
moment a "mod manager" mod starts loading plugins on demand after startup,
well outside the sorter's view entirely.

## The `Mod` object and its lifecycle

Every loaded mod is represented by a `Mod` instance, tracked internally by
id. It's a plain state container:

```python
class Mod:
    def __init__(self, mod_id, module_name, dependencies=()):
        self.id = mod_id
        self.module_name = module_name
        self.dependencies = dependencies
        self.module: ModuleType | None = None
        self.state = "loading"
        # plus a private list of Registrations it owns
```

`state` moves through `"loading"` → `"loaded"` → `"unloading"` → `"unloaded"`
and is checked defensively throughout the rest of the module - you can't
register a new hook or event subscription owned by a mod that's mid-unload,
and you can't unload a mod that's already unloading.

`load_mod(mod_id, module_name, dependencies=())` is what both the C bootstrap
loop and any later runtime caller actually go through. Before importing
anything it checks, in order: the framework isn't mid-shutdown; no mod is
already registered under `mod_id`; no other mod already owns `module_name`
(two different ids can't fight over the same importable module); and for
every listed dependency, that it's `not mod_id` itself (a mod depending on
itself is rejected immediately as `"dependency cycle"`), that it's currently
loaded at all, and that its `state` is specifically `"loaded"` rather than
still `"loading"` (which reports `"dependency 'x' is 'loading'; possible
cycle"` - the practical situation this catches is a dependency's own
`initialize()` trying to load something that depends back on it). Only after
all of that does it actually `import_module` your mod and, if present, call
its `initialize()` - both with your mod set as the *current* mod (see
`current_mod()` below) so anything you register during import or
`initialize()` is automatically attributed to you.

If import or `initialize()` raises, `load_mod` rolls back everything that mod
managed to register before the failure, evicts the mod's module (and every
submodule) from `sys.modules`, and re-raises. An `Exception` gets wrapped as
`ModError(mod_id, "load", "import or initialize failed")` with the original
exception chained via `from`; a `BaseException` (`SystemExit`,
`KeyboardInterrupt`, and friends) is left alone and just gets a note attached
instead of being wrapped, so it still propagates as itself. That
`Exception`-wraps-but-`BaseException`-doesn't-block split shows up again,
independently, in how `Event.emit` treats subscriber failures - see below.

`current_mod()` returns whichever `Mod` is "active" right now, tracked with a
`contextvars.ContextVar` rather than a plain global specifically so it
behaves correctly across `asyncio` tasks and threads, not just synchronous
call stacks. It's what lets `register_hook(...)` and `Event.subscribe(...)`
default their `owner=` argument to "whoever's code is calling this right
now" instead of making every mod pass its own identity around by hand.
`ModError` itself carries `.mod_id` and `.operation` as real attributes, not
just message text, if you want to catch and branch on it programmatically.

## `Registration`: an object, not a callback

Every hook and every event subscription hands back a `Registration`. It
would be simpler on paper for `register_hook`/`Event.subscribe` to just
return a bare `close()` callable - but a `Registration` has to do several
things a raw closure can't do by itself, so it's a real type:

- **It's idempotently closeable.** `close()` sets its internal callback to
  `None` before invoking the real one, and does nothing at all on a second
  call. A bare closure would call whatever cleanup it wraps twice if you
  weren't careful.
- **It's the removal token, not just the close handle.** The tuple stored in
  a hook chain or an event's subscriber list holds the `Registration` object
  itself, and removal filters that collection by `item is not registration`
  identity. The same object is both "the thing you call `.close()` on" and
  "the sentinel the internal machinery uses to find and drop that entry" -
  one type serving both roles instead of a closure plus a separate
  identity token.
- **It tracks its owner and registers itself with it.** Creating a
  `Registration` with an active owner appends it to that `Mod`'s private
  registration list immediately (and raises `ModError(..., "register",
  "owner is not active")` if the owner isn't currently `"loading"` or
  `"loaded"`). That's what makes automatic cleanup on unload possible without
  every call site in `_hooks.py` and `_events.py` reimplementing bookkeeping.
- **It restores the right `current_mod()` around its own close.** `close()`
  runs its callback inside `_activate(self.owner)`, so if closing one
  registration happens to trigger more framework activity, `current_mod()`
  still reports the original owner rather than whatever mod happened to be
  the one that called `.close()`.
- **It's a context manager.** `Registration.__enter__`/`__exit__` just calls
  `close()`, so a hook or subscription scoped to one block is a `with`
  statement, not a manually-paired setup/teardown.

Unloading a mod drains its registration list **in reverse registration
order** (last registered, first closed), catching each `close()`'s errors
individually - one broken close doesn't stop the rest of the mod's resources
from also getting released - and reports every failure together, each
annotated with `f"While removing a registration owned by mod {mod.id!r}"`.

Here's a `Registration` being closed by hand, rather than left for unload to
find:

```python
from modcore import HookContext, Registration, current_mod, register_hook
from stubs.pr import Game, Hero

_god_mode: Registration | None = None

def block_damage(context: HookContext[[Hero, int], None], hero: Hero, amount: int) -> None:
    pass  # never calls context.call_next: the hit just doesn't happen

def enable_god_mode() -> None:
    global _god_mode
    if _god_mode is None:
        _god_mode = register_hook(Hero.take_damage, block_damage, priority=100)

def disable_god_mode() -> None:
    global _god_mode
    if _god_mode is not None:
        _god_mode.close()   # second close() from anywhere else would be a no-op
        _god_mode = None
```

Nothing here is special-cased for "manual" versus "automatic" closing -
`enable_god_mode`/`disable_god_mode` could just as well be wired to a REPL
command or a debug menu toggle, and if the mod gets unloaded with god mode
still on, the same `Registration` gets closed automatically as part of
teardown, in exactly the same way.

## Unloading, reloading, and shutdown

`unload_mod(mod_id, *, cascade=False)` computes which mods actually need to
come down: a depth-first walk starting at `mod_id`, visiting anything that
*depends on* it first. If something still depends on the mod you asked to
unload and `cascade` is `False`, it refuses with `"required by x, y"` rather
than silently tearing down mods you didn't ask about; with `cascade=True` it
unloads the whole dependent chain, dependents-first, target-last. Each mod in
that order gets its `state` flipped to `"unloading"` up front (before any
callbacks run, so a `shutdown()` hook can't sneak a reload of a mod that's
already mid-teardown), then actually torn down: its own module-level
`shutdown()` callback runs if it defined one - specifically excluding the
case where a mod merely did `from modcore import shutdown` and never
overrode it, so that import doesn't accidentally become the mod's per-mod
teardown hook - followed unconditionally by draining its registrations and
evicting its module (and submodules) from `sys.modules`. Errors from any
mod's `shutdown()` or from its registration cleanup are collected rather than
raised immediately, so one broken mod's unload doesn't stop its neighbors
from also coming down; if anything went wrong, `unload_mod` raises a
`BaseExceptionGroup` once everything's been given a chance to clean up.

`reload_mod(mod_id, *, cascade=False)` is `unload_mod` immediately followed
by re-`load_mod`-ing the same mods in reverse (target first, its dependents
on top, mirroring how they were torn down), with `importlib.invalidate_caches()`
in between so edited source on disk is actually picked up - this is the
mechanism [the dev loop](./dev-loop.md) hot-reload feature rides on. It
refuses outright if `modcore` itself is anywhere in the affected set
(`"the framework cannot reload itself"`) - reloading the module that's
currently running the reload isn't something the framework tries to survive.
If any mod in the sequence fails to reload, whatever already succeeded in
*this* reload attempt gets force-unloaded again so you're not left with a
half-reloaded mod running stale-but-different code next to its dependents;
mods further down the sequence that were never reached are simply left
unloaded. Reload is not a transactional rollback to "however things were
before you called it" - it just refuses to leave a partially-reloaded mod
running.

:::note
Reloading swaps out a mod's *Python* module state. Any native HL object
that's already alive keeps the class and closures it was constructed with -
hlmod doesn't retroactively rewrite a live object's vtable out from under
the VM. See [Known issues](./known-issues.md#reloading-doesnt-touch-already-running-native-instances)
for what that means in practice.
:::

`finish_loading()` is called once, after every mod in the initial batch has
loaded, and emits the `mods_loaded` event - it's the framework's own
"everyone's `initialize()` has run" signal, not a statement about the host
game being ready to play. It raises `RuntimeError` if any mod is still
`"loading"` or `"unloading"` when called, and calling it again is a no-op.
`shutdown()` is the mirror image at process exit: it emits `shutting_down`
first, then unloads every remaining mod in reverse load order, collecting
errors from the event emission and every mod's unload into one final
`BaseExceptionGroup` rather than aborting partway through.

## Hooks: composing behavior on one function

`register_hook(target, callback, *, priority=0, owner=None)` and its
decorator form `hook(target, *, priority=0, owner=None)` install a Python
callback into the dispatch chain for one HL function. `target` accepts a
function name (resolved with `native.findex_for_name`), a raw integer
findex, a sequence of findexes (installs the same callback on all of them at
once), or a generated method reference like `Game.update` - anything
callable carrying `__hl_findex__` metadata, which is how the stub-generated
methods you actually write hooks against work. Bound methods are explicitly
rejected (`"use Class.method so the native receiver remains an explicit
argument"`), and a target with keyword-only parameters or `**kwargs` in its
signature can't be hooked at all, since positional argument forwarding is
how the chain actually calls things.

There's exactly one dispatcher installed per findex, the first time anything
hooks it - a `_HookChain` holding an ordered tuple of `(priority, callback,
registration, target_signature)` entries. Every later `register_hook` call
against the same findex just inserts another entry into the *same* chain;
unhooking the last entry unregisters the native dispatcher entirely rather
than leaving an empty chain sitting around. New entries are inserted just
before the first existing entry with a strictly lower priority - so among
equal priorities, whoever registered first runs first, and higher priority
always runs before lower, deterministically: **priority, then registration
order**, exactly as advertised.

`HookContext` is what your callback actually receives as its first argument.
`context.call_next(*args)` invokes whatever's next in the chain - the next
lower-priority hook, or, once the chain is exhausted, the original HL
function itself. `context.call_original(*args)` is a different thing
entirely: it jumps straight to the underlying native function immediately,
skipping every remaining hook in the chain outright, not just the current
one. A hook that calls `call_original` instead of `call_next` silently
prevents every hook registered at lower priority from ever running for that
particular call - which is sometimes exactly what you want (you're the
authority on whether this call happens at all) and sometimes a bug in a mod
that didn't realize other mods were also hooking the same function.

If a hook raises, `_invoke` doesn't swallow it or retry the original -
whatever the exception is, it attaches a note identifying the findex and the
owning mod (`f"Hook findex {findex}, mod {owner!r}"`) and re-raises
immediately, and it picks up another note at every frame it passes back
through on the way out, so an exception raised deep in a chain arrives with
one note per hook it unwound through. That failure eventually reaches the
native call site as a catchable HL exception carrying the Python traceback;
the original is never invoked a second time by this machinery, since by the
time an exception is propagating, either nothing called it yet or something
already did.

Hooks and events differ sharply here on purpose: a hook stands in for
something the engine is about to use the return value of, so a hook failure
has to fail loud and stop the call. An event is a fire-and-forget
notification with no return value anyone's waiting on, so - as the next
section covers - one broken subscriber doesn't get to break every other
mod's unrelated listener.

`call_next`/`call_original` also accept keyword arguments, but only against
a target that actually carries a signature (a generated method reference,
not a raw name or findex) - `context.call_next(hero=h, amount=5)` gets bound
against that signature and converted to positional arguments before being
forwarded, and raises `TypeError` if you try that against an index/name
target with no signature to bind against.

## Events: decoupled publish/subscribe

Hooks intercept one specific native call site. Events are how library code
publishes something happened without caring who's listening - `dcmod`
publishes `game_update` off the back of its own `Game.update` hook so every
other mod can subscribe to "the game updated" without knowing or caring that
a hook is involved at all:

```python
# In a core library such as dcmod.
from modcore import Event
game_update: Event[[Game]] = Event("dcmod.game_update")

@hook(Game.update)
def publish(context: HookContext[[Game], None], game: Game) -> None:
    context.call_next(game)
    game_update.emit(game)
```

`Event(name)` just needs a name (used in log messages, not for lookup -
there's no global event registry to collide over). `subscribe(callback, *,
priority=0, owner=None)` and the `@event.listen(priority=0, owner=None)`
decorator both return a `Registration` exactly the way hooks do, and use the
identical priority-then-registration-order insertion rule described above -
it's the same tie-break logic, independently implemented for the same
reason.

`emit(*args, **kwargs)` calls every current subscriber in priority order.
The subscriber tuple itself doubles as its own snapshot: `_subscribers` is
replaced wholesale, never mutated in place, on every subscribe or
unsubscribe, so a dispatch in progress keeps iterating the tuple it started
with even if a subscriber unsubscribes itself (or something else) partway
through - that change takes effect on the *next* `emit()`, not the current
one. A subscriber that recursively calls `emit()` again, on the other hand,
sees the newly published tuple immediately, since it reads `self._subscribers`
fresh rather than inheriting the caller's snapshot.

Each subscriber runs with its owning mod active (so `current_mod()` reports
correctly from inside it), and:

```python
try:
    callback(*args, **kwargs)
except Exception:
    owner = registration.owner.id if registration.owner is not None else "<unowned>"
    _log.exception("Event %r subscriber failed (mod %s)", self.name, owner)
```

A subscriber raising an ordinary `Exception` gets logged with the event's
name and its owning mod id, and dispatch just continues on to the remaining
subscribers - one mod's broken listener doesn't take down anyone else's.
`BaseException` (`SystemExit`, `KeyboardInterrupt`, an `asyncio.CancelledError`,
...) is deliberately *not* caught here, and propagates straight out of
`emit()`, aborting the rest of that dispatch.

`modcore` ships two events of its own, both zero-argument: `mods_loaded`,
emitted once by `finish_loading()` after every startup mod has initialized,
and `shutting_down`, emitted once by `shutdown()` before any mod actually
starts tearing down. Subscribing to either is the idiomatic way to defer
work that needs every mod's `initialize()` to have already run, or to flush
state before the process goes away, without hard-coding a load-order
dependency just to get a callback at the right moment.

## Gotchas

- `MOD_INFO` really must be a literal - `ast.literal_eval` chokes on anything
  computed, including something as harmless-looking as
  `MOD_INFO = {"id": "x", "version": get_version()}`.
- A disabled mod (`"enabled": False`) isn't merely skipped, it's absent from
  the dependency graph entirely - anything still declaring it as a dependency
  fails resolution with "unmet dependency", not a warning.
- `register_hook`/`Event.subscribe` raise `ModError` if you try to register
  something owned by a mod that isn't currently `"loading"` or `"loaded"` -
  most commonly hit by holding onto a reference to some other mod's function
  and calling it after that mod has already started unloading.
- `call_original` doesn't just skip *your* remaining handling, it skips every
  hook below you in priority order too. If you only meant to bypass the
  default behavior for your own logic, you probably wanted `call_next`.
- `reload_mod` on a mod nothing else depends on is safe with `cascade=False`
  (the default); the moment something depends on it, you need
  `cascade=True` or it refuses with "required by ...".
- Unloading evicts a mod's module *and every submodule* from `sys.modules`,
  but never touches native HL instances still alive from before the reload -
  they keep running with the class and closures they were built with. See
  [Known issues](./known-issues.md) for the practical fallout.

## See also

- [Developing outside the mods directory](./external-mods.md) - `HLMOD_EXTRA_MODS`/`HLMOD_MODS_DIR`, which directories the sorter actually searches.
- [Harmony-style patches](./harmony-patches.md) - `patch`/`prefix_hook`/`postfix_hook`, which share the exact same per-findex chain and priority ordering hooks use.
- [Hooking native functions](./native-hooks.md) - what `register_hook` does differently when the target is a `@:hlNative` function instead of bytecode.
- [Dev loop](./dev-loop.md) - the hot-reload workflow built on `reload_mod`.
- [Global configuration](./configuration.md) - `modcore.config`, for mod settings that need to outlive a reload.
- [Known issues](./known-issues.md) - what reloading does and doesn't fix up on live native objects.
