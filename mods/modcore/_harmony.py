"""Harmony-style prefix/postfix patches, composed on the same native dispatch
chain as `hook`/`register_hook` (see `_hooks.py`). A patch is not a second,
independent hook mechanism: it is sugar that installs one ordinary chain entry
per patch, so plain hooks and prefix/postfix patches on the same target
interleave by priority exactly as documented for `hook()`.

Semantics (deliberately narrower than C# Harmony's flat multi-patch model,
because hlmod composes hooks as a single linear chain rather than independent
prefix/postfix lists - see the docstrings below for the exact contract):

- A prefix runs before the rest of the chain (and the real original). Returning
  `False` skips the rest of the chain *for this patch's link*: neither the
  next lower-priority hook/patch nor the original function runs, and the
  result is `None` unless a postfix on the same patch supplies one. Returning
  a tuple replaces the positional arguments passed onward. Returning `None`
  continues unchanged.
- A postfix runs after the rest of the chain returns (or after a same-patch
  prefix skipped it) and may replace the result by returning non-`None`.
- `@patch` bundles an optional prefix and postfix into one chain entry, so
  they always sit at the same priority and see each other's decisions,
  matching the C# `[HarmonyPatch] class { static bool Prefix(...); static void
  Postfix(...); }` unit.
"""

from typing import Callable

from ._hooks import HookContext, register_hook
from ._lifecycle import Mod


def _adapter(prefix: Callable | None, postfix: Callable | None):
    def run(context: HookContext, *args):
        call_args = args
        run_original = True
        if prefix is not None:
            outcome = prefix(*call_args)
            if outcome is False:
                run_original = False
            elif outcome is not None:
                if not isinstance(outcome, tuple):
                    raise TypeError(
                        "Prefix must return None, False, or a tuple of replacement "
                        f"positional arguments, got {outcome!r}"
                    )
                call_args = outcome
        result = context.call_next(*call_args) if run_original else None
        if postfix is not None:
            replacement = postfix(result, *call_args)
            if replacement is not None:
                result = replacement
        return result

    return run


def _resolve(cls: type, name: str) -> Callable | None:
    member = cls.__dict__.get(name)
    if member is None:
        return None
    if isinstance(member, staticmethod):
        return member.__func__
    if isinstance(member, classmethod):
        raise TypeError(
            f"{cls.__name__}.{name} must be a plain function or @staticmethod, not @classmethod"
        )
    if not callable(member):
        raise TypeError(f"{cls.__name__}.{name} must be callable")
    return member


def prefix_hook(target, *, priority: int = 0, owner: Mod | None = None):
    """Decorator: `def fn(*args) -> None | Literal[False] | tuple[Any, ...]`.

    Returning `False` skips the original call (and any lower-priority hook or
    patch on this target); returning a tuple replaces the positional
    arguments seen downstream; returning `None` continues unchanged.
    """

    def decorator(callback: Callable) -> Callable:
        register_hook(target, _adapter(callback, None), priority=priority, owner=owner)
        return callback

    return decorator


def postfix_hook(target, *, priority: int = 0, owner: Mod | None = None):
    """Decorator: `def fn(result, *args) -> Any | None`.

    A non-`None` return value replaces the result; returning `None` keeps the
    existing result (from the original, or from a same-patch prefix skip)
    unchanged.
    """

    def decorator(callback: Callable) -> Callable:
        register_hook(target, _adapter(None, callback), priority=priority, owner=owner)
        return callback

    return decorator


def patch(target, *, priority: int = 0, owner: Mod | None = None):
    """Class decorator mirroring C# Harmony's `[HarmonyPatch]` convention:
    decorate a class defining an optional `prefix`/`postfix` (plain function
    or `@staticmethod`, matching Harmony's static `Prefix`/`Postfix`). At
    least one of the two must be present.
    """

    def decorator(cls: type) -> type:
        prefix = _resolve(cls, "prefix")
        postfix = _resolve(cls, "postfix")
        if prefix is None and postfix is None:
            raise TypeError(f"Patch class {cls.__name__!r} defines neither prefix nor postfix")
        registration = register_hook(target, _adapter(prefix, postfix), priority=priority, owner=owner)
        cls._hlmod_patch_registration = registration
        return cls

    return decorator


__all__ = ["prefix_hook", "postfix_hook", "patch"]
