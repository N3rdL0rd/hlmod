# hlmod

[![Nightly Build](https://github.com/N3rdL0rd/hlmod/actions/workflows/nightly.yml/badge.svg)](https://nightly.link/N3rdL0rd/hlmod/workflows/nightly/main)

A generic modding framework for Hashlink, powered by Python. The spiritual successor to [pyhl](https://github.com/N3rdL0rd/crashlink/tree/main/pyhl).

Join the [Hashlink Modding Community Discord](https://discord.gg/Es8ZpVkPey) for support!

## Documentation

Full documentation lives in [`docs/`](docs) - installation, building, the dev
loop, mods/hooks/events, native hooking, the REPL, editor support, and more.
Start at [`docs/index.md`](docs/index.md).

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
- [x] TCP / socket REPL for interactive live inspection and runtime testing
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

See [`docs/installation.md`](docs/installation.md) for installing hlmod into
a game (a graphical installer, or manual unzip).

## Building

See [`docs/building.md`](docs/building.md) for build dependencies, compiling,
and the verification/test suites. Quick start on Linux:

```sh
just prepare
just build
just test
```

On Windows, use `just prepare-win` and `just build-win` instead (see
[`docs/building.md`](docs/building.md) for the full vcpkg/MSVC setup).

