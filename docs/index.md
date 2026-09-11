---
sidebar_position: 1
---

# hlmod

[![Nightly Build](https://github.com/N3rdL0rd/hlmod/actions/workflows/nightly.yml/badge.svg)](https://nightly.link/N3rdL0rd/hlmod/workflows/nightly/main)

A generic modding framework for Hashlink, powered by Python. The spiritual successor to [pyhl](https://github.com/N3rdL0rd/crashlink/tree/main/pyhl).

Join the [Hashlink Modding Community Discord](https://discord.gg/Es8ZpVkPey) for support!

## Why another modding framework? Don't we already have DCCM?

Astute observation! Although DCCM is fantastic and very well-developed, it exists *specifically* for Dead Cells. Although, with some work, DCCM could be generalized to other applications and games (think: Wartales, Northgard, Dune: Spice Wars, etc.), it's still *just a Dead Cells modding tool*.

hlmod aims to be a truly generic, easy-to-use Hashlink modding framework that Just Works everywhere Hashlink does. In the long run, it should be able to do everything that DCCM does, and possibly even more!

### So... why Python?

[crashlink](https://n3rdl0rd.github.io/crashlink) is written in Python already - it's a reimplementation of [hlbc](https://github.com/Gui-Yom/hlbc) written from the ground up to be dynamically scriptable, as Rust is unfortunately not. hlmod uses Python because:

- It has a great C API that can integrate pretty nicely at a low level with HL, and an accessible and controllable GC (unlike .NET, which requires more marshalling)
- It's very metaprogrammable and you can define classes and types on the fly, which offers a great option for representing HL bytecode types
- It can reuse the existing crashlink classes and datastructures with its collection of tooling, which minimizes repeated code
- I already know it really well

## Documentation

- [Installation](./installation.md)
- [Building](./building.md)
- [Dev loop](./dev-loop.md)
- [Developing outside the mods directory](./external-mods.md)
- [hlmod-sdk](./hlmod-sdk.md)
- [REPL](./repl.md)
- [Mods, hooks and events](./mods-hooks-events.md)
- [Harmony-style patches](./harmony-patches.md)
- [Hooking native functions](./native-hooks.md)
- [Resolving names to indices](./name-resolution.md)
- [GC controls](./gc-controls.md)
- [Editor support](./editor-support.md)
- [Python subclasses and native values](./subclassing.md)
- [Global configuration](./configuration.md)
- [Design philosophy](./design-philosophy.md)
- [Known issues](./known-issues.md)
- [What's changed upstream](./upstream-changes.md)
