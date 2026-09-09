"""Common modding routines for HashLink games."""

from importlib import import_module
from pathlib import Path

from ._events import Event, mods_loaded, shutting_down
from ._hooks import HookContext, hook, register_hook
from ._lifecycle import (
    Mod,
    ModError,
    Registration,
    current_mod,
    finish_loading,
    load_mod,
    reload_mod,
    shutdown,
    unload_mod,
)

MOD_INFO = {
    "id": "modcore",
    "name": "hlmod Modding Core",
    "description": "Core utilities, tools, and functions for instrumenting HashLink.",
    "version": "0.0.1",
    "dependencies": [],
}

__all__ = [
    "Event", "HookContext", "Mod", "ModError", "Registration", "current_mod",
    "finish_loading", "hook", "load_all_stubs", "load_mod", "mods_loaded",
    "register_hook", "reload_mod", "shutdown", "shutting_down", "unload_mod",
]


def load_all_stubs(base_dir: str = "./mods/stubs") -> None:
    """Import generated runtime modules/packages, never editor stubs or cache data."""
    root = Path(base_dir)
    import_module("stubs")
    for path in sorted(root.rglob("*.py")):
        parts = path.relative_to(root).with_suffix("").parts
        if "__pycache__" in parts or any(not part.isidentifier() for part in parts):
            continue
        if parts[-1] == "__init__":
            parts = parts[:-1]
        if parts:
            import_module("stubs." + ".".join(parts))
