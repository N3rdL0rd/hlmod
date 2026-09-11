---
sidebar_position: 6
---

# hlmod-sdk

[`sdk/`](https://github.com/N3rdL0rd/hlmod/tree/main/sdk) is a small, globally-installable CLI that does everything the graphical
installer does - download a build, install it into a game directory, remember where you put it - plus one thing the GUI
doesn't: scaffolding a starter mod project against any install it knows about. It exists mostly so you never have to open
a file browser to make a mod. `hlmod-sdk install`, then `hlmod-sdk new`, and you have a project with working editor
intellisense before you've written a line of Python.

The interesting bit isn't the CLI itself, it's that it *isn't* a reimplementation of the [graphical installer](./installation.md).
`installer/main.py` (the Qt GUI) imports `install()` straight out of `hlmod_sdk.installer` and runs it on a background
thread; the CLI in `hlmod_sdk/cli.py` calls the exact same function. One install routine, two front ends, and both of
them record what they did into the same [registry file](#the-install-registry) - which is the whole reason `hlmod-sdk new`
can find an install you made with the GUI three weeks ago without you typing the path back in.

## Installing the CLI itself

```sh
# straight from a checkout of this repo...
uv tool install ./sdk
pipx install ./sdk

# or from PyPI! <-- ignore this, I'm too lazy to publish on PyPi
# uv tool install hlmod-sdk
# pipx install hlmod-sdk
```

It's a normal Python package (`requires-python = ">=3.10"`, one dependency: `requests`) that installs a `hlmod-sdk`
console script (`hlmod_sdk.cli:main`). `uv tool install` and `pipx install` both put that script on your `PATH` in an
isolated environment, which is the entire point - you shouldn't need a virtualenv lying around just to install a modding
framework.

## `hlmod-sdk install`

```sh
hlmod-sdk install <directory> [--type TYPE] [--version VERSION] [--tweak TWEAK] [--no-auto-detect]
```

`directory` is the only required argument - the game folder to install into, created with `os.makedirs` if it doesn't
already exist. Everything else has a default that's right for a plain vanilla install.

**`--type`** picks which nightly build variant to download. The valid choices depend on *the platform running
`hlmod-sdk`*, not the target game - the CLI only offers build types for your own OS, so cross-installing a Windows
build from a Linux machine isn't currently possible through this command. Default is the first entry below for your OS:

| `--type` | nightly artifact | platform |
|---|---|---|
| `gcc-release` (default on Linux) | `Linux-gcc-Release` | Linux |
| `gcc-debug` | `Linux-gcc-Debug` | Linux |
| `clang-release` | `Linux-clang-Release` | Linux |
| `clang-debug` | `Linux-clang-Debug` | Linux |
| `msvc-release` (default on Windows) | `Windows-msvc-Release` | Windows |
| `msvc-relwithdebinfo` | `Windows-msvc-RelWithDebInfo` | Windows |
| `mingw-release` | `Windows-mingw-Release` | Windows |

An unrecognized `--type` fails fast with `error: unknown build type 'foo'; choose from: ...` rather than trying to
download something that doesn't exist.

**`--version`** is `latest` by default, which asks GitHub for the current HEAD commit of `main` and then finds the
newest successful `Nightly Build` workflow run for that commit's SHA. You can pass any commit SHA that has a
corresponding nightly build if you need to pin to something specific (bisecting a regression, matching a build a
friend is using, etc.) - `hlmod-sdk install ~/games/foo --version a1b2c3d`.

**`--tweak`** (repeatable) applies one of a handful of install-time adjustments, each with a short CLI alias:

| alias | effect |
|---|---|
| `steam` | Use the game's existing `steam.hdll` (and `libsteam_api.so` on Linux) instead of hlmod's bundled build |
| `sdl` | Use the game's existing `sdl.hdll` instead of hlmod's bundled build |
| `openal` | Use the game's existing `openal.hdll` (and `OpenAL32.dll` on Windows) instead of hlmod's bundled build |
| `dcmod` | Install the Dead Cells mod (`dcmod`) alongside the base framework |
| `no-base-mods` | Skip installing `hlobj`, `hlvalues`, and `modcore` - just the raw `hlmod` native module and its `.pyi` stub |

:::warning
`--tweak` only takes effect together with `--no-auto-detect`. By default the installer *auto-detects* tweaks by
inspecting the target directory - `steam.hdll` present means "use existing steam", a `deadcells`/`deadcells.exe`
binary means "install dcmod", and so on - and that auto-detected set silently **replaces** whatever you passed with
`--tweak`, it doesn't merge with it. If you want manual control, say so explicitly:

```sh
hlmod-sdk install /path/to/game --no-auto-detect --tweak dcmod --tweak steam
```
:::

Auto-detection (`detect_tweaks`) checks: `steam.hdll` present *and* running on a POSIX host → use-existing-steam;
`sdl.hdll` present → use-existing-sdl; `openal.hdll` present *and* running on Windows → use-existing-openal; a
`deadcells`/`deadcells.exe` binary present → install dcmod. It never auto-selects `no-base-mods` - skipping the
framework mods is something you have to ask for on purpose.

Under the hood, a successful `install()` call does, in order: resolve the version to a commit SHA and workflow run
ID, download `hlmod-hl-nightly-python3.13-<artifact>.zip` from `nightly.link`, extract it into `<directory>/hlmod`,
resolve tweaks (auto or manual), then copy the framework-managed pieces into place - a `run_hlmod.sh` (Linux) or
`run_hlmod.bat` (Windows) launcher script that sets `PYTHONHOME`/`PYTHONPATH` (and `LD_LIBRARY_PATH` on Linux) to
point at the bundled embedded Python before exec-ing `hl.bin`/`hl.exe`, plus `hlobj.py`/`hlobj.pyi`/`hlvalues.py`
and the `modcore` package into `mods/` (unless `no-base-mods`), plus `hlmod.pyi` unconditionally, since `import hlmod`
needs its stub even with the framework skipped. It only ever touches those specific paths - any other mods already
sitting in `mods/`, yours or someone else's, are left alone across reinstalls and updates. The very last step records
the install in the registry; that step is best-effort (an `OSError` there is swallowed rather than failing an
otherwise-successful install).

## `hlmod-sdk list`

```sh
hlmod-sdk list
```

No arguments. Prints every registered install, most recently installed first, one entry per index:

```
1. /home/user/games/deadcells
   build: Linux-gcc-Release  version: a1b2c3d  installed: 2026-09-10T18:04:22+00:00
2. /home/user/games/some-other-hl-game
   build: Windows-msvc-Release  version: 7f3e9aa  installed: 2026-08-02T09:11:47+00:00
```

If nothing is registered yet it prints a hint to run `hlmod-sdk install` first and exits with status 1.

## `hlmod-sdk new`

```sh
hlmod-sdk new <name> [--install SELECTOR] [--dir PATH]
```

`name` becomes the mod's id after slugification: anything that isn't `[a-zA-Z0-9_]` becomes an underscore, leading
and trailing underscores are stripped, and a leading digit gets an underscore prefixed (`3cool` → `_3cool`) since it
wouldn't be a valid Python module name otherwise. A name that slugifies to nothing raises an error.

`--install SELECTOR` picks which registered install to target. The selector can be a 1-based index matching
`hlmod-sdk list`'s output, an exact install path, or a unique case-insensitive substring of one - `--install 2`,
`--install /home/user/games/deadcells`, and `--install deadcells` are all valid ways to pick the same entry, as long
as the substring only matches one install. If you omit `--install` entirely: with exactly one install registered it's
used automatically; with zero, you get told to run `install` first; with more than one, you get an error listing
every candidate so you can pick.

`--dir PATH` sets the output directory; it defaults to `./<name>` under the current working directory. The directory
must not already exist - `hlmod-sdk new` refuses to write into (or silently merge with) an existing folder.

```sh
hlmod-sdk new my_mod
hlmod-sdk new my_mod --install 2
hlmod-sdk new my_mod --install deadcells --dir ~/projects/my_mod
```

## What gets generated

Three files, all written by `hlmod_sdk/scaffold.py`:

**`<mod_id>.py`** - the starter mod itself:

```python
MOD_INFO = {"id": "my_mod", "dependencies": []}


def initialize() -> None:
    print("[my_mod] loaded")
```

**`pyrightconfig.json`** - points a type checker at the target install's `mods/` directory so `from stubs...`,
`from modcore import ...`, and `import hlmod` all resolve without copying anything or running a generator step. See
[Editor support](./editor-support.md) for what that buys you once generated proxy `.pyi` stubs are in the picture:

```json
{
  "include": ["my_mod.py"],
  "extraPaths": ["/home/user/games/deadcells/mods"],
  "pythonVersion": "3.12",
  "typeCheckingMode": "standard"
}
```

**`README.md`** - a short explanation of the two things you'd otherwise have to remember: that editor support comes
from the generated `pyrightconfig.json`, and that this project is meant to be loaded *without* copying it into the
game's own `mods/` folder - point `HLMOD_EXTRA_MODS` at this directory instead and launch the install's own launcher
script as usual:

```sh
HLMOD_EXTRA_MODS="/home/user/projects/my_mod" "/home/user/games/deadcells/run_hlmod.sh" deadcells.hl
```

(the README picks `run_hlmod.bat` instead of `run_hlmod.sh` automatically when the target install's recorded build
type starts with `Windows`). Keeping the project directory separate from the game's `mods/` folder means `git status`
in your mod repo never has to think about the rest of the game's files, and reinstalling or updating hlmod never
touches your project.

## The install registry

Every successful install - CLI or GUI - is recorded in one per-user JSON file, keyed by the install's resolved
absolute path, at the platform-conventional config location:

- Linux (and anything else): `$XDG_CONFIG_HOME/hlmod/installs.json`, falling back to `~/.config/hlmod/installs.json`
- macOS: `~/Library/Application Support/hlmod/installs.json`
- Windows: `%APPDATA%\hlmod\installs.json`, falling back to `~/AppData/Roaming/hlmod/installs.json`

The shape (schema version 1) is about as plain as JSON gets:

```json
{
  "schema_version": 1,
  "installs": {
    "/home/user/games/deadcells": {
      "mods_dir": "/home/user/games/deadcells/mods",
      "version": "a1b2c3d4e5f6...",
      "build_type": "Linux-gcc-Release",
      "installed_at": "2026-09-10T18:04:22+00:00"
    }
  }
}
```

Writes are atomic (`installs.json.tmp` written first, then `os.replace`d over the real file), and a missing or
corrupt registry file is treated the same as an empty one rather than raising - `hlmod-sdk list` on a fresh machine
just tells you nothing's registered instead of crashing.

The reason this file matters more than its size suggests: `hlmod_sdk.installer.install()` is the *only* function
that writes to it, and both the GUI installer and `hlmod-sdk install` call that same function. Install a game through
the GUI, and it shows up in `hlmod-sdk list` and is selectable by `hlmod-sdk new --install ...` immediately - no
separate "import" step, no keeping two lists in sync, because there was only ever one list.

## See also

- [Installation](./installation.md) - the graphical and manual installation paths that `hlmod-sdk install` automates over.
- [Editor support](./editor-support.md) - what the generated `pyrightconfig.json` actually gets you once proxy
  `.pyi` stubs exist for a mod's target types.
