---
sidebar_position: 1
---

# hlmod

[![Nightly Build](https://github.com/N3rdL0rd/hlmod/actions/workflows/nightly.yml/badge.svg)](https://nightly.link/N3rdL0rd/hlmod/workflows/nightly/main)

hlmod is a generic modding framework for Hashlink, the VM that runs Haxe games like Dead Cells, Northgard, Wartales, and a surprising number of other things you didn't know were Haxe. It's powered by Python: hlmod embeds a real CPython interpreter directly inside the game process, wires it into HL's own JIT and garbage collector at the C level, and lets you write mods as ordinary Python modules that hook, subclass, and generally rummage around in the game's actual bytecode while it's running. It's the spiritual successor to [pyhl](https://github.com/N3rdL0rd/crashlink/tree/main/pyhl), which was the same idea with considerably more duct tape (and segfaults).

Join the [Hashlink Modding Community Discord](https://discord.gg/Es8ZpVkPey) for support!

## "Why another modding framework? Don't we already have DCCM?"

Astute observation! Although DCCM is fantastic and very well-developed, it exists *specifically* for Dead Cells. Although, with some work, DCCM could be generalized to other applications and games (think: Wartales, Northgard, Dune: Spice Wars, etc.), it's still *just a Dead Cells modding tool*.

hlmod aims to be a truly generic, easy-to-use Hashlink modding framework that Just Works everywhere Hashlink does. In the long run, it should be able to do everything that DCCM does, and possibly even more!

### So... why Python?

[crashlink](https://n3rdl0rd.github.io/crashlink) is written in Python already - it's a reimplementation of [hlbc](https://github.com/Gui-Yom/hlbc) written from the ground up to be dynamically scriptable, as Rust is unfortunately not. hlmod uses Python because:

- It has a great C API that can integrate pretty nicely at a low level with HL, and an accessible and controllable GC (unlike .NET, which requires more marshalling)
- It's very metaprogrammable and you can define classes and types on the fly, which offers a great option for representing HL bytecode types
- It can reuse the existing crashlink classes and datastructures with its collection of tooling, which minimizes repeated code
- I already know it really well

## The shape of the thing

hlmod is really three layers:

1. **`hlmod-hl`** - a fork of HashLink itself (the `hl` executable and its JIT), patched to embed CPython, expose native HL internals (types, functions, the GC) to Python, and support hooking both JIT-compiled bytecode functions and raw `@:hlNative` functions via an inline x86-64 detour. This is the only part written in C, and deliberately so - see [Design philosophy](./design-philosophy.md) for the reasoning.
2. **`modcore`** - the Pythonic standard library that sits on top of the raw native bindings: mod discovery and lifecycle, composable hooks, an event system, Harmony-style patches, TOML config, and the native REPL. If you're writing a mod, this is almost everything you'll `import`.
3. **Your mods** - a Python module or package with a `MOD_INFO` dict, living in the game's `mods/` directory (or somewhere else entirely, see [Developing outside the mods directory](./external-mods.md)), doing whatever it is you're here to do.
