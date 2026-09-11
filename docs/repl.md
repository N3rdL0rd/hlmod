---
sidebar_position: 7
---

# REPL

Setting `HLMOD_REPL_PORT` starts an interactive Python session on a TCP socket, running inside the game, on a background thread, for as long as the game is alive as a way to poke at a live process without restarting it.

```sh
HLMOD_REPL_PORT=4711 hl game.hl
```

Connect with anything that speaks raw TCP - `nc 127.0.0.1 4711`, a `telnetlib` script, whatever's lying around - and you get a prompt:

```
$ nc 127.0.0.1 4711
hlmod REPL. Type Python, or one of: help, mods, hooks.
>>> 1 + 1
2
>>> import hlmod
>>> hlmod.gc_stats()
{'total_allocated': 41823744, 'allocation_count': 128841, 'current_memory': 52428800}
```

## Why a background thread?

The REPL server runs on its own OS thread, started right after mods finish loading, independently of the game's main HL thread. That's a deliberate choice: a REPL that only works when the game happens to be paused at a breakpoint is a debugger, not a REPL. Wiring this up meant reaching for HL's own socket primitives (`hl_socket_*`) rather than raw BSD sockets, which turned out to already have a template to copy - HL's own remote debugger (`debugger.c`) runs exactly this shape of background accept-loop thread, GC-rooting its listening and client sockets so the collector doesn't reclaim them out from under a thread it can't see into otherwise. The REPL server is close to a straight port of that pattern, aimed at a Python prompt instead of a debug protocol.

Each connection acquires the GIL only for the duration of a single command - `hl_blocking(true)` around the wait, `PyGILState_Ensure()` to actually take it, then release and go back to blocking before the next socket read - so a REPL session sitting idle at a prompt costs nothing and blocks nothing else in the process.

## What you actually get

Each connection gets its own persistent namespace, backed by a real `code.InteractiveInterpreter`, which means it behaves exactly like `python3 -i`:

- Expressions auto-print their `repr()`.
- Multi-line blocks (`def`, `if`, `for`, ...) buffer across lines and wait for the blank line that closes them, with a `... ` continuation prompt in the meantime.
- Uncaught exceptions print a traceback and land you back at the prompt - they don't drop the connection.
- `exit()`/`quit()` are caught and politely declined; disconnecting is how you leave. Letting them propagate as `SystemExit` across the C/Python boundary is exactly the kind of thing that goes wrong in interesting ways, so the REPL backend (`modcore._repl`) swallows it explicitly.

Two connections never share state. Assign `x = 1` in one terminal and open a second one, and `x` is a clean `NameError` there - each connection's namespace is its own dictionary, torn down when the connection closes.

A handful of shorthand commands are checked before a line is handed to the interpreter, for the things you'd otherwise have to `import` modcore internals to see:

| Command | Shows |
| --- | --- |
| `help` | The list of shorthand commands |
| `mods` | Every loaded mod, its lifecycle state, and its dependencies |
| `hooks` | Every registered native hook: function index, priority, owning mod, and the callback itself |

These read `modcore`'s own internal registries directly (the mod table in `_lifecycle`, the hook chain table in `_hooks`), so what you see is exactly the live state the framework is operating on, not a snapshot or an approximation.

```
>>> mods
modcore [loaded] deps=[]
my_weapon_mod [loaded] deps=['modcore']
>>> hooks
findex=1042 priority=0 owner=my_weapon_mod callback=<function on_create at 0x7f2b1c0a5da0>
```

## Security posture

The REPL binds to `127.0.0.1` and nothing else - there is no configuration option to expose it more broadly, on purpose. It runs arbitrary Python inside the game process with no authentication beyond "can open a TCP connection to this machine," which is a fine trust boundary for the machine you're developing on and a catastrophic one for anything reachable from a network. Omitting `HLMOD_REPL_PORT` never starts the listener at all, so shipping a mod that happens to link against a build with this feature compiled in does not, by itself, expose anything.

## Shutdown

Closing the game while a REPL client is connected has to not hang, which is a more interesting problem than it sounds: a thread blocked in a socket read doesn't notice a shutdown flag being set. hlmod handles this by closing both the listening socket and any active client socket during shutdown, then waiting - with a hard two-second cap, never indefinitely - for the accept loop to notice and exit before Python itself finalizes. An idle REPL client left connected when the game exits gets disconnected as part of that sequence; it doesn't need to be closed by hand first.
