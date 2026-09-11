---
sidebar_position: 19
---

# Heaps resource overlay

`mods/heaps` is a small, fully generic package for one specific problem: letting a mod add or override game assets - textures, sounds, data files, whatever - without depending on Dead Cells, or any other particular Heaps game's asset layout. It ships as part of hlmod itself (not `modcore`, since not every Hashlink game uses [Heaps](https://heaps.io/)), and a mod opts into it with an ordinary dependency:

```python
MOD_INFO = {"id": "my_mod", "dependencies": ["heaps"]}

import heaps
from pathlib import Path

def initialize():
    heaps.add_overlay_dir(Path(__file__).parent / "res")
```

Any file placed under that directory now wins over the game's own copy at the same relative path, the moment the game's resource loader asks for it - no `.pak` unpacking, no CastleDB awareness, nothing game-specific at all.

## Why this doesn't touch the pak format

Every Heaps game picks exactly one of three ways to stand up its resource loader at compile time - `hxd.Res.initEmbed()`, `.initLocal()`, or `.initPak()` - and each one hands `hxd.res.Loader` a different concrete `hxd.fs.FileSystem` implementation: an embedded-resource reader, a loose-directory reader, or a `.pak` archive reader. A generic overlay that tried to understand `.pak`'s binary layout, or CastleDB's table format, or any other Heaps-ecosystem file format, would only ever cover *some* games, and would need updating every time a new asset format showed up.

`mods/heaps` sidesteps all of it by hooking one level higher: the `hxd.fs.FileSystem` *interface* boundary itself. Whichever of the three init functions the game actually calls, `heaps` installs a synthesized `FileSystem` in front of the real one - constructed once, the first time it's needed, via [`create_subclass`'s `interfaces=`](./subclassing.md) - that checks each registered overlay directory before falling through to whatever the original `FileSystem` was going to do anyway. The override object it returns for a hit, similarly, is a from-scratch subclass of the game's own `hxd.fs.FileEntry`, so it satisfies every caller expecting a real `FileEntry` without hlmod needing to know anything about `.pak` internals, embedded-resource indexing, or CastleDB. This is the same "wrap the interface, not the format" idea a bespoke `.pak` reader would eventually have to converge on anyway - just applied one layer up, where it works identically against every Heaps game regardless of which of the three loader backends it happens to compile in.

## Finding the loader without a stub import

`hxd.Res` is a Haxe class with no instance side - every member is `static`. HashLink compiles a class shaped like that down to a single hidden global instance of a companion type named `pack.$Type` (the `$` marks the *last* path segment, so it's `hxd.$Res`, not `$hxd.Res`), and its static fields - `loader` among them - are just ordinary object fields on that one global. `mods/heaps` resolves `hxd.$Res` by name, reads its `loader` field off of `hlmod.get_global(...)`, and only then walks down into `Loader.fs` to find the `FileSystem` it needs to wrap. None of this requires a generated Python stub for `hxd.Res` or `hxd.res.Loader` to exist - `hlmod.inspect_native` supplies everything `heaps` needs (field indices, method findexes, interface member signatures) to build call-through wrapper classes for types it's never seen a stub for, entirely at runtime.

## Ordering and precedence

`add_overlay_dir` can be called any time - before the resource loader exists yet, from a mod's own `initialize()`, or later - since the directory is just queued until whichever `hxd.Res.init*()` the game calls actually runs. Multiple mods can each register their own overlay directory; the first one registered that contains a given path wins, so load order (see [Mods, hooks and events](./mods-hooks-events.md#discovery-and-load-order)) doubles as override priority the same way it does everywhere else in hlmod.

## See also

- [Subclassing native HL objects](./subclassing.md) - the `create_subclass`/`implements=` machinery `heaps` builds its overlay classes on top of.
- [Mods, hooks and events](./mods-hooks-events.md) - `postfix_hook`, dependency resolution, and load order in general.
