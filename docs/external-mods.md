---
sidebar_position: 5
---

# Developing outside the mods directory

A mod's own source does not have to live inside a game's `mods/` directory. That's fine for a five-minute experiment, but for an actual project you probably want the mod in its own git repository, versioned independently of both the game install and hlmod itself, and you probably don't want your editor treating `modcore/`, `hlobj.py`, and a folder of generated stubs as part of *your* project's source tree. Two environment variables exist for exactly this: `HLMOD_EXTRA_MODS` adds directories the loader also searches and imports from, and `HLMOD_MODS_DIR` relocates the primary directory entirely.

## Why bother

A few concrete reasons this comes up:

- **Editor tooling.** A type checker works best with one clean root to reason about. If your mod's source is interleaved inside `mods/` with a dozen other mods and hlmod's own generated files, `extraPaths` config and "go to definition" get muddier than they need to be. Give your mod its own directory and it behaves like any other Python project.
- **Versioning your mod separately.** A mod under active development wants its own git history, its own README, its own tags - none of which belong mixed into a `mods/` folder that's really the game install's business, not yours.
- **Sharing one hlmod install across projects.** If you're maintaining more than one mod, or a mod alongside a fork you're testing changes against, you don't want to duplicate `hlobj.py`/`hlvalues.py`/`modcore/` per project. Point every project's source directory at the same primary `mods/` directory via `HLMOD_EXTRA_MODS` and each stays a self-contained checkout.

## What each directory supplies

This distinction is the one to actually remember, because the two kinds of directory are not interchangeable:

- The **primary directory** (`./mods` by default, or wherever `HLMOD_MODS_DIR` points) supplies `hlobj.py`, `hlvalues.py`, `modcore/`, and the `stubs/` directory hlmod regenerates from the loaded bytecode on every launch (unless the binary was built with `NO_STUBGEN`, in which case whatever's already in `stubs/` is used as-is). It's also the one directory the `hl` executable itself appends to `sys.path`, before Python has imported anything.
- **Extra directories**, from `HLMOD_EXTRA_MODS`, supply mod source only. They get added to `sys.path` too - by the mod loader itself, not by `hl` - and get scanned for mods exactly like the primary directory does, but nothing generates `hlobj.py`, `modcore/`, or stubs into them.

In practice: an extra directory should hold *only* your mod's `.py` file (or a package with an `__init__.py` and a `MOD_INFO`, see [Mods, hooks, and events](./mods-hooks-events.md)). A mod there still does `from modcore import hook` or `from stubs.pr import Game` exactly as if it lived in `mods/` - those imports resolve through the primary directory's copy, wherever that is, because both directories share the same `sys.path`. Copying `modcore/` into an extra directory yourself doesn't help anything; it isn't scanned for framework files, only for mods, so the copy just sits there as a second, stale, unused tree.

## `HLMOD_EXTRA_MODS`

```sh
HLMOD_EXTRA_MODS=/path/to/my_mod_project hl game.hl
```

The value is `os.pathsep`-separated, so `:` on Linux/macOS and `;` on Windows, and takes as many directories as you like:

```sh
HLMOD_EXTRA_MODS=/path/to/mod_a:/path/to/mod_b hl game.hl
```

The loader searches the primary directory first, then each extra directory in the order given, and within a single directory entries are visited alphabetically. Anything named `stubs`, or starting with `_`, is skipped so hlmod's own generated output never gets mistaken for a mod. That scan order matters more than it might look: mods with no dependency relationship between them load in exactly the order they were found - primary directory first, extras after, alphabetically within each - and only a `MOD_INFO["dependencies"]` entry can push a mod later than that. So a self-contained mod with no declared dependencies effectively loads in directory-scan order; declare a real dependency if you actually need to load after something specific.

The one place scan order is enforced strictly, not just as a tie-break, is mod IDs. They're global, not scoped per directory: if a mod in an extra directory declares the same `MOD_INFO["id"]` as one already found earlier in the scan - the primary directory, or an earlier extra directory - the loader raises `ValueError: Duplicate mod ID '<id>': <first mod name> and <second mod name>` and refuses to start. There's no shadowing and no "last one wins"; a colliding ID is treated as an authoring mistake, not a feature, so if you're vendoring someone else's mod alongside your own for testing, check its declared ID first.

## `HLMOD_MODS_DIR`

```sh
HLMOD_MODS_DIR=/path/to/install/mods hl game.hl
```

This one is a straight relocation: wherever it points *becomes* the primary directory for that launch, in place of `./mods`. Stub generation writes there, `hlobj.py`/`hlvalues.py`/`modcore/` are expected to already live there, and it's the directory that ends up on `sys.path` before mod loading starts. Useful whenever the game/mod install just isn't named or located at `./mods` - a CI job unpacking a fixture into a temp directory, an install in an unusual place, or a setup where "mods" isn't even the right word for what's in there.

`HLMOD_MODS_DIR` and `HLMOD_EXTRA_MODS` compose normally: relocate the primary directory with one, layer extra source directories on top with the other.

## A concrete layout

Say you're building `super_mod` and don't want it living inside the game's own install. Before, everything sits together under the game's `mods/`:

```
dead_cells_install/
└── mods/
    ├── hlobj.py
    ├── hlvalues.py
    ├── modcore/
    ├── stubs/             # regenerated on every launch
    └── super_mod.py       # your mod, mixed in with the framework files
```

After, with `super_mod` pulled into its own repository and launched via `HLMOD_EXTRA_MODS=/home/you/projects/super_mod hl game.hl`:

```
dead_cells_install/
└── mods/
    ├── hlobj.py
    ├── hlvalues.py
    ├── modcore/
    └── stubs/              # still generated here, and only here

~/projects/super_mod/       # its own repo, its own editor root
└── super_mod.py
```

`super_mod.py` doesn't change at all - same `from modcore import hook`, same `from stubs.pr import Game` - because both directories are on `sys.path` and the imports resolve through the primary one regardless of where the importing file lives. Point Pyright/pylance's `extraPaths` at `dead_cells_install/mods` (see [Editor support](./editor-support.md)) and both directories resolve for autocomplete and type checking without hlmod needing to generate anything a second time.

## `tools/dev.py`

`tools/dev.py` takes the same two knobs directly instead of making you export the environment variables by hand:

```sh
python3 tools/dev.py game.hl --mods /path/to/install/mods --extra-mods /path/to/my_mod_project
```

`--mods` defaults to `./mods` and sets the primary directory - equivalent to `HLMOD_MODS_DIR`. `--extra-mods` is repeatable (pass it more than once for more than one directory) and gets merged with any `HLMOD_EXTRA_MODS` already present in the environment before being re-exported to the `hl` child process. The file watcher tracks all of them, primary and extra alike, so editing a `.py` file in an external project directory triggers the same hot reload as editing one inside `mods/` directly. See [Dev loop](./dev-loop.md) for how the watch-and-reload cycle itself works.

## Gotchas

- A mod ID collision across directories is a hard startup failure (`ValueError`), not a warning or a silent override.
- Directory scan order is a real (if weak) ordering signal for mods with no declared dependencies between them - don't rely on it instead of an explicit `dependencies` entry if load order actually matters.
- Only one `stubs/` directory ever exists per launch, generated into whichever directory is currently primary. Extra directories never get their own.
- Copying framework files into an extra directory doesn't do anything useful; that directory is scanned for mods, not for `hlobj.py`/`modcore/`, so the copy just becomes stale dead weight nobody imports.
