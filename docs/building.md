---
sidebar_position: 3
---

# Building

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

The mod resolver and proxy renderer live in `hlmod-hl/python/`, not C string
literals. CMake validates and embeds those Python sources into the executable;
deployed builds do not need the source files. Editing either source regenerates
the embedded header during the next build. Generated proxies are cached by both
the generator signature and the loaded bytecode hash.

## Verification

```sh
just build
just test            # every suite below
just test-bridge     # conversions, subclasses, GC ownership
just test-value      # enums, dynamic objects, references, inspection
just test-events      # core events, composed hooks, mod lifecycle
just test-framework   # framework units, no HL runtime required
just test-repl        # native REPL protocol, isolation, idle-client shutdown
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

:::note

The `hl` JIT VM binary expects a `./mods` directory relative to its working directory by default (override with `HLMOD_MODS_DIR`). Distribute `mods/hlobj.py`, `mods/hlvalues.py`, the `mods/modcore/` package and the `.pyi` files with your mods. Proxies under `mods/stubs/` are generated for the loaded bytecode; do not copy them between applications. `hl --generate-stubs game.hl` writes the SDK without running the game.

:::
