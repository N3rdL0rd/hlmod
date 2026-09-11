---
sidebar_position: 4
---

# Dev loop

Mods are plain Python with no compile step, so there is nothing to "build" -
the only friction in local iteration is noticing an edit and restarting `hl`
by hand. `tools/dev.py` closes that gap:

```sh
just dev game.hl      # or: python3 tools/dev.py game.hl --hl path/to/hl
```

It launches `hl game.hl`, watches your mod sources and a couple of config
files for changes, and restarts the process the moment it sees one. It is
deliberately *not* a packaging tool - see [Building](./building.md) for
compiling `hlmod-hl` itself and the installer for end-user distribution. This
script has no relation to either; it exists purely to save you from Alt-Tab,
Ctrl-C, up-arrow, Enter fifty times a session.

## How the polling works

`dev.py` does not use a filesystem-event watcher (inotify, `watchdog`, or
similar). It takes a snapshot of every watched file's `(mtime_ns, size)`,
sleeps for a poll interval, takes another snapshot, and diffs the two:

```python
def snapshot(paths: list[Path]) -> dict[Path, tuple[int, int]]:
    """mtime_ns + size per file, so edits are seen even with coarse mtimes."""
    state = {}
    for path in paths:
        try:
            info = path.stat()
        except OSError:
            continue
        state[path] = (info.st_mtime_ns, info.st_size)
    return state
```

Any path whose `(mtime_ns, size)` tuple differs from the previous snapshot -
including a path that appeared or disappeared entirely, since the diff is
taken over the union of both key sets - counts as a change and triggers a
restart. This is a plain poll, not a push, and that's on purpose: it adds no
extra dependency and stays consistent with the rest of the mod SDK, which
already avoids native/third-party tooling wherever a stdlib approach is good
enough. `pathlib.Path.stat()` and a sleep loop is something every Python
install already has; a real filesystem watcher is one more package to pin,
vendor, and keep working across Linux and Windows.

The tradeoff is latency, controlled by `--poll` (default `0.5` seconds - see
[Flags](#flags) below). A shorter interval notices edits faster at the cost
of more frequent `stat()` calls across every watched file; a longer one is
cheaper but adds up to half the interval's worth of dead time between saving
a file and seeing the restart. For a mod source tree - dozens to low hundreds
of small `.py` files - the default interval is unmeasurable in practice; it
only starts to matter if you point `--mods` at something enormous.

## What gets watched (and what doesn't)

The watch set is built from:

- Every `*.py` file under the primary mods directory (`--mods`, default
  `mods/`), recursively.
- Every `*.py` file under each `--extra-mods` directory, recursively (see
  [Developing outside the mods directory](./external-mods.md) for what that
  flag is for).
- `hlmod.toml` and `typing_overlays.json`, read from the *primary* mods
  directory only - `<mods>/hlmod.toml` and `<mods>/typing_overlays.json`.
  Config files inside an `--extra-mods` directory are not watched.

Two things are explicitly excluded from the `.py` scan, per mods directory:

```python
def is_generated(mods_dir: Path, path: Path) -> bool:
    """hlmod regenerates `mods/stubs/**` (and each package's `__pycache__`)
    on its own schedule, not in response to edits, so treating those as
    user changes would restart on every launch."""
    parts = path.relative_to(mods_dir).parts
    return parts and (parts[0] == "stubs" or any(part == "__pycache__" for part in parts))
```

- The generated `stubs/` tree at the top of a mods directory (see
  [Editor support](./editor-support.md) for what lives there and why).
- Any `__pycache__` directory, at any depth.

Both are generated output, not something you hand-edit, so watching them
would mean restarting `hl` every time it writes its own stub or bytecode
cache - a loop chasing its own tail. If a file goes missing entirely (say you
delete a module), that still shows up as a change, because the diff runs
over the union of both snapshots' keys, not just the new one.

## Restarting `hl`

On a detected change, `dev.py` stops the current process and starts a new
one:

- Stop sends `SIGTERM` and waits up to 5 seconds; if the process hasn't
  exited by then, it's `SIGKILL`ed outright. There's no configurable grace
  period - 5 seconds is hardcoded and assumed to be generous enough for a
  Hashlink process to shut down cleanly.
- Start launches `hl <bytecode>` again with `cwd` set to the bytecode's own
  directory (or `--cwd`, if you passed one), and with
  `PYTHONDONTWRITEBYTECODE=1` forced into the environment. That last part
  isn't cosmetic: CPython's `.pyc` cache keys on mtime at one-second
  granularity, so a restart that lands within the same second as the edit
  that triggered it could otherwise load a stale cached bytecode file
  instead of your actual change. Disabling `.pyc` writes for the dev-loop
  child process sidesteps the race entirely rather than trying to win it.

If the `hl` process exits on its own - crash, explicit quit, whatever -
`dev.py` does not treat that as fatal. It prints a one-line notice
(`hl exited with status N; waiting for a change to restart.`) and keeps
polling; saving a file (or otherwise producing a watched-set diff) brings it
back up. The loop itself only stops on Ctrl-C, at which point it tears down
any still-running `hl` process before exiting.

## Flags

| Flag | Default | Meaning |
| --- | --- | --- |
| `bytecode` (positional) | - | Compiled `.hl` bytecode to run. |
| `--hl` | `hlmod-hl/build/bin/hl` | Path to the `hl` executable. |
| `--mods` | `mods` | Primary mods directory to watch and load from. |
| `--extra-mods` | *(none)* | Additional directory to watch and load mods from; repeatable. Passed through to `hl` via `HLMOD_EXTRA_MODS`, merged with anything already set in the environment. |
| `--cwd` | bytecode's own directory | Working directory for the `hl` process. |
| `--poll` | `0.5` | Filesystem poll interval, in seconds. |

`--extra-mods` is how you point the dev loop at a mod project that lives
entirely outside the game's `mods/` directory - the same setup described in
[Developing outside the mods directory](./external-mods.md), just without
having to export `HLMOD_EXTRA_MODS` by hand first. Anything already present
in `HLMOD_EXTRA_MODS` from the surrounding shell is preserved and combined
with whatever `--extra-mods` values you pass; the combined list is both
watched for changes and forwarded to the `hl` child process.

## Example invocations

The one-liner from the top, with an explicit `hl` path:

```sh
python3 tools/dev.py game.hl --hl hlmod-hl/build/bin/hl
```

Working on a mod that lives outside the game install, watching and loading
it alongside the game's own `mods/` directory:

```sh
python3 tools/dev.py game.hl --extra-mods ~/projects/my-mod
```

Pointing at an entirely out-of-tree install (no in-repo `mods/` at all) and
your project directory, per [Developing outside the mods directory](./external-mods.md):

```sh
python3 tools/dev.py game.hl --mods /path/to/install/mods --extra-mods ~/projects/my-mod
```

Widening the poll interval, e.g. because `--mods` points at something large
enough that a 0.5-second `stat()` sweep is actually noticeable:

```sh
python3 tools/dev.py game.hl --poll 2.0
```

## Gotchas

- This is a local iteration tool, not packaging: it does not compile
  anything, does not touch `hlmod-hl`'s build, and has no relation to the
  installer or the nightly build. If `hl` itself needs rebuilding, that's
  [Building](./building.md), not this.
- Only `.py` files (plus the two named config files in the primary mods
  directory) are watched. Editing anything else - a data file your mod
  reads, an asset, `hlmod-hl`'s C source - will not trigger a restart.
- Config changes only restart when they're in the primary mods directory.
  An `hlmod.toml` inside an `--extra-mods` directory is invisible to the
  watcher (there generally isn't one there in practice, since per-mod
  configuration lives with the primary install).
- A crashing `hl` doesn't stop the loop, but it also doesn't restart on its
  own - `dev.py` waits for an actual file change before trying again, even
  if the crash was transient.
