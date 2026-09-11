---
sidebar_position: 3
---

# Building

`hlmod-hl` is not a Haxe library you `haxelib install` and forget about - it's a fork of HashLink itself, with a CPython interpreter, a JIT hooking engine, and a native x86-64 disassembler wired directly into the VM's C sources. There's no prebuilt upstream `hl` binary you can bolt Python onto afterward; the hooking machinery lives inside `jit.c`'s code generation and the module loader's startup sequence, so building hlmod means building the whole virtual machine from source, the same way you'd build stock HashLink, plus roughly twenty extra `.c` files and an embedded Python runtime linked straight into the executable.

:::note

You can download the latest nightlies for Linux and Windows from [the nightly.link](https://nightly.link/N3rdL0rd/hlmod/workflows/nightly/main). OSX builds are NOT supported.

:::

If you want to cross-compile locally, you can use [act](https://github.com/nektos/act).

You'll need to first satisfy all the build requirements in HL's README:

## HL Dependencies on Linux/OSX

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

`brew bundle` to install the dependencies listed in [Brewfile](https://github.com/N3rdL0rd/hlmod/blob/main/Brewfile).

Notice the extra `hlmod` row: everything above it is a stock HashLink graphics/runtime dependency, unrelated to modding. The `python3-dev`/`python-devel` package is the one hlmod actually needs, because `CMakeLists.txt` calls `find_package(Python COMPONENTS Interpreter Development REQUIRED)` and links the `hl` executable against `Python::Python` directly - the interpreter isn't shelled out to, it's part of the binary.

## HL Dependencies on Windows

To build all of HashLink libraries it is required to download several additional distributions, read each library README file (in hashlink/libs/xxx/README.md) for additional information.

In short you'll probably need:

- [SDL2-devel](https://github.com/libsdl-org/SDL/releases/download/release-2.30.12/SDL2-devel-2.30.12-VC.zip), extract to `<hashlink>/include/sdl`
- [openal-soft](https://github.com/kcat/openal-soft/releases/download/1.23.1/openal-soft-1.23.1-bin.zip), extract to `<hashlink>/include/openal`

You'll also need Ninja installed, do `choco install ninja` or `scoop install ninja`, depending on your package manage of choice. If you're a winget nerd, try `winget install Ninja-build.Ninja`. As well as this, `vcpkg` should be installed somewhere. I have mine at `D:\vcpkg`, so the Windows Justfile recipe is configured to use that path by default - but this can point wherever you want.

:::note

Building `video.hdll` is disabled, since it depends on some weird ffmpeg stuff that I'm too lazy to actually get working. I haven't seen a game that actually depends on it yet, so it's Probably Fine&trade; to just leave alone.

:::

## Compiling

:::warning

MacOS is not supported yet. The only supported targets are Linux (glibc) and Windows (MSVC). musl *should* work, and so should Cygwin/MinGW/MSYS2, but they are untested and unsupported. Nightly builds for MinGW are provided but are not supported and may be broken.

:::

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

### What CMake is actually building

`hlmod-hl/CMakeLists.txt` builds two targets: `libhl`, the shared runtime library (GC, arrays, bytes, regex, sockets, threads - bundled PCRE2 plus the usual `src/std/*.c` files, essentially unmodified stock HashLink), and `hl`, the executable. All of hlmod's own code lives in the `hl` executable target, gated behind an `option(WITH_VM ...)` flag that defaults on everywhere except 32/64-bit ARM builds not targeting `x86_64` (where it defaults off, since the native hooking disassembler and JIT trampolines are x86-64-only - see [Known issues](./known-issues.md)). On top of the stock VM sources (`code.c`, `jit.c`, `main.c`, `module.c`, `debugger.c`, `profile.c`), the executable links roughly twenty hlmod-specific files: `hlmod_jit_hook.c` and `native_hook.c` implement the bytecode and native hooking paths described in [Design philosophy](./design-philosophy.md), `mod_loader.c` and `hook_registry.c` own mod discovery and lifecycle, `hlmod_python.c` and `py_module.c` bridge to the embedded interpreter, `hlmod_repl.c` serves the [native REPL](./repl.md), and `hlmod_codegen.c` turns runtime type metadata into the generated SDK. `find_package(Python ... Development REQUIRED)` only runs when `WITH_VM` is on - a `libhl`-only build (rare, but the option exists) never needs a Python dev install at all.

If you're on MSVC, one file - `native_hook.c` - gets built as its own object library with `C_STANDARD 90` instead of the project-wide C11, because Windows' own headers rely on Microsoft's anonymous-struct extensions that `/std:c11`'s strict ISO mode rejects. It's a narrow, deliberate carve-out, not a sign the rest of the codebase is loose about standards.

### The embedded Python sources

The mod dependency resolver and the proxy/SDK renderer live as ordinary, editable files in `hlmod-hl/python/` - `mod_sorter.py` (topologically sorts mods by their declared `MOD_INFO` dependencies) and `stub_renderer.py` (turns native type metadata into importable `.pyi`/proxy modules) - not as C string literals hand-escaped into the source tree. A CMake custom command runs `hlmod-hl/python/embed.py` during configure/build to turn both into a generated header (`generated/hlmod_embedded.h`) that gets compiled straight into the `hl` binary.

`embed.py` does three things for each `--module SYMBOL PATH` pair: it `compile()`s the source to catch syntax errors at build time rather than at some player's first launch, rejects any file containing a NUL byte (which would truncate the C string), and emits it as a `static const char SYMBOL[]` byte array rather than a literal string - sidestepping the various platform limits on how long a single string literal is allowed to be. It also hashes every embedded module's name and bytes, plus the contents of `src/hlmod_codegen.c` (passed via `--hash-file`), into a `SOURCE_FILE_SHA256_HASH` macro. `hlmod_codegen.c` passes that hash straight into `stub_renderer.generate()`, which is how "generated proxies are cached by both the generator signature and the loaded bytecode hash" (see [Editor support](./editor-support.md)) actually works - change either script or `hlmod_codegen.c` and every cached proxy invalidates itself automatically, rather than silently going stale.

At runtime, `mod_loader.c` and `hlmod_codegen.c` don't read `.py` files off disk for these two modules at all - they call `Py_CompileString()` directly on the embedded `hlmod_mod_sorter_source`/`hlmod_stub_renderer_source` byte arrays and execute the result in-process. That's the actual payoff: a deployed build is one self-contained binary with no companion script files to ship, version, or accidentally leave behind on a player's disk out of sync with the binary that expects them. Editing either source under `hlmod-hl/python/` and rebuilding regenerates the header automatically - the custom command's `DEPENDS` list covers `embed.py`, `mod_sorter.py`, `stub_renderer.py`, and `hlmod_codegen.c`, so CMake reruns it whenever any of them change.

## Verification

```sh
just build
just test            # every suite below except test-editor and bench
just test-bridge     # conversions, subclasses, GC ownership
just test-value      # enums, dynamic objects, references, inspection
just test-events      # core events, composed hooks, mod lifecycle
just test-harmony     # Harmony-style prefix/postfix patches, native-hook decoder
just test-devloop     # tools/dev.py restart-on-change, including --extra-mods
just test-sdk         # hlmod SDK CLI: install registry, scaffolding, discovery
just test-framework   # framework units, no HL runtime required
just test-repl        # native REPL protocol, isolation, idle-client shutdown
just test-editor      # Pyright acceptance for the generated SDK
just bench            # dispatch, collector and broadcast timings
```

`just test` runs `test-framework`, `test-bridge`, `test-value`, `test-events`, `test-harmony`, `test-devloop`, `test-sdk`, and `test-repl`. `test-editor` and `bench` are deliberately left out of the default run - the first needs a Pyright binary on hand (see the recipe's `pyright="pyright"` argument, e.g. `uvx --from pyright which pyright`), and the second reports timings rather than pass/fail, so bundling it into a suite that's supposed to give you a clean yes/no would be actively misleading.

Every suite that touches the compiled VM (`bridge`, `value`, `events`, `harmony`, `devloop`, `repl`, `performance`) does the same thing under the hood: it creates its own `tempfile.TemporaryDirectory`, copies in only `mods/hlobj.py`, `mods/hlvalues.py`, `mods/modcore/`, and that suite's own fixture module, compiles a purpose-built Haxe fixture against `hlmod-hl/build/bin/hl` in both debug and release, and greps the fixture's stdout for suite-specific completion markers before declaring victory. None of them touch the repository's real `mods/` directory or load Dead Cells - if a suite passes, it's because *that fixture, in isolation*, produced the expected output, not because something happened to work against whatever mods happen to be lying around on your machine. A few suites go further than a single fixture run:

- **`test-bridge`** compiles `BridgeFixture.hx` and checks for `PYTHON_BRIDGE_CHECKS_OK`, `PYTHON_BRIDGE_GC_OK`, and `BRIDGE_FIXTURE_OK` - covering native/Python type casting, subclassing across the boundary, and GC ownership handoff between HashLink's collector and Python's.
- **`test-value`** checks `PYTHON_VALUE_CHECKS_OK`, `PYTHON_GC_CHECKS_OK`, `PYTHON_REF_CHECKS_OK`, `VALUE_FIXTURE_OK` - enum values, dynamic objects, `HlRef` references, and structural inspection of native values from Python.
- **`test-events`** runs its own fixture, then three extra isolated checks: that a mod raising on import aborts startup with a clear banner printed to stderr *before* the raw traceback (not buried after it); that a mod's source doesn't have to live inside the game's own `mods/` directory as long as it can still see `hlobj.py`, `hlvalues.py`, and `modcore`; and that `HLMOD_MODS_DIR` can relocate the *primary* mods directory itself, stubs included, not just add extra search paths.
- **`test-harmony`** checks `NATIVE_HOOK_DECODER_OK` and `HARMONY_FIXTURE_OK` - Harmony-style prefix/postfix patch composition and the native-hook length disassembler described in [Hooking native functions](./native-hooks.md).
- **`test-devloop`** drives `tools/dev.py` against a live `hl` process over stdout, confirming it restarts the process when a mod's Python source changes, plus a second check that `--extra-mods` watches a directory outside the primary mods folder too. See [Dev loop](./dev-loop.md).
- **`test-sdk`** (`cd sdk && uv run python3 -m unittest discover -s tests`) is the one suite that never touches `hl` at all - it exercises the `hlmod_sdk` CLI's install registry, project scaffolding, and installer logic entirely against temporary directories and a patched registry path, with no real HashLink install involved.
- **`test-framework`** (`python3 -m unittest discover -s tests/framework`) is pure Python and needs no HL runtime or Haxe compiler: `Event` priority ordering and exception isolation, mod load/reload/unload lifecycle, stub-package loading, TOML config round-tripping, and `stub_renderer`'s `.pyi` body generation, all against `modcore` directly. Native hook-chain composition is deliberately left to the bridge fixture instead of being re-tested here.
- **`test-repl`** starts a real `hl` process running `ReplFixture.hx`, connects over the loopback socket the [native REPL](./repl.md) listens on, and drives the actual wire protocol: shorthand commands, expression vs. statement evaluation, multi-line buffering, exception reporting, per-connection namespace isolation, and - critically - that shutdown never hangs waiting on a client that's just sitting there idle.
- **`test-editor`** feeds known-good and known-bad Python snippets through Pyright against a freshly generated SDK, confirming that valid programs type-check (inferred return types, overload resolution, the works) *and* that invalid ones are rejected, plus that the overlay cache behaves. See [Editor support](./editor-support.md).

Measured on one machine (Linux, release bytecode) with `just bench`:
unhooked native calls cost about 6.5 ns, a hooked call about 200 ns, and one
million event deliveries about 0.54 s.

:::note

The `hl` JIT VM binary expects a `./mods` directory relative to its working directory by default (override with `HLMOD_MODS_DIR`). Distribute `mods/hlobj.py`, `mods/hlvalues.py`, the `mods/modcore/` package and the `.pyi` files with your mods. Proxies under `mods/stubs/` are generated for the loaded bytecode; do not copy them between applications. `hl --generate-stubs game.hl` writes the SDK without running the game.

:::
