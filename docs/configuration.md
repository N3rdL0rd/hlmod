---
sidebar_position: 15
---

# Global configuration

`modcore.config` stores mod settings in one `hlmod.toml` file, one table per
mod, deliberately not JSON:

```python
from modcore import config

settings = config.section(defaults={"volume": 5, "show_hud": True})
settings["volume"] = 8   # marks the file dirty
```

TOML was specifically chosen since a config file is
something a user is expected to open in a text editor and hand-edit, and
TOML tables with comments read a great deal better than nested braces do.
The tradeoff is that Python's stdlib only reads TOML (`tomllib`, since
3.11) and doesn't write it, so hlmod ships a small writer of its own
(`modcore._toml_writer`) rather than pull in a third-party dependency just
to round-trip plain data back to disk.

## Where the file lives

The path is `Path("hlmod.toml")` - relative, resolved against the
process's current working directory, which in practice means it sits next
to wherever the embedding game (or your dev harness) was launched from.
There's no per-mod file and no subdirectory scheme; every mod's settings
live in the same file, distinguished only by table name.

If that default doesn't suit you, `config.set_path(path)` overrides it:

```python
config.set_path("config/hlmod.toml")
```

This has to happen *before* the first `section()` or any implicit load -
calling it later discards whatever's already been read into memory
(including unsaved changes) and resets the dirty flag, so a late call is a
silent data-loss footgun, not a no-op. In practice this means call it once,
early, from whatever bootstraps the framework, and never again.

## Sections: one table per mod

`config.section(name=None, *, defaults=None)` gets (creating if necessary)
one mod's top-level table and hands back a `Section` wrapping it. `name`
defaults to the id of whatever mod is currently loading, resolved via the
same `current_mod()` lookup the rest of `modcore` uses internally - so the
idiomatic call from inside a mod's `initialize()` is just
`config.section(defaults={...})` with no name at all. Call it with no name
outside of `initialize()` (no mod actively loading) and you get a
`RuntimeError` telling you to pass one explicitly.

Every key present in `defaults` but missing from the file gets filled in
immediately, without touching a key the user already changed. This is the
whole point of `defaults`: a fresh install ends up with a complete config
file after its first save, and an existing install only ever gains new
keys, never has old ones silently reset. Even calling `section()` with no
`defaults` at all still marks the file dirty the first time it runs for a
given mod, because an empty table gets created and inserted into the
top-level document - so a mod that never sets a single key still ends up
with `[its_mod_id]` written to `hlmod.toml` on shutdown, which is harmless
but occasionally surprising the first time you go looking for it.

## The `Section` API

`Section` isn't a `collections.abc.MutableMapping` subclass - it doesn't
register with the ABC and doesn't inherit any of the mixin methods that
come with one - but it implements enough of the mapping protocol by hand
that it behaves like a dict for everyday use:

```python
settings["volume"]              # __getitem__
settings["volume"] = 8          # __setitem__, marks dirty
del settings["show_hud"]        # __delitem__, marks dirty
"volume" in settings            # __contains__
for key in settings: ...        # __iter__ (over keys)
len(settings)                   # __len__
settings.get("volume", 5)       # .get, with default
settings.setdefault("fov", 90)  # marks dirty only if the key was missing
settings.as_dict()              # a plain dict *copy* of the table
settings.save()                 # equivalent to config.save()
```

Because it isn't a real `MutableMapping`, the mixin conveniences that
protocol would normally give you for free - `.keys()`, `.values()`,
`.items()`, `.update()`, `.pop()`, `.clear()`, and friends - simply aren't
there. If you need those, `settings.as_dict()` gets you a real dict to
call them on (mutating that copy does nothing to the underlying config,
by design - it's a snapshot, not a live view). Everything that *is*
implemented above marks the module-level dirty flag on any actual
mutation; reads never do.

`settings.name` holds the mod id the section was created for, if you ever
need to double-check which table you're holding onto.

## Saving: autosave and manual save

Writes are debounced behind a single module-level dirty flag, not written
on every `__setitem__`. `config.save()` writes the whole in-memory
document to `hlmod.toml` if and only if something has changed since the
last save; call it as many times as you like when nothing's dirty and it's
a no-op.

You'll rarely need to call it yourself, though, because `modcore.config`
subscribes its own listener to the `shutting_down` event (see
[Mods, hooks, and events](./mods-hooks-events.md)) at import time:

```python
@shutting_down.listen()
def _autosave() -> None:
    save()
```

`shutting_down` is emitted once by `shutdown()`, before any mod's own
shutdown callback runs and before mods are unloaded, so every mod's config
changes from the entire session get flushed in one write at the very start
of teardown. If you want a setting persisted immediately - right before an
operation that might crash the process, say - call `config.save()` (or the
equivalent `section.save()`) directly rather than waiting for shutdown.

## The TOML writer: what it can and can't serialize

`modcore._toml_writer.dumps(data)` is a narrow writer, not a general TOML
library, and it says so in its own docstring: it covers exactly the value
shapes `tomllib` reads back and nothing more - `bool`, `int`, `float`,
`str`, `list` (and `tuple`, serialized the same way, as a TOML array),
and `dict` as a nested table. Anything else raises immediately:

```
TypeError: Value of type 'set' is not TOML-serializable: {1, 2, 3}
```

A few details worth knowing if you're putting anything unusual in a
config value:

- **Keys** are written bare when every character is alphanumeric,
  underscore, or hyphen; anything else (spaces, dots, unicode) gets
  written as a quoted string key instead. Either way it round-trips.
- **Strings** are escaped for backslashes, quotes, and the usual
  whitespace control characters and always written as one quoted TOML
  string - no bare/literal/multi-line string forms.
- **Floats** handle the non-finite cases TOML actually supports:
  `float("nan")` writes as `nan`, `float("inf")`/`float("-inf")` as `inf`
  / `-inf`. Anything else goes through `repr()`.
- **Booleans are checked before ints.** `isinstance(value, bool)` is
  tested first specifically because `bool` is a subclass of `int` in
  Python - without that ordering, `True` would silently serialize as `1`.
- **Nested tables** are just nested dicts; `dumps` walks them recursively
  and emits a `[section.subsection]` header per level. There's no special
  syntax for arrays of tables (`[[...]]`) - a list of dicts serializes as
  a TOML inline-array-of-inline-tables (`[{...}, {...}]`) on one line,
  not as repeated `[[section]]` blocks.

Correctness here is verified by round-tripping through `tomllib.loads` in
hlmod's own test suite, not by chasing full TOML-spec conformance - it's
a writer built to serve exactly one reader (`tomllib`, loading exactly
what `dumps` wrote), and it doesn't try to be anything more general than
that.

## Gotchas

- **`set_path` is a hard reset - it doesn't rename your existing file.** Calling it after any
  `section()`/`save()` activity throws away in-memory state, including
  anything unsaved. Set it once, before anything else touches config.
- **`section()` needs a name outside of `initialize()`.** Config access
  from a REPL session, a test, or a background thread that isn't "the
  currently loading mod" needs an explicit `name=` argument or it raises.
- **Unsupported value types fail at save time, not at assignment time.**
  `settings["thing"] = some_object` succeeds silently; the `TypeError`
  only shows up later, inside `config.save()` (or at process shutdown, via
  autosave), which can make the failure feel disconnected from its cause.
  Stick to plain data - bool/int/float/str/list/dict - in config values.
