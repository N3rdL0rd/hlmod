---
sidebar_position: 2
---

# Installation

There are three ways to get hlmod onto a game: the graphical installer, `hlmod-sdk install` from a terminal, or just unzipping a build yourself. All three end up doing more or less the same thing to the game directory - the GUI and the CLI actually share one implementation (`hlmod_sdk.installer.install()`) so they can't drift apart from each other, and the manual path is what that function does with all the automation stripped away. This page covers the GUI in detail, since it's the one with knobs to explain, and the manual path for people who'd rather not run a Qt app. The CLI gets its own page - see [hlmod-sdk](./hlmod-sdk.md) - since it does more than just installing.

## The GUI installer

Grab it from [nightly.link](https://nightly.link/N3rdL0rd/hlmod/workflows/installer/main) or the GitHub Releases page. That link builds the *installer program itself* from CI - it's a separate build from the hlmod runtime it goes on to download, so don't confuse the two if something looks stale; redownload the installer, then let it fetch a fresh runtime.

Point it at your game's install directory (the folder with the game's main executable in it, wherever Steam or your launcher of choice put it), pick a version and build type, and hit Install. Under the hood, that one click runs through a fixed pipeline:

1. **Resolve a version.** "Nightly (latest)" resolves to whatever commit is currently on `main` via the GitHub API; "Custom" asks for a full git commit hash (the long one - a short hash won't match). Either way, the installer then looks up that commit's CI runs and picks the newest one where the `Nightly Build` workflow actually succeeded. If nothing succeeded for that commit, you get a clear "Failed to find successful build!" instead of a silent wrong download.
2. **Download.** The build artifact is fetched from nightly.link, named by convention as `hlmod-hl-nightly-python3.13-<BuildType>.zip` (e.g. `hlmod-hl-nightly-python3.13-Linux-gcc-Release.zip`) - the embedded CPython version is baked into the filename, so this is one of the few places a Python upgrade would need a coordinated change on both ends.
3. **Extract.** The zip unpacks into a new `hlmod/` subdirectory of your game folder. This is the same `hlmod/` you'd create by hand in the manual path below.
4. **Resolve tweaks.** Either auto-detected from what's already sitting in the game directory, or exactly whatever you checked in Advanced Tweaks - see [Tweaks](#tweaks) below.
5. **Install files.** Launch scripts get written, tweak-specific files get copied in or out, and the `mods/` directory gets seeded with the base framework mods (unless you turned that off). Full breakdown in [What ends up on disk](#what-ends-up-on-disk).
6. **Record the install.** The resolved path, commit, and build type get written to a small per-user registry so `hlmod-sdk new` and `hlmod-sdk list` can find this install later without you retyping the path. This step is best-effort - if it fails for some permissions reason, the install itself has already succeeded and isn't rolled back over it.

The progress bar tracks this fairly literally: version/build lookup is the first 10%, downloading eats 10-60%, extraction 60-70%, and tweak resolution plus file copying covers the rest. Cancel is checked between download chunks and between each extracted zip member, so hitting Cancel mid-download or mid-extraction stops promptly rather than after the fact - you'll get a "cancelled" message instead of a half-extracted directory silently left behind (though it will still be there on disk; nothing cleans it up for you).

### Version and build type

The version dropdown is either "Nightly (latest, will be unstable)" or "Custom", where custom means typing in a full commit hash you got from somewhere else - a specific PR build, a known-good older nightly, whatever. There's no build browser; you're expected to already know the hash.

The build type dropdown is populated from whichever OS you're running the installer on:

| OS | Build types |
| --- | --- |
| Linux | GCC (Release), GCC (Debug), Clang (Release), Clang (Debug) |
| Windows | MSVC (Release), MSVC (Release w/ debug info), MinGW (Release) |

These map directly to the exact suffixes the nightly workflow publishes (`Linux-gcc-Release`, `Windows-msvc-RelWithDebInfo`, and so on) - see [Building](./building.md) if you want to know what these toolchains actually differ by. Release is what you want unless you have a specific reason to want debug symbols or a debug-mode HashLink VM; see [Known issues](./known-issues.md) for why MinGW in particular is a second-class citizen here.

## Tweaks

By default the installer auto-detects a small set of adjustments by poking around your game directory before it writes anything. You can override this in the "Advanced Tweaks..." dialog, and the moment you do, auto-detect is *entirely* off - the dialog says as much: with auto-detect unchecked, hlmod applies exactly the tweaks you ticked and nothing else, no steam/sdl/openal/Dead Cells detection runs at all. It's all-or-nothing, not a set of overrides layered on top of detection.

What auto-detect actually checks, and what each tweak does when applied:

- **Use the game's existing `steam.hdll`** - detected when a `steam.hdll` already exists in the game folder *and* you're on a POSIX system (Linux only; this one is deliberately not checked on Windows). If set, the game's `steam.hdll` and `libsteam_api.so` get copied into the extracted `hlmod/` directory, overwriting hlmod's bundled copies, so Steam features initialized before hlmod loads keep working against the exact Steamworks build the game shipped with.
- **Use the game's existing `sdl.hdll`** - detected when `sdl.hdll` is already present, on either OS. Copies it into `hlmod/` the same way. Useful if the game's bundled SDL has patches or a version hlmod's bundled one doesn't.
- **Use the game's existing `openal.hdll`** - detected only on Windows (`os.name == "nt"`). When applied, copies both `OpenAL32.dll` and `openal.hdll` from the game directory into `hlmod/`, if present.
- **Install the Dead Cells mod (dcmod)** - detected when a `deadcells` or `deadcells.exe` executable is sitting in the game directory. hlmod ships a bundled `dcmod` inside the archive itself; this tweak copies it from `hlmod/mods/dcmod` into your game's `mods/dcmod`. This is the one tweak that's genuinely game-specific - hlmod is trying to grow into a generic Hashlink framework, but underneath, it's still *just a Dead Cells modding tool*, and this is where that shows.
- **Skip installing base framework mods** - never auto-detected; this one only ever applies if you tick it by hand. Normally `hlobj.py`, `hlobj.pyi`, `hlvalues.py`, and the whole `modcore/` package get copied into `mods/` so `import modcore` and friends work immediately. With this tweak on, none of that happens - useful if you're deliberately vendoring your own copies, or debugging framework code in place rather than the copy the zip shipped. Note that `hlmod.pyi` (the low-level native API stub) always ships regardless of this tweak, since even bare `import hlmod` needs the stub for type checking.

## What ends up on disk

Everything the installer touches lives under two places: the new `hlmod/` directory (the extracted runtime) and your existing `mods/` directory (created if it doesn't exist yet). Installs and reinstalls only ever touch the specific framework-managed paths listed above - anything else you've put in `mods/`, your own mods or someone else's, is left completely alone, including across a version upgrade.

On Linux, `hl` and `hl.bin` get their executable bit set (in case the zip didn't preserve it), and a `run_hlmod.sh` launcher gets written next to your game executable:

```sh
#!/bin/sh

DIR=$(cd "$(dirname "$0")" && pwd)
HLMOD_DIR="$DIR/hlmod"
PY_LIB="$HLMOD_DIR/python3.13"

export PYTHONHOME="$HLMOD_DIR"
export PYTHONPATH="$PY_LIB:$PY_LIB/lib-dynload"
export LD_LIBRARY_PATH="/usr/lib/x86_64-linux-gnu:/usr/lib64:/usr/lib:/lib:$HLMOD_DIR"
exec "$HLMOD_DIR/hl.bin" "$@"
```

On Windows it's `run_hlmod.bat` instead, setting `PYTHONHOME`/`PYTHONPATH` to the `hlmod\` directory and execing `hl.exe`. Either way, the point of the launch script is the same: the embedded CPython needs `PYTHONHOME`/`PYTHONPATH` pointed at the bundled interpreter directory rather than whatever Python happens to be on your system path, and it needs the process's working directory to be the game root so relative bytecode/asset lookups behave the way the base game expects. Run the script instead of `hl`/`hl.exe` directly and both of those are handled for you.

## Installing by hand (no GUI)

If you don't want to run the Qt installer at all - CI environment, headless box, or just a preference for doing it yourself - the whole thing reduces to: unzip a `hlmod-hl-nightly-python3.13-<BuildType>.zip` build (grab one from the [Releases](https://github.com/N3rdL0rd/hlmod/releases) page or a nightly workflow run) into a `hlmod/` subdirectory of your game, then run `hl`/`hl.exe` with your working directory set to the game's root so it picks up the main bytecode automatically.

Doing it this way means you're on your own for everything the tweaks above automate: no existing-hdll swapping, no dcmod copy, no launch script, no `mods/` seeding, and no registry entry (so `hlmod-sdk list`/`hlmod-sdk new` won't know this install exists until you tell them about it - `hlmod-sdk new` can still target an unregistered path directly). For a first install this is genuinely more fiddly than it sounds; the GUI and CLI both exist mainly to save you from re-deriving this checklist every time.

## The CLI equivalent

`hlmod-sdk install <path>` runs the exact same `install()` function as the GUI, with the same tweak flags and build-type selection available from `-t`/`--tweak` and friends, and writes to the same registry. It's the better option for anything scripted or repeated - see [hlmod-sdk](./hlmod-sdk.md) for the full command reference; nothing here duplicates it.
