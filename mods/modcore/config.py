"""Global hlmod configuration, backed by a single TOML file (not JSON).

One file - `hlmod.toml`, next to the game's working directory by default -
with one top-level table per mod, so unrelated mods can't collide on keys.
`tomllib` (stdlib since 3.11) reads it; hlmod ships its own minimal TOML
writer (`_toml_writer.py`) to save it back out, since `tomllib` is read-only
and this avoids bundling a third-party dependency just for round-tripping
small, plain-data config files.
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

from ._events import shutting_down
from ._lifecycle import current_mod
from ._toml_writer import dumps as _dumps

_path = Path("hlmod.toml")
_data: dict[str, Any] | None = None
_dirty = False


def set_path(path: str | Path) -> None:
    """Overrides the config file location. Must be called before the first
    `section()`/`load()` call; existing in-memory state is discarded."""
    global _path, _data, _dirty
    _path = Path(path)
    _data = None
    _dirty = False


def _load() -> dict[str, Any]:
    global _data
    if _data is None:
        if _path.exists():
            with _path.open("rb") as file:
                _data = tomllib.load(file)
        else:
            _data = {}
    return _data


def _mark_dirty() -> None:
    global _dirty
    _dirty = True


def save() -> None:
    """Writes the config file if anything has changed since the last save."""
    global _dirty
    if not _dirty or _data is None:
        return
    _path.write_text(_dumps(_data), encoding="utf-8")
    _dirty = False


@shutting_down.listen()
def _autosave() -> None:
    save()


class Section:
    """A mutable, dict-like view onto one mod's top-level TOML table."""

    def __init__(self, name: str, table: dict[str, Any]):
        self.name = name
        self._table = table

    def __getitem__(self, key: str) -> Any:
        return self._table[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self._table[key] = value
        _mark_dirty()

    def __delitem__(self, key: str) -> None:
        del self._table[key]
        _mark_dirty()

    def __contains__(self, key: str) -> bool:
        return key in self._table

    def __iter__(self):
        return iter(self._table)

    def __len__(self) -> int:
        return len(self._table)

    def get(self, key: str, default: Any = None) -> Any:
        return self._table.get(key, default)

    def setdefault(self, key: str, default: Any) -> Any:
        if key not in self._table:
            _mark_dirty()
        return self._table.setdefault(key, default)

    def as_dict(self) -> dict[str, Any]:
        return dict(self._table)

    def save(self) -> None:
        save()


def section(name: str | None = None, *, defaults: dict[str, Any] | None = None) -> Section:
    """Gets (creating if needed) a mod's config section. `name` defaults to
    the currently-loading mod's id, so a mod typically just calls
    `config.section(defaults={...})` during `initialize()`. Any key present
    in `defaults` but missing from the file is filled in and marked dirty,
    so a fresh install always gets a complete, saved config on first exit."""
    if name is None:
        mod = current_mod()
        if mod is None:
            raise RuntimeError(
                "config.section() needs an explicit name outside of a mod's initialize()"
            )
        name = mod.id
    data = _load()
    table = data.get(name)
    if not isinstance(table, dict):
        table = {}
        data[name] = table
        _mark_dirty()
    if defaults:
        for key, value in defaults.items():
            if key not in table:
                table[key] = value
                _mark_dirty()
    return Section(name, table)


__all__ = ["Section", "save", "section", "set_path"]
