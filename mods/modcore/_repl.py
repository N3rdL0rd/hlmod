"""Line-oriented backend for hlmod's native REPL server (see hlmod_repl.c).

Each TCP connection gets its own persistent namespace and its own
`code.InteractiveInterpreter`, exactly like `python3 -i`: single-line
statements/expressions run immediately, and multi-line compound statements
(`if ...:`, `def ...:`) are buffered until complete. A handful of shorthand
commands are checked first for quick introspection without importing
anything by hand; everything else is evaluated as Python. `open_connection`,
`handle_line`, and `close_connection` are called only from the native REPL
thread, under the GIL - never call these directly from a mod.
"""

import code
import io
import traceback
from contextlib import redirect_stderr, redirect_stdout
from typing import Any

from . import _hooks, _lifecycle

_PROMPT = ">>> "
_CONTINUATION_PROMPT = "... "
_BANNER = "hlmod REPL. Type Python, or one of: help, mods, hooks.\n"


class _Connection:
    __slots__ = ("namespace", "interpreter", "buffer")

    def __init__(self) -> None:
        self.namespace: dict[str, Any] = {"__name__": "__hlmod_repl__"}
        self.interpreter = code.InteractiveInterpreter(self.namespace)
        self.buffer: list[str] = []


_connections: dict[int, _Connection] = {}


def _list_mods() -> str:
    if not _lifecycle._mods:
        return "(no mods loaded)\n"
    return "".join(
        f"{mod.id} [{mod.state}] deps={list(mod.dependencies)}\n"
        for mod in _lifecycle._mods.values()
    )


def _list_hooks() -> str:
    if not _hooks._chains:
        return "(no native hooks registered)\n"
    lines = []
    for findex, chain in sorted(_hooks._chains.items()):
        for priority, callback, registration, _ in chain.entries:
            owner = registration.owner.id if registration.owner is not None else "<unowned>"
            lines.append(f"findex={findex} priority={priority} owner={owner} callback={callback!r}\n")
    return "".join(lines)


_COMMANDS = {
    "help": lambda: "Commands: help, mods, hooks. Anything else is evaluated as Python.\n",
    "mods": _list_mods,
    "hooks": _list_hooks,
}


def open_connection(connection_id: int) -> str:
    _connections[connection_id] = _Connection()
    return _BANNER + _PROMPT


def close_connection(connection_id: int) -> None:
    _connections.pop(connection_id, None)


def handle_line(connection_id: int, line: str) -> str:
    connection = _connections.get(connection_id)
    if connection is None:
        return ""  # closed from under us (e.g. shutdown mid-line); nothing to say

    stripped = line.strip()
    if not connection.buffer and stripped in _COMMANDS:
        return _COMMANDS[stripped]() + _PROMPT

    connection.buffer.append(line)
    source = "\n".join(connection.buffer)
    output = io.StringIO()
    try:
        with redirect_stdout(output), redirect_stderr(output):
            needs_more = connection.interpreter.runsource(source, "<hlmod-repl>")
    except SystemExit:
        # exit()/quit() would otherwise propagate as a GIL-boundary error;
        # disconnecting is the REPL's actual exit mechanism.
        connection.buffer.clear()
        return "exit()/quit() are disabled here; disconnect instead.\n" + _PROMPT
    except BaseException:
        connection.buffer.clear()
        return traceback.format_exc() + _PROMPT

    if needs_more:
        return output.getvalue() + _CONTINUATION_PROMPT
    connection.buffer.clear()
    return output.getvalue() + _PROMPT
