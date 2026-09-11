---
sidebar_position: 5
---

# Developing outside the mods directory

A mod's own source does not have to live inside a game's `mods/` directory.
`HLMOD_EXTRA_MODS` adds one or more additional directories (`os.pathsep`-separated,
so `:` on Linux/macOS and `;` on Windows) that are searched and imported from
alongside the primary directory:

```sh
HLMOD_EXTRA_MODS=/path/to/my_mod_project hl game.hl
```

The primary directory (`./mods` by default, or wherever `HLMOD_MODS_DIR`
points) still supplies `hlobj.py`, `hlvalues.py`, `modcore/` and the generated
`stubs/`; your own project directory holds only your mod's source. Point your
editor's `extraPaths` (Pyright/pylance) or equivalent at the primary directory
so `from stubs.pr import Game` and `from modcore import hook` resolve, while
your project's own root stays clean of generated files and other mods.

`HLMOD_MODS_DIR` relocates the primary directory entirely, so a game/mod
install does not have to be named or located at `./mods`:

```sh
HLMOD_MODS_DIR=/path/to/install/mods hl game.hl
```

`tools/dev.py` accepts the same shape directly, watching and loading from an
external project without exporting anything by hand:

```sh
python3 tools/dev.py game.hl --mods /path/to/install/mods --extra-mods /path/to/my_mod_project
```
