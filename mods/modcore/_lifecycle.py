"""Owned registrations and dependency-ordered Python mod lifecycle."""

from contextlib import contextmanager
from contextvars import ContextVar
from importlib import import_module, invalidate_caches
import sys
from types import ModuleType
from typing import Callable, Iterator


class ModError(RuntimeError):
    def __init__(self, mod_id: str, operation: str, message: str):
        self.mod_id = mod_id
        self.operation = operation
        super().__init__(f"Mod {mod_id!r} {operation}: {message}")


class Mod:
    def __init__(self, mod_id: str, module_name: str, dependencies: tuple[str, ...] = ()):
        self.id = mod_id
        self.module_name = module_name
        self.dependencies = dependencies
        self.module: ModuleType | None = None
        self.state = "loading"
        self._registrations: list[Registration] = []


_current: ContextVar[Mod | None] = ContextVar("modcore_owner", default=None)
_mods: dict[str, Mod] = {}
_finished = False
_shutting_down = False
_shutdown_complete = False


def current_mod() -> Mod | None:
    return _current.get()


@contextmanager
def _activate(owner: Mod | None) -> Iterator[None]:
    token = _current.set(owner)
    try:
        yield
    finally:
        _current.reset(token)


class Registration:
    """An idempotently removable resource, retained by its owning mod."""

    def __init__(self, close: Callable[[], None], *, owner: Mod | None = None):
        self.owner = current_mod() if owner is None else owner
        self._close: Callable[[], None] | None = close
        if self.owner is not None:
            if self.owner.state not in ("loading", "loaded"):
                raise ModError(self.owner.id, "register", "owner is not active")
            self.owner._registrations.append(self)

    @property
    def closed(self) -> bool:
        return self._close is None

    def close(self) -> None:
        close = self._close
        if close is None:
            return
        self._close = None
        if self.owner is not None:
            self.owner._registrations.remove(self)
        with _activate(self.owner):
            close()

    def __enter__(self) -> "Registration":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()


def _cleanup(mod: Mod) -> list[BaseException]:
    errors: list[BaseException] = []
    while mod._registrations:
        registration = mod._registrations[-1]
        try:
            registration.close()
        except BaseException as error:
            error.add_note(f"While removing a registration owned by mod {mod.id!r}")
            errors.append(error)
    return errors


def _remove_namespace(module_name: str) -> None:
    # Never clear other libraries or modules merely imported by this mod.
    # The framework owns these singletons for the entire interpreter lifetime.
    if module_name == __package__:
        return
    for name in tuple(sys.modules):
        if name == module_name or name.startswith(module_name + "."):
            module = sys.modules.pop(name)
            parent_name, _, child_name = name.rpartition(".")
            parent = sys.modules.get(parent_name)
            if parent is not None and getattr(parent, child_name, None) is module:
                delattr(parent, child_name)


def load_mod(mod_id: str, module_name: str, dependencies=()) -> Mod:
    """Import and initialize once under an owner; roll back resources on failure."""
    global _finished, _shutdown_complete
    dependencies = tuple(dict.fromkeys(dependencies))
    if _shutting_down:
        raise ModError(mod_id, "load", "framework is shutting down")
    if mod_id in _mods:
        raise ModError(mod_id, "load", "already loaded or loading")
    for other in _mods.values():
        if other.module_name == module_name:
            raise ModError(mod_id, "load", f"module already managed by {other.id!r}")
    for dependency in dependencies:
        if dependency == mod_id:
            raise ModError(mod_id, "load", "dependency cycle")
        required = _mods.get(dependency)
        if required is None:
            raise ModError(mod_id, "load", f"dependency {dependency!r} is not loaded")
        if required.state != "loaded":
            raise ModError(mod_id, "load", f"dependency {dependency!r} is {required.state}; possible cycle")
    mod = Mod(mod_id, module_name, dependencies)
    _mods[mod_id] = mod
    try:
        with _activate(mod):
            mod.module = import_module(module_name)
            initialize = getattr(mod.module, "initialize", None)
            if initialize is not None:
                initialize()
        mod.state = "loaded"
    except BaseException as error:
        mod.state = "unloading"
        cleanup_errors = _cleanup(mod)
        _mods.pop(mod_id, None)
        _remove_namespace(module_name)
        mod.state = "unloaded"
        if cleanup_errors:
            error.add_note("Registration rollback also failed: " + "; ".join(map(str, cleanup_errors)))
        if isinstance(error, Exception):
            raise ModError(mod_id, "load", "import or initialize failed") from error
        error.add_note(f"While loading mod {mod_id!r}")
        raise
    _finished = False
    _shutdown_complete = False
    return mod


def _unload_order(mod_id: str, cascade: bool) -> list[Mod]:
    mod = _mods.get(mod_id)
    if mod is None:
        raise ModError(mod_id, "unload", "not loaded")
    order: list[Mod] = []
    visited: set[str] = set()

    def visit(current: Mod) -> None:
        if current.id in visited:
            return
        visited.add(current.id)
        if current.state != "loaded":
            raise ModError(current.id, "unload", f"mod is {current.state}")
        dependents = [item for item in _mods.values() if current.id in item.dependencies]
        if dependents and not cascade:
            names = ", ".join(item.id for item in dependents)
            raise ModError(current.id, "unload", f"required by {names}")
        for dependent in reversed(dependents):
            visit(dependent)
        order.append(current)

    visit(mod)
    return order


def _unload(mod: Mod) -> list[BaseException]:
    mod.state = "unloading"
    errors: list[BaseException] = []
    try:
        with _activate(mod):
            callback = getattr(mod.module, "shutdown", None)
            if callback is not None and callback is not shutdown:
                callback()
    except BaseException as error:
        error.add_note(f"While shutting down mod {mod.id!r}")
        errors.append(error)
    finally:
        errors.extend(_cleanup(mod))
        _mods.pop(mod.id, None)
        _remove_namespace(mod.module_name)
        mod.state = "unloaded"
    return errors


def unload_mod(mod_id: str, *, cascade: bool = False) -> None:
    """Detach Python resources, not live native instances or their old Python code."""
    errors: list[BaseException] = []
    order = _unload_order(mod_id, cascade)
    # Reserve the entire dependency closure before user shutdown callbacks can
    # try to load new dependents or recursively unload a pending member.
    for mod in order:
        mod.state = "unloading"
    for mod in order:
        errors.extend(_unload(mod))
    if errors:
        raise BaseExceptionGroup(f"Errors unloading mod {mod_id!r}", errors)


def reload_mod(mod_id: str, *, cascade: bool = False) -> Mod:
    """Reload managed namespaces; existing native instances retain their old code."""
    order = _unload_order(mod_id, cascade)
    if any(mod.module_name == __package__ for mod in order):
        raise ModError(mod_id, "reload", "the framework cannot reload itself")
    specs = [(mod.id, mod.module_name, mod.dependencies) for mod in reversed(order)]
    unload_mod(mod_id, cascade=cascade)
    invalidate_caches()
    loaded: list[Mod] = []
    try:
        for identifier, module_name, dependencies in specs:
            loaded.append(load_mod(identifier, module_name, dependencies))
    except BaseException as error:
        for mod in reversed(loaded):
            for cleanup_error in _unload(mod):
                error.add_note(f"Reload rollback failed: {cleanup_error}")
        raise
    return _mods[mod_id]


def finish_loading() -> None:
    """Emit the framework's mod-loading phase, not Haxe application readiness."""
    global _finished
    if _finished:
        return
    if any(mod.state != "loaded" for mod in _mods.values()):
        raise RuntimeError("Cannot finish loading while a mod is initializing or unloading")
    _finished = True
    from ._events import mods_loaded
    mods_loaded.emit()


def shutdown() -> None:
    """Broadcast teardown, then release mods in reverse dependency/load order."""
    global _shutting_down, _finished, _shutdown_complete
    if _shutting_down or _shutdown_complete:
        return
    if any(mod.state != "loaded" for mod in _mods.values()):
        raise RuntimeError("Cannot shut down while a mod is initializing or unloading")
    _shutting_down = True
    errors: list[BaseException] = []
    try:
        from ._events import shutting_down
        try:
            shutting_down.emit()
        except BaseException as error:
            errors.append(error)
        for mod in reversed(tuple(_mods.values())):
            if mod.id in _mods:
                errors.extend(_unload(mod))
    finally:
        _shutting_down = False
        _finished = False
        _shutdown_complete = True
    if errors:
        raise BaseExceptionGroup("Errors shutting down mods", errors)
