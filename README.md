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
- [ ] Static Obj support and global instance support
- [ ] HVIRTUAL, HABSTRACT, and other types
- [ ] Hook a function by name
- [ ] Better HENUM support
- [ ] Subclass an HL object from Python, or define a Python class and make it available as an HL Obj
  - [ ] Types and intellisense for HL Objs?
- [ ] Common base lib mods for specific games and libs:
  - [ ] Heaps.IO base
    - [ ] Bundled PAK loading
    - [ ] Dead Cells
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

> [!NOTE]
> The `hl` JIT VM binary built from `hlmod-hl` expects there to be a directory `./mods` from the working dir, containing mods to be loaded! You should copy over `hlmod.pyi` and `modcore.py` from this repo's `mods/` directory as the base library for other mods to reference.

## Design Philosophy

- Modify the JIT compiler as LITTLE as possible. The more assembly we generate, the more unstable the VM becomes. Keep your ASM short, and write trampolines to C instead of full routines.
- The end user shouldn't have to memorize internal HL incantations to be able to write a basic mod. When in doubt, cast to and from a similar builtin Python class rather than write a full wrapper that may have incompatibilities with Python's `std`.
- Keep low-level APIs on the C side, then wrap them in nice Pythonic functions in `modcore`. For example, `hlmod.register_hook` is wrapped by a Pythonic decorator in `modcore.hook`.

## Known Issues

- Anything that depends on older versions of HL's DirectX APIs will crash and sometimes even segfault.
  - Dead Cells provides an OpenGL-only executable, use that if possible.

## What's Changed?

In the HL VM, a few fixes and tweaks have been made or merged from upstream PRs:

- HaxeFoundation/hashlink#795 (Add newline to `--version` print)
- HaxeFoundation/hashlink#482 and HaxeFoundation/hashlink#831 (Fix MinGW build)
