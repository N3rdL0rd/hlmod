"""Minimal TOML writer.

`tomllib` (stdlib, 3.11+) only reads TOML; hlmod's config (`_config.py`)
needs to write it back out too. Rather than bundle a third-party TOML
library for round-tripping small, plain-data config files, this ships a
narrow writer covering exactly the value shapes `tomllib` reads back:
bool, int, float, str, list, and nested dict-as-table. It is not a
general-purpose TOML library - correctness is verified by round-tripping
through `tomllib.loads` in tests, not by TOML-spec completeness.
"""

from __future__ import annotations

from typing import Any

_BARE_KEY_CHARS = frozenset(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-"
)


def _format_key(key: str) -> str:
    if key and all(c in _BARE_KEY_CHARS for c in key):
        return key
    return _format_string(key)


def _format_string(value: str) -> str:
    escaped = (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\t", "\\t")
        .replace("\r", "\\r")
    )
    return f'"{escaped}"'


def _format_scalar(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if value != value:
            return "nan"
        if value in (float("inf"), float("-inf")):
            return "inf" if value > 0 else "-inf"
        return repr(value)
    if isinstance(value, str):
        return _format_string(value)
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(_format_scalar(item) for item in value) + "]"
    if isinstance(value, dict):
        items = ", ".join(f"{_format_key(k)} = {_format_scalar(v)}" for k, v in value.items())
        return "{" + items + "}"
    raise TypeError(f"Value of type {type(value).__name__!r} is not TOML-serializable: {value!r}")


def dumps(data: dict[str, Any]) -> str:
    """Serializes a nested dict of TOML-representable values to TOML text."""
    lines: list[str] = []
    _dump_table(data, (), lines)
    return "\n".join(lines) + ("\n" if lines else "")


def _dump_table(table: dict[str, Any], path: tuple[str, ...], lines: list[str]) -> None:
    scalars = {k: v for k, v in table.items() if not isinstance(v, dict)}
    subtables = {k: v for k, v in table.items() if isinstance(v, dict)}
    if path:
        if lines:
            lines.append("")
        lines.append("[" + ".".join(_format_key(p) for p in path) + "]")
    for key, value in scalars.items():
        lines.append(f"{_format_key(key)} = {_format_scalar(value)}")
    for key, value in subtables.items():
        _dump_table(value, path + (key,), lines)
