---
sidebar_position: 9
---

# Harmony-style patches

`modcore.prefix_hook`/`postfix_hook`/`patch` give you the C# Harmony
`[HarmonyPatch] class { static bool Prefix(...); static void Postfix(...); }`
convention, because a lot of people already know it and it's a genuinely
convenient shape for "run some code before/after this function, and maybe
veto or rewrite what happens." But it isn't a second patching engine bolted
onto hlmod next to `hook()` - it's sugar that installs one ordinary entry on
the exact same per-findex chain `hook()`/`register_hook` use (see
[Mods, hooks and events](./mods-hooks-events.md)). Read `_harmony.py` and
you'll find it's about ninety lines, most of which is docstring.

```python
from modcore import patch, postfix_hook, prefix_hook

@prefix_hook(Weapon.create, priority=10)
def reject_locked(hero, item):
    if not hero.hasUnlocked(item):
        return False  # skip the original and every lower-priority hook/patch

@postfix_hook(Weapon.create, priority=0)
def log_result(result, hero, item):
    log(f"created {result}")

@patch(Weapon.create, priority=5)
class DoubleDamage:
    @staticmethod
    def postfix(result, hero, item):
        result.damage *= 2
```

## The mechanism: it's just `register_hook` with a wrapper callback

There is no separate prefix list, postfix list, or patch registry anywhere
in hlmod. `prefix_hook`, `postfix_hook`, and `patch` all funnel through the
same private helper, `_adapter(prefix, postfix)`, which builds one ordinary
hook callback closing over whichever of the two you supplied:

```python
def _adapter(prefix, postfix):
    def run(context: HookContext, *args):
        call_args = args
        run_original = True
        if prefix is not None:
            outcome = prefix(*call_args)
            if outcome is False:
                run_original = False
            elif outcome is not None:
                call_args = outcome  # must be a tuple, else TypeError
        result = context.call_next(*call_args) if run_original else None
        if postfix is not None:
            replacement = postfix(result, *call_args)
            if replacement is not None:
                result = replacement
        return result
    return run
```

`run` has exactly the signature `hook()` expects - `(context: HookContext,
*args)` - and each decorator just hands it straight to `register_hook`:

- `prefix_hook(target, ...)` calls `register_hook(target, _adapter(callback,
  None), priority=priority, owner=owner)`.
- `postfix_hook(target, ...)` calls `register_hook(target, _adapter(None,
  callback), priority=priority, owner=owner)`.
- `patch(target, ...)` resolves `prefix`/`postfix` off the decorated class
  and calls `register_hook(target, _adapter(prefix, postfix), priority=priority,
  owner=owner)` once, stashing the returned `Registration` on
  `cls._hlmod_patch_registration` so you can close it manually if you ever
  need to (same `Registration` object `hook()` and `register_hook` return
  elsewhere).

That's it. There's exactly one entry inserted into the chain per
`prefix_hook`/`postfix_hook` call and per `@patch` class, sorted into
`_HookChain.entries` by the same `(priority, then registration order)` rule
every other hook uses. From the chain's point of view a patch is just
another callback; it has no idea prefixes and postfixes exist.

**A crucial consequence of this**: because `run` only ever calls
`context.call_next(...)` (or doesn't), your prefix and postfix functions
never receive the `HookContext` themselves. `prefix_hook`'s callback sees
`(*args)`, and `postfix_hook`'s sees `(result, *args)` - no `context`
argument at all. A plain `hook()` callback can call `context.call_original()`
to jump straight past every remaining entry in the chain; a prefix/postfix
has no equivalent escape hatch. It can only ask the adapter to continue the
chain (by not returning `False`) or stop it (by returning `False`), nothing
finer-grained.

## Writing a prefix or postfix directly

```python
@prefix_hook(Weapon.create, priority=10)
def fn(*args) -> None | Literal[False] | tuple[Any, ...]: ...

@postfix_hook(Weapon.create, priority=0)
def fn(result, *args) -> Any | None: ...
```

Prefix return values, read straight off `_adapter.run`:

- `False` (identity check, not merely falsy) - skip `context.call_next`
  entirely for this entry. `call_args` is left as the *original* incoming
  arguments (a `False` return doesn't also rewrite them), `result` becomes
  `None`, and the postfix - if this same patch has one - still runs with
  that `None` result.
- a `tuple` - replaces the positional arguments passed to `context.call_next`
  *and* to this patch's own postfix. Anything non-`None`, non-`False`,
  non-`tuple` raises `TypeError`.
- `None` - continue with the arguments unchanged.

Postfix always runs if present, whether or not a prefix on the same patch
vetoed the call: `postfix(result, *call_args)` is called with whatever
`result` is at that point (the real return value, or `None` after a skip)
and the same `call_args` the prefix left behind. Returning a non-`None`
value replaces `result`; returning `None` leaves it as-is. There's no way
for a postfix to distinguish "the original returned `None`" from "a prefix
skipped it" other than checking `result is None` yourself - the adapter
doesn't pass that information along.

## What a `@patch` class needs to look like

```python
@patch(Weapon.create, priority=5)
class ChargeCost:
    @staticmethod
    def prefix(hero, item):
        if hero.charge < item.cost:
            return False
        return (hero, item)

    @staticmethod
    def postfix(result, hero, item):
        if result is not None:
            hero.charge -= item.cost
        return result
```

`patch` looks up `prefix` and `postfix` with a private `_resolve(cls, name)`
helper, and the rules it enforces are worth knowing exactly:

- **Both are optional, but not both absent.** `_resolve` returns `None` for
  a missing attribute, and if *both* come back `None` the decorator raises
  `TypeError: Patch class 'Name' defines neither prefix nor postfix` right
  at decoration time. A patch with only a postfix (like `DoubleDamage`
  above) or only a prefix is completely normal.
- **`@staticmethod` or a plain function, not `@classmethod`.** `_resolve`
  reads `cls.__dict__.get(name)` directly - it does *not* go through
  `getattr`/the descriptor protocol - so it gets the raw object sitting in
  the class body. A `staticmethod` gets unwrapped via `.__func__`; a plain
  `def prefix(hero, item): ...` with no decorator comes back as a bare
  function and gets called directly with `(*call_args)`, which is exactly
  why the docstring says "plain function or `@staticmethod`" are
  interchangeable here - neither one goes through instance binding, so
  there's no implicit `self` to worry about either way. A `classmethod` is
  rejected outright with `TypeError: {cls}.{name} must be a plain function
  or @staticmethod, not @classmethod`, and anything present but not callable
  raises `TypeError: {cls}.{name} must be callable`.
- **Reading `cls.__dict__` means no inheritance.** If you write a base class
  with a `prefix` and subclass it without redefining `prefix` in the
  subclass's own body, `@patch` on the subclass won't see it - `__dict__`
  only holds what's defined directly on that class, not what it inherits.
  Define both `prefix` and `postfix` in the class you actually decorate.

## Composition versus plain `hook()`

The module docstring calls this out directly, and it's worth taking
seriously rather than assuming Harmony-familiar semantics: hlmod composes
every hook and every patch on one target into a **single linear chain**,
not independent prefix/postfix/transpiler lists the way C# Harmony does.
Concretely, a patch's prefix+postfix pair occupies exactly one slot in that
chain, at one priority, and "the rest of the chain" a skipping prefix cuts
off is *whatever sits at lower priority in that same chain* - which may be
another patch, a plain `hook()`, or the original function itself, in
whatever order `(priority, then registration order)` put them. There's
nothing chain-wide that distinguishes "this next entry happens to be a
patch" from "this next entry is a plain hook"; `_invoke` just walks the
`entries` tuple and calls whatever callable is sitting in each slot.

That has one very concrete implication worth spelling out: if a prefix's
patch is registered at a *higher* priority than a plain `hook()` on the same
target, and the prefix returns `False`, the plain hook never runs at all -
not skipped-and-notified, just never invoked, exactly as if it didn't
exist for that call, because `context.call_next()` (the only thing that
would reach it) is never called. If the ordering is reversed - the plain
`hook()` sits at higher priority - then it's the hook's own code that
decides the patch's fate the normal way any hook decides a lower-priority
entry's fate: call `context.call_next(...)` and the prefix/postfix pair
runs as usual, or call `context.call_original(...)` and it's skipped
entirely, same as skipping any other lower-priority hook. The patch gets no
special treatment either way - which is really just the module docstring's
point restated: prefix/postfix patches "interleave by priority exactly as
documented for `hook()`" because they *are* hook chain entries, not a
parallel mechanism the chain has to know about.

:::note
Errors propagate the same way too. If a prefix returns something that's
neither `None`, `False`, nor a `tuple`, `_adapter.run` raises `TypeError`
from inside the chain entry's callback - which `_invoke` catches, annotates
with the findex and owning mod, and re-raises, so it surfaces as the same
kind of catchable HL exception any raising `hook()` callback produces (see
[Mods, hooks and events](./mods-hooks-events.md)). It does not skip only
that patch; it aborts the whole call the same way any hook exception does.
:::

`patch`, `prefix_hook`, and `postfix_hook` all accept the same `priority`
and `owner` keywords `hook()` does, and behave identically with respect to
mod lifetime: pass `owner=` (or let it default the way `hook()` does) and
unloading that mod removes the registration - and therefore this chain
entry - the same way it removes a plain hook.

## See also

- [Mods, hooks and events](./mods-hooks-events.md) - the underlying
  `hook()`/`register_hook`/`HookContext` chain that patches are built on.
- [Design philosophy](./design-philosophy.md) - why `modcore` favors thin
  Python sugar like this over new native mechanism.
