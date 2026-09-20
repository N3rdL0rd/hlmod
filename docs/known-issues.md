---
sidebar_position: 17
---

# Known issues

Here's what's actually broken, actually limited, or actually just Like That.

## DirectX support sucks

Games ship the Haxe bindings of the `directx.hdll` they were compiled against, and that library's ABI has drifted a lot over the years. hlmod sorta tries to absorb the two ways that drift breaks a game:

- `dx.Event` has gained fields (`mouseXRel`/`mouseYRel`, `scanCode`, `dropFile`). Rather than blitting its own struct into the game's object - which shifts every later field and writes past the end of the allocation for older classes - `win_get_next_event` resolves the real field offsets from the object's own runtime type and writes only the fields that class actually has. Evoland 2, whose `dx.Event` stops at `value`, used to read a stale `wheelDelta` as its `keyCode` and die on the first keypress after a scroll with `Invalid array index -1`.
- When a primitive's C signature changed upstream (`win_clip_cursor` gained an `enable` flag, `create_depth_stencil_view` a `readOnly` flag), bytecode declaring the older arity can no longer bind and the VM aborts with `Invalid signature for function`. `directx.hdll` therefore exports the historical signatures alongside the current one as `hlp_<name>__v1`, `hlp_<name>__v2`, ..., and the module loader binds the first variant matching the bytecode, logging `bound legacy ABI variant vN`. If nothing matches it still aborts rather than guessing.

What's left is the graphics path itself: anything leaning on older DirectX bindings can still crash or segfault, and that's inherited from the bindings rather than something hlmod can paper over without rewriting a backend nobody asked us to touch. If the game ships an OpenGL executable (eg. Dead Cells), prefer it.

## Native hooking is x86-64 only

Hooking a `@:hlNative` function requires hlmod's own length disassembler to find and overwrite a safe instruction sequence at the function's entry point (see [Hooking native functions](./native-hooks.md) for the full mechanism). That disassembler only understands x86-64, and even on x86-64 it will refuse rather than guess: if it can't confidently account for at least 12 bytes of linear, non-branching instructions - because the compiler emitted something the decoder doesn't recognize, or a branch shows up too early - hooking raises `RuntimeError: Native hooking requires an x86-64 build of hlmod` or a decoder-specific message, instead of silently patching the wrong bytes. On aarch64 builds it's unconditionally unavailable for the same reason.

This is a deliberate fail-closed limit, not a bug report waiting to happen. The alternative - patching blind and hoping - produces corrupted machine code that crashes some unrelated number of instructions later, which is a miserable thing to debug. If you hit this, the native in question simply isn't a hookable one right now; bytecode-level hooking (which has no such restriction) is usually available as a fallback if there's a Haxe-level call site you can intercept instead.

## Reloading doesn't touch already-running native instances

`reload_mod` swaps out a mod's Python module state, but any native HL object that's already alive keeps the class and closures it was constructed with. This is intentional - rewriting the vtable of a live object out from under the VM is exactly the kind of thing the [design philosophy](./design-philosophy.md) says not to do - but it does mean a hot-reloaded change to, say, a subclass's `__init__` won't retroactively apply to objects that already exist. New instances pick up the change immediately.

## Windows and MinGW builds are second-class citizens

The only fully supported build targets are Linux (glibc) and Windows (MSVC). MinGW/MSYS2/Cygwin builds are provided in nightlies mostly because someone asked, not because they're exercised as thoroughly - see [Building](./building.md) for the gory compiler-flag details. macOS isn't supported at all yet; there's a `Brewfile` for the dependencies HashLink itself needs, but nobody's finished wiring up the framework or the CI leg to go with it.
