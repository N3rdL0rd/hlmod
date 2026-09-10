# hlmod

[![Nightly Build](https://github.com/N3rdL0rd/hlmod/actions/workflows/nightly.yml/badge.svg)](https://nightly.link/N3rdL0rd/hlmod/workflows/nightly/main)

A generic modding framework for Hashlink, powered by Python. The spiritual successor to [pyhl](https://github.com/N3rdL0rd/crashlink/tree/main/pyhl).

Join the [Hashlink Modding Community Discord](https://discord.gg/Es8ZpVkPey) for support!

## Introduction; Or, "Why another modding framework? Don't we already have DCCM?"

Astute observation! Although DCCM is fantastic and very well-developed, it exists *specifically* for Dead Cells. Although, with some work, DCCM could be generalized to other applications and games (think: Wartales, Northgard, Dune: Spice Wars, etc.), it's still *just a Dead Cells modding tool*.

hlmod aims to be a truly generic, easy-to-use Hashlink modding framework that Just Works everywhere Hashlink does. In the long run, it should be able to do everything that DCCM does, and possibly even more!

### So... why Python?

[crashlink](https://n3rdl0rd.github.io/crashlink) is written in Python already - it's a reimplementation of [hlbc](https://github.com/Gui-Yom/hlbc) written from the ground up to be dynamically scriptable, as Rust is unfortunately not. hlmod uses Python because:

- It has a great C API that can integrate pretty nicely at a low level with HL, and an accessible and controllable GC (unlike .NET, which requires more marshalling)
- It's very metaprogrammable and you can define classes and types on the fly, which offers a great option for representing HL bytecode types
- It can reuse the existing crashlink classes and datastructures with its collection of tooling, which minimizes repeated code
- I already know it really well

## Roadmap

- [x] Basic Python mods as modules, resolve dependencies, mod metadata
- [x] JIT hooking to Python
- [x] Basic casting of primitives from HL -> Python and Python -> HL
- [x] HNULL casting support
- [x] Obj wrappers, metaclasses and Python interfaces for HL objects
- [x] Static Obj support and global instance support
  - [x] Close the import-time lifecycle gap for static data fields
- [x] HVIRTUAL data and callable-field proxies
- [x] HENUM, HDYNOBJ and HREF wrappers plus native inspection
- [x] HBYTES buffers bounded by their real allocation (abstracts stay opaque by design)
- [x] Hook a function by name
- [x] Composable hooks, mod ownership, lifecycle and reload
- [x] Game-core event objects with large-scale broadcast dispatch
- [x] Subclass an HL object from Python with native dispatch and round-trip identity
- [x] Stub generation and editor ergonomics
- [x] Runtime lifecycle and documentation
- [x] Custom Haxe fixture coverage for hooks, closures, statics, subclasses, GC, and generated proxies
- [x] Harmony-style prefix/postfix patches sharing the same hook chain as `hook()`
- [x] Hook `@:hlNative` functions via an x86-64 inline detour, not just JIT-compiled bytecode
- [x] Global TOML-backed configuration (`modcore.config`), one section per mod
- [ ] File-watcher hot-reload (automatic mod reload on file save without game restart)
- [ ] TCP / socket REPL for interactive live inspection and runtime testing
- [ ] Deep crashlink integration: realtime bytecode poking and mid-function opcode patching
- [ ] Cleaner extension points for game-specific base mods and helper libraries
- [ ] Better packaging and release ergonomics for mods, stubs, and framework updates
- [ ] Generic Heaps.IO base library (`heapsmod`) across all Shiro / Motion Twin games:
  - [ ] Virtual filesystem PAK mounting (`hxd.fs`)
  - [ ] CastleDB table inspection, diffing and runtime patching
  - [ ] Generic `hxbit` save-game serialization hooks
- [ ] Game-specific base libraries:
  - [ ] Dead Cells (`dcmod`)
    - [ ] Custom weapon subsystem

## Installation

A graphical installer is provided that can automatically download and install hlmod in a good majority of HL games. You can get it from [the nightly.link](https://nightly.link/N3rdL0rd/hlmod/workflows/installer/main) or from the Releases.

Alternately, just unzip the build to a subdirectory of your game, then run `hl.exe` with your current working directory set at the root of the game to pick up the main bytecode automatically.

## Building

> [!NOTE]
> You can download the latest nightlies for Linux and Windows from [the nightly.link](https://nightly.link/N3rdL0rd/hlmod/workflows/nightly/main). OSX builds are NOT supported.

If you want to cross-compile locally, you can use [act](https://github.com/nektos/act).

You'll need to first satisfy all the build requirements in HL's README:

### HL Dependencies on Linux/OSX

HashLink is distributed with some graphics libraries allowing to develop various applications, you can manually disable the libraries you want to compile in Makefile.
Here's the dependencies that you install in order to compile all the libraries:

- fmt: libpng-dev libturbojpeg-dev libvorbis-dev
- openal: libopenal-dev
- sdl: libsdl2-dev libglu1-mesa-dev
- ssl: libmbedtls-dev
- uv: libuv1-dev
- sqlite: libsqlite3-dev
- hlmod: python3-dev

To install all dependencies on the latest **Ubuntu**, for example:

`sudo apt-get install libpng-dev libturbojpeg-dev libvorbis-dev libopenal-dev libsdl2-dev libglu1-mesa-dev libmbedtls-dev libuv1-dev libsqlite3-dev python3-dev`

For 16.04, see [this note](https://github.com/HaxeFoundation/hashlink/issues/147).

To install all dependencies on the latest **Fedora**, for example:

`sudo dnf install libpng-devel turbojpeg-devel libvorbis-devel openal-soft-devel SDL2-devel mesa-libGLU-devel mbedtls-devel libuv-devel python-devel sqlite-devel`

**And on OSX:**

`brew bundle` to install the dependencies listed in [Brewfile](Brewfile).

### HL Dependencies on Windows

To build all of HashLink libraries it is required to download several additional distributions, read each library README file (in hashlink/libs/xxx/README.md) for additional information.

In short you'll probably need:

- [SDL2-devel](https://github.com/libsdl-org/SDL/releases/download/release-2.30.12/SDL2-devel-2.30.12-VC.zip), extract to `<hashlink>/include/sdl`
- [openal-soft](https://github.com/kcat/openal-soft/releases/download/1.23.1/openal-soft-1.23.1-bin.zip), extract to `<hashlink>/include/openal`

You'll also need Ninja installed, do `choco install ninja` or `scoop install ninja`, depending on your package manage of choice. If you're a winget nerd, try `winget install Ninja-build.Ninja`. As well as this, `vcpkg` should be installed somewhere. I have mine at `D:\vcpkg`, so the Windows Justfile recipe is configured to use that path by default - but this can point wherever you want.

> [!NOTE]
> Building `video.hdll` is disabled, since it depends on some weird ffmpeg stuff that I'm too lazy to actually get working. I haven't seen a game that actually depends on it yet, so it's Probably Fine&trade; to just leave alone.

### Compiling

> [!WARNING]
> MacOS is not supported yet. The only supported targets are Linux (glibc) and Windows (MSVC). musl *should* work, and so should Cygwin/MinGW/MSYS2, but they are untested and unsupported. Nightly builds for MinGW are provided but are not supported and may be broken.

The Justfile has recipes in it to handle this for you:

- `prepare` and `build` on Linux
- `prepare-win` and `build-win` on Windows

Basically, this boils down to:

```sh
# For linux
mkdir -p hlmod-hl/build
pushd hlmod-hl/build
cmake -G "Ninja" ..
cmake --build . --parallel
popd
```

or

```cmd
mkdir hlmod-hl\build
"C:/Program Files (x86)/Microsoft Visual Studio/2019/Community/VC/Auxiliary/Build/vcvarsall.bat" x64
@rem Make sure to change D:/vcpkg to wherever you installed vcpkg!
cmake -G "Ninja" .. -DCMAKE_TOOLCHAIN_FILE=D:/vcpkg/scripts/buildsystems/vcpkg.cmake -DVCPKG_TARGET_TRIPLET=x64-windows
cmake --build . --parallel
cd ..
cd ..
```

Then, binaries will be at `hlmod-hl/build/bin`, as normal.

The mod resolver and proxy renderer live in `hlmod-hl/python/`, not C string
literals. CMake validates and embeds those Python sources into the executable;
deployed builds do not need the source files. Editing either source regenerates
the embedded header during the next build. Generated proxies are cached by both
the generator signature and the loaded bytecode hash.

### Verification

```sh
just build
just test            # every suite below
just test-bridge     # conversions, subclasses, GC ownership
just test-value      # enums, dynamic objects, references, inspection
just test-events      # core events, composed hooks, mod lifecycle
just test-framework   # framework units, no HL runtime required
just test-editor      # Pyright acceptance for the generated SDK
just bench            # dispatch, collector and broadcast timings
```

Each runner compiles its own Haxe fixture in debug and release and runs it in a
temporary directory containing only that fixture's mods. None of them load the
repository's game mods or Dead Cells. Coverage includes native and Python
inheritance, constructors, `super()`, virtual/direct/bound/dynamic calls,
scalar and structural conversions, worker-thread callbacks, ownership across
both collectors, hook composition across mods, unload/reload, and event
broadcast to many subscribers.

Measured on one machine (Linux, release bytecode) with `just bench`:
unhooked native calls cost about 6.5 ns, a hooked call about 200 ns, and one
million event deliveries about 0.54 s. Treat these as a local baseline, not a
guarantee.

> [!NOTE]
> The `hl` JIT VM binary expects a `./mods` directory relative to its working directory by default (override with `HLMOD_MODS_DIR`). Distribute `mods/hlobj.py`, `mods/hlvalues.py`, the `mods/modcore/` package and the `.pyi` files with your mods. Proxies under `mods/stubs/` are generated for the loaded bytecode; do not copy them between applications. `hl --generate-stubs game.hl` writes the SDK without running the game.

### Dev loop

Mods are plain Python with no compile step, so the only friction in local
iteration is noticing an edit and restarting `hl` by hand. `tools/dev.py`
closes that gap:

```sh
just dev game.hl      # or: python3 tools/dev.py game.hl --hl path/to/hl
```

It launches `hl game.hl`, watches `mods/**/*.py` (excluding the generated
`mods/stubs/` tree) plus `hlmod.toml`/`typing_overlays.json`, and restarts the
process on any change. This is a local iteration tool, not packaging: it does
not build anything and has no relation to the installer or the nightly build.

### Developing outside the mods directory

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

## Mods, hooks and events

Every mod is a module or package with a literal `MOD_INFO`. The framework loads
mods in dependency order, runs an optional `initialize()`, and owns everything a
mod registers so unloading cannot leave stale callbacks behind.

```python
MOD_INFO = {"id": "my_mod", "dependencies": ["dcmod"]}

from dcmod import events
from modcore import HookContext, hook
from stubs.pr import Game

@events.game_update.listen(priority=10)
def on_update(game: Game) -> None:
    ...

@hook(Game.update)
def wrap_update(context: HookContext[[Game], None], game: Game) -> None:
    context.call_next(game)   # run the remaining hooks, then the original
```

Hooks compose: several mods may hook the same function, highest priority first,
then registration order. `call_next` continues the chain, `call_original`
deliberately skips the rest of it. A hook that raises propagates a catchable HL
exception with the Python traceback, the function index and the owning mod; the
original never runs twice. `register_hook` returns a `Registration` that can be
closed, and unloading a mod removes its hooks and subscriptions automatically.

Game core libraries publish their own events, so other mods never need to know
which native function produces them:

```python
# In a core library such as dcmod.
from modcore import Event
game_update: Event[[Game]] = Event("dcmod.game_update")

@hook(Game.update)
def publish(context: HookContext[[Game], None], game: Game) -> None:
    context.call_next(game)
    game_update.emit(game)
```

`emit` dispatches over the snapshot taken when it starts, so subscribing or
unsubscribing during a dispatch takes effect on the next one. A subscriber that
raises `Exception` is logged with its owning mod and the remaining subscribers
still run; `BaseException` propagates.

`load_mod`, `unload_mod` and `reload_mod` manage mods at runtime. Reloading
replaces Python state, but native objects that are still alive keep the class
and closures they were created with; hlmod never frees them early.

### Harmony-style patches

`modcore.prefix_hook`/`postfix_hook`/`patch` install ordinary entries on the
same per-findex chain `hook()` uses, so plain hooks and patches on one target
interleave by priority:

```python
from modcore import patch, postfix_hook, prefix_hook

@prefix_hook(Weapon.create, priority=10)
def reject_locked(hero, item):
    if not hero.hasUnlocked(item):
        return False  # skip the original and every lower-priority hook/patch

@postfix_hook(Weapon.create, priority=0)
def log_result(result, hero, item):
    log(f"created {result}")

@patch(Weapon.create, priority=5)
class DoubleDamage:
    @staticmethod
    def postfix(result, hero, item):
        result.damage *= 2
```

A prefix returning `False` skips the rest of the chain for its own link
(neither lower-priority entries nor the original run); returning a tuple
replaces the positional arguments seen downstream; `None` continues
unchanged. A postfix's non-`None` return replaces the result. This composes
strictly (each patch wraps the *rest of the chain*, not an independent flat
list), which is narrower than C# Harmony's model but shares its ergonomics
and its one-hook-chain-per-target guarantee with DCCM's HarmonyX bridge.

### Hooking native functions

`hook()`/`register_hook()` also accept the findex of an `@:hlNative`
function, resolved with `hlmod.native_findex(lib, name)`:

```python
from modcore import hook
import hlmod

@hook(hlmod.native_findex("std", "sys_time"))
def frozen_clock(context):
    return 0.0
```

Bytecode functions are hookable because their JIT-compiled bodies carry an
injected check; natives are raw C pointers with no such body, and every
caller bakes their address in as a constant at JIT-compile time. The first
hook on a native lazily installs a small x86-64 inline detour at its entry
point instead, so `call_next`/`call_original` and hook composition behave
identically either way. Installing the detour requires hlmod to recognize a
safely-overwritable instruction sequence at the native's entry; if it can't,
hooking raises `RuntimeError` rather than guessing at an instruction
boundary. x86-64 only, matching hlmod's supported JIT targets.

### Resolving names to indices

`hlmod.findex_for_name("$Class.method")` resolves a bytecode function; the
companion `hlmod.type_index_for_name("Class")` resolves an obj/struct/enum
type the same way, for `alloc_obj`, `create_subclass`, `enum_new`, and
anywhere else a type index is otherwise a hardcoded magic number. Both raise
rather than guess when nothing matches (`KeyError` for a missing type,
`NameError` for a missing function).

### GC controls

`hlmod.gc_major()` forces a full collection; `hlmod.gc_stats()` returns a
dict of `total_allocated`/`allocation_count`/`current_memory`;
`hlmod.gc_enable(bool)` toggles collection without stopping allocation.
`hlmod.is_gc_ptr(ptr)`/`hlmod.gc_memsize(ptr)` report whether an `HlPtr` is
GC-managed and its allocation size, for diagnosing memory pressure from a
mod without an external profiler attached.


### Editor support

Generated proxies ship with `.pyi` interfaces, so a type checker infers
`BridgeBase(1)` as `BridgeBase`, checks constructor and method arguments, field
types, overrides, hook signatures and event payloads. Point your editor at the
`mods` directory. Where the bytecode has erased detail, such as native array
element types, `mods/typing_overlays.json` supplies annotations that apply only
to the generated interfaces:

```json
{"version": 1,
 "imports": {"NativeArray": "hlobj.HlArray"},
 "types": {"pr.Game": {"fields": {"players": "NativeArray[int] | None"}}}}
```

## Python subclasses and native values

Generated object classes can be constructed and subclassed normally:

```python
from stubs import BridgeBase

class Offset(BridgeBase):
    def __init__(self, value: int):
        super().__init__(value)  # Runs the native constructor on this instance.
        self.offset = 100       # Python-only state.

    def compute(self, delta: int) -> int:
        return super().compute(delta) + self.offset

obj = Offset(10)
obj.value = 20                  # Writes the inherited native field.
```

Passing `obj` to a compatible HL parameter passes a real native subtype. HL method
calls reach its Python overrides; returning it through a base-class or `Dynamic`
value recovers the original Python instance, including Python-only state. Native
instances of the base class are unaffected. Wrapping an existing native object
does not run Python `__init__`. Ordinary Python mixins are supported, but multiple
native bases are rejected.

Native fields keep their HL layout and types. New Python attributes are not new
HL fields; class defaults/properties that shadow native data fields are rejected.
Native dynamic-method fields are live: assigning a compatible Python callable
changes subsequent calls from both languages. Explicit base calls and `super()`
still execute the selected base implementation. Calls already inlined by Haxe
cannot be intercepted after compilation.

### Conversion and ownership rules

- Native object, virtual, closure, and array wrappers carry their actual HL type
  and keep their native allocations alive. HL-held Python objects and callbacks
  retain their Python state; unreachable cross-runtime cycles are collected.
- `None` represents null pointer/nullable values, not scalar zero. Pointer-value
  annotations include `None`, since bytecode does not retain non-null guarantees.
- Integers are range-checked, including signed 64-bit values. `Bool` requires a
  Python `bool`. Strings preserve UTF-16 contents, embedded NULs, and leading BOM
  characters. Incompatible object and closure types raise `TypeError`.
- `HlArray` is a live native-array proxy, not a copied Python list. Its indexing
  reads/writes native storage; `HlArray.create(type_index, values)` creates
  an array with an explicit element type. Plain lists are not implicitly cast to
  HL native arrays: an `HARRAY` signature does not encode its element type.
- Python callables become typed HL closures when the receiving signature is
  known. Ambiguous `Dynamic` callbacks need an explicit signature through
  `hlmod.make_callback`. Python callback exceptions become catchable HL exceptions;
  HL exceptions in calls from Python become `RuntimeError`.
- Raw `HlPtr(address, kind)` values are opaque and untrusted. Integer addresses
  and untrusted pointers cannot be used as typed objects, arrays, or closures.
- `HlEnum`, `HlDynObject`, `HlRef[T]` and `HlBytes` wrap native enums, dynamic
  records, references and byte buffers; `inspect_native` reports real runtime
  fields, methods and enum constructors. Abstracts stay opaque `HlPtr` values by
  design. Packed/GUID values and unsupported struct/callback layouts raise
  explicit errors rather than guessing memory layout.
- Enum values compare structurally, like `Type.enumEq`: HL shares pointers only
  for compiler-created constants. Constructor *parameter names* are absent from
  bytecode, so parameters are positional.
- `HlBytes` bounds every read and write by the buffer's real allocation. HL
  bytes carry no length, so a wrapper knows its length only when Python
  allocated it, otherwise it reports the allocation size; buffers HL never
  allocated have no discoverable size and stay unreadable. Passing `bytes`
  where HL expects `hl.Bytes` copies into a GC-owned buffer, so pass `HlBytes`
  when both sides must share storage.
- Calls through HL's dynamic dispatcher accept at most nine arguments, counting
  a bound receiver. Native fields/static globals still follow HL initialization:
  import-time static reads may expose default values before Haxe initialization.

## Global configuration

`modcore.config` stores mod settings in one `hlmod.toml` file, one table per
mod, deliberately not JSON:

```python
from modcore import config

settings = config.section(defaults={"volume": 5, "show_hud": True})
settings["volume"] = 8   # marks the file dirty
```

`section()` defaults to the currently-loading mod's id and fills in any key
missing from the file (so a fresh install always ends up with a complete,
saved config), without touching keys a user already changed. The file is
written automatically when mods shut down, or immediately via
`config.save()`. `tomllib` (stdlib since Python 3.11) reads the file back;
since it's read-only, hlmod ships a small writer (`modcore._toml_writer`)
covering the value shapes a config file actually needs - bool, int, float,
str, list, and nested tables - rather than pull in a third-party TOML
dependency for round-tripping plain data.

## Design Philosophy

- Modify the JIT compiler as LITTLE as possible. The more assembly we generate, the more unstable the VM becomes. Keep your ASM short, and write trampolines to C instead of full routines.
- The end user shouldn't have to memorize internal HL incantations to be able to write a basic mod. When in doubt, cast to and from a similar builtin Python class rather than write a full wrapper that may have incompatibilities with Python's `std`.
- Keep low-level APIs on the C side, then wrap them in nice Pythonic functions in `modcore`. For example, `hlmod.register_hook` is wrapped by a Pythonic decorator in `modcore.hook`.

## Known Issues

- Anything that depends on older versions of HL's DirectX APIs will crash and sometimes even segfault.
  - Dead Cells provides an OpenGL-only executable, use that if possible.
- Native hooking is x86-64 only and requires hlmod to recognize a safely
  overwritable instruction sequence at the target's entry point; a native
  compiled with an unrecognized prologue raises `RuntimeError` instead of
  installing a hook. This is a deliberate fail-closed limit, not a bug: see
  "Hooking native functions" above.

## What's Changed?

In the HL VM, a few fixes and tweaks have been made or merged from upstream PRs:

- HaxeFoundation/hashlink#795 (Add newline to `--version` print)
- HaxeFoundation/hashlink#482 and HaxeFoundation/hashlink#831 (Fix MinGW build)
- HaxeFoundation/hashlink#856 (Fix `hl_dyni32` for systems with unsigned `char`,
  plus its `2cd7a78` prerequisite optimizing small `null<int>` allocation)
- HaxeFoundation/hashlink#940 (Fix `Reflect.compare` on overflow values)
- `0da6cb5` (Fixed a potential buffer overflow when compact align passes bounds)
- HaxeFoundation/hashlink#867 (Fix a GC segfault from allocation tracking)
- HaxeFoundation/hashlink#872 (Fix `Single` large-value printing to an empty string)
- HaxeFoundation/hashlink#868 (Add `hl_gc_safepoint`)
- `cab50ba` (Fixed a `check_same_type` stack overflow with hot-reloaded plugins)
- HaxeFoundation/hashlink#949 (Fix x86 register names leaking into aarch64 profiles)
- HaxeFoundation/hashlink#870 (Fix a null access in `ProfileGen.hx` on a
  finished thread, the flamegraph converter referenced above)

