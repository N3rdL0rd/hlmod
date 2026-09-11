---
sidebar_position: 7
---

# REPL

Setting `HLMOD_REPL_PORT` starts a loopback-only TCP REPL alongside the game,
in a background thread that runs independently of the main HL thread:

```sh
HLMOD_REPL_PORT=4711 hl game.hl
```

Connect with any raw TCP client, for example `nc 127.0.0.1 4711`. Each
connection gets its own persistent namespace and behaves like `python3 -i`:
expressions auto-print, multi-line `def`/`if` blocks buffer until a blank
line closes them, and exceptions print a traceback instead of dropping the
connection. A few shorthand commands are checked before falling back to
Python:

- `help` - lists the shorthand commands
- `mods` - every loaded mod, its state and dependencies
- `hooks` - every registered native hook, its owning mod and priority

The REPL only binds to `127.0.0.1` - it is never reachable from the network -
and it is entirely optional: omitting `HLMOD_REPL_PORT` never starts it.
