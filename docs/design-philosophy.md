---
sidebar_position: 16
---

# Design philosophy

A few opinions have shaped hlmod along the way, usually learned the hard way. Written down here so nobody - including future me - has to relearn them by breaking something first.

## Modify the JIT as little as possible

Hashlink's JIT compiler is the part of this whole enterprise that is genuinely terrifying to touch. It's hand-written machine code generation, per-architecture, and every byte you add is a byte that can misalign a stack frame or clobber a register some later instruction assumed was still alive. hlmod's rule is: keep the generated assembly *short*, and write trampolines to C instead of full routines. When a bytecode function gets hooked, the JIT injects a small check and a call out to `jit_dispatch_hook`; the actual dispatch, argument marshalling, and Python invocation all happen in ordinary C, where mistakes produce a segfault with a stack trace instead of a silent VM corruption three functions later.

The native-hook engine (see [Hooking native functions](./native-hooks.md)) takes this further than the bytecode path has to: since a `@:hlNative` function has no JIT-injected check to begin with, hooking one means overwriting its actual machine code with a jump. hlmod's disassembler is deliberately conservative here - it will only patch a prologue it can *prove* is at least 12 bytes of linear, non-branching instructions, and refuses with a clear `RuntimeError` the moment it isn't sure. Guessing wrong about instruction boundaries in someone else's compiled code is how you get a corrupted binary that crashes ten thousand instructions away from the actual mistake; failing loudly at the point of the mistake is much, much cheaper to debug, even though it means some natives simply can't be hooked.

## Nobody should have to memorize HL internals to write a mod

The bytecode format has opinions about how integers, arrays, and dynamic values are represented, and approximately none of those opinions are ones a mod author should need to internalize. When there's a builtin Python type that behaves close enough to the HL equivalent, hlmod casts to it rather than inventing a bespoke wrapper class with its own quirks to learn. `HlArray` acts like a Python sequence because iterating and indexing are exactly what people already know how to do with one; the moment a wrapper starts requiring you to remember *its* rules instead of Python's, something has gone wrong upstream in the design.

This is also why `hlobj.HlObjectMeta` leans hard on Python's metaclass machinery instead of a code-generation step you have to run and re-run - a generated proxy class can be subclassed, have its methods overridden, and generally be treated like *a normal Python class*, because underneath it is one. It just also happens to know how to talk to the native side. See [Python subclasses and native values](./subclassing.md) for what that buys you in practice.

## Low-level on the C side, Pythonic on top

The native module (imported as `hlmod`) is intentionally boring and mechanical: `register_hook`, `findex_for_name`, `native_findex`, `gc_major`, and so on are thin, direct bindings to what the C runtime can actually do, with none of the ergonomics. `modcore` is where those primitives get wrapped in something a mod author would actually want to write. `hlmod.register_hook` returns a raw registration handle and expects you to manage its lifetime yourself; `modcore.hook` wraps it in a decorator that infers the target from a generated method reference, composes cleanly with every other hook on the same function, and ties its lifetime to the owning mod automatically, so unloading the mod cleans it up without anyone having to remember to call anything.

The rule of thumb: if a capability is genuinely new, it goes in C, next to the VM internals it depends on. If it's really just a nicer way to call something that already exists, it goes in `modcore`, in Python, where it's easy to read, easy to change, and easy to get right on the first try.
