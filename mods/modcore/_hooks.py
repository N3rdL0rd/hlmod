"""One native dispatcher per function, composed from removable Python hooks."""

from collections.abc import Sequence
from importlib import import_module
from inspect import Parameter, Signature, signature
from typing import Any, Callable, Generic, ParamSpec, TypeVar

from ._lifecycle import Mod, Registration, _activate

P = ParamSpec("P")
R = TypeVar("R")


class HookContext(Generic[P, R]):
    def __init__(self, findex: int, native: Any, snapshot: tuple, index: int,
                 target_signature: Signature | None):
        self.findex = findex
        self._native = native
        self._snapshot = snapshot
        self._index = index
        self._target_signature = target_signature

    def call_next(self, /, *args: P.args, **kwargs: P.kwargs) -> R:
        if kwargs:
            args = self._positional_args(args, kwargs)
        return _invoke(self.findex, self._native, self._snapshot, self._index, args)

    def call_original(self, /, *args: P.args, **kwargs: P.kwargs) -> R:
        if kwargs:
            args = self._positional_args(args, kwargs)
        return self._native.call_original(*args)

    def _positional_args(self, args: tuple, kwargs: dict) -> tuple:
        if self._target_signature is None:
            raise TypeError("Keyword hook arguments require a generated callable target; "
                            "name/index targets accept positional arguments only")
        bound = self._target_signature.bind(*args, **kwargs)
        bound.apply_defaults()
        return bound.args


def _invoke(findex: int, native: Any, snapshot: tuple, index: int, args: tuple):
    if index == len(snapshot):
        return native.call_original(*args)
    _, callback, registration, target_signature = snapshot[index]
    context = HookContext(findex, native, snapshot, index + 1, target_signature)
    with _activate(registration.owner):
        try:
            return callback(context, *args)
        except BaseException as error:
            owner = registration.owner.id if registration.owner is not None else "<unowned>"
            error.add_note(f"Hook findex {findex}, mod {owner!r}")
            # The native bridge propagates this failure; never retry the original
            # here, since this callback may already have invoked it via next.
            raise


class _HookChain:
    def __init__(self, findex: int, native: Any):
        self.findex = findex
        self.native = native
        self.entries: tuple = ()
        # Keep a stable bound-method identity for conditional native unregister.
        self.dispatcher = self.dispatch

    def dispatch(self, native_context: Any, *args):
        return _invoke(self.findex, native_context, self.entries, 0, args)


_chains: dict[int, _HookChain] = {}


def _targets(target, native) -> tuple[int, ...]:
    if isinstance(target, str):
        indices = (native.findex_for_name(target),)
    elif isinstance(target, int):
        indices = (target,)
    elif callable(target):
        if getattr(target, "__self__", None) is not None:
            raise TypeError("Bound method hook targets are not supported; use Class.method "
                            "so the native receiver remains an explicit argument")
        index = getattr(target, "__hl_findex__", None)
        if not isinstance(index, int):
            raise TypeError("Callable hook targets require integer __hl_findex__ metadata")
        indices = (index,)
    elif isinstance(target, Sequence):
        indices = tuple(target)
    else:
        raise TypeError("Hook target must be a name, findex, sequence of findexes, or generated method")
    if not indices or any(not isinstance(index, int) or index < 0 for index in indices):
        raise ValueError("Hook target must contain nonnegative integer function indices")
    return tuple(dict.fromkeys(indices))


def register_hook(target, callback: Callable, *, priority: int = 0,
                  owner: Mod | None = None) -> Registration:
    if not callable(callback):
        raise TypeError("Hook callback must be callable")
    if not isinstance(priority, int):
        raise TypeError("Hook priority must be an integer")
    # Events/lifecycle work outside the embedded native runtime.
    native = import_module("hlmod")
    indices = _targets(target, native)
    target_signature = signature(target) if callable(target) else None
    if target_signature is not None and any(
        parameter.kind in (Parameter.KEYWORD_ONLY, Parameter.VAR_KEYWORD)
        for parameter in target_signature.parameters.values()
    ):
        raise TypeError("Native hook targets cannot have keyword-only parameters or **kwargs")
    installed: list[_HookChain] = []

    def remove() -> None:
        errors: list[BaseException] = []
        for chain in reversed(installed):
            chain.entries = tuple(item for item in chain.entries if item[2] is not registration)
            if not chain.entries:
                try:
                    chain.native.unregister_hook(chain.findex, chain.dispatcher)
                except BaseException as error:
                    errors.append(error)
                finally:
                    _chains.pop(chain.findex, None)
        installed.clear()
        if errors:
            raise BaseExceptionGroup("Errors removing native hook dispatchers", errors)

    registration = Registration(remove, owner=owner)
    try:
        for findex in indices:
            chain = _chains.get(findex)
            if chain is None:
                chain = _HookChain(findex, native)
                native.register_hook(findex, chain.dispatcher)
                _chains[findex] = chain
            installed.append(chain)
            entries = chain.entries
            index = next((i for i, item in enumerate(entries) if item[0] < priority), len(entries))
            entry = (priority, callback, registration, target_signature)
            chain.entries = entries[:index] + (entry,) + entries[index:]
    except BaseException as error:
        try:
            registration.close()
        except BaseException as cleanup_error:
            error.add_note(f"Hook registration rollback failed: {cleanup_error}")
        raise
    return registration


def hook(target, *, priority: int = 0, owner: Mod | None = None):
    def decorator(callback: Callable) -> Callable:
        register_hook(target, callback, priority=priority, owner=owner)
        return callback
    return decorator
