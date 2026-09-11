---
sidebar_position: 10
---

# Hooking native functions

`hook()`/`register_hook()` also accept the findex of an `@:hlNative` function,
resolved with `hlmod.native_findex(lib, name)`:

```python
from modcore import hook
import hlmod

@hook(hlmod.native_findex("std", "sys_time"))
def frozen_clock(context):
    return 0.0
```

From the mod author's side this looks exactly like hooking a Haxe function -
same decorator, same `HookContext`, same `call_next`/`call_original`. Under the
hood it's a completely different mechanism, because natives aren't compiled by
HL's JIT at all; they're plain C functions the runtime `dlsym`s (or
`GetProcAddress`s) once at startup and never touches again. Making one
hookable means editing its actual machine code in place, which is a much
scarier operation than anything the bytecode hook path has to do, and it's
worth understanding why before you rely on it.

## Why bytecode functions are easy and natives aren't

Every HL bytecode function's JIT-compiled body carries a small check hlmod
injects at compile time: on entry, ask the hook registry (`hook_registry.c`)
whether this findex has a Python callback installed, and if so, jump into
`jit_dispatch_hook` instead of running the function's own body. Installing a
hook later just flips a flag the already-compiled prologue is already
checking - no existing machine code needs to move. That's the whole trick
behind [mods, hooks and events](./mods-hooks-events.md).

Natives get no such check, because there's no HL-JIT-compiled body to inject
it into. A `@:hlNative` function is a raw C pointer, resolved once and stored
in `functions_ptrs[findex]`. Every *caller* of that native - itself
JIT-compiled bytecode - bakes the resolved address in as an immediate
constant at JIT-compile time (`op_call_fun`'s native branch, in `jit.c`).
Patching `functions_ptrs[findex]` after the fact does precisely nothing for
callers that already exist, because they never read that array again; they
call the address they compiled in directly. The only way to intercept an
already-running native, short of recompiling every caller, is to redirect the
native's own entry point in memory, so every existing and future caller lands
somewhere else without needing to know it happened.

That's an inline detour: hlmod's native-hook engine (`native_hook.c`)
overwrites the first several bytes at the native's address with a jump to a
generated landing stub. It's the same category of technique tools like
minhook use, implemented narrowly enough to fit hlmod's one use case. The
[design philosophy](./design-philosophy.md#modify-the-jit-as-little-as-possible)
page has more on why this gets treated as the riskier of the two hook paths
even though both end up calling into the same Python dispatch.

## What actually happens on the first hook

`register_hook`/`hook()` resolve to the same C entry point
(`hlmod_register_hook`, in `hook_registry.c`) regardless of whether the
findex names a bytecode function or a native - it looks up
`functions_indexes[findex]` and checks whether that index falls in the
native range. If it does, it calls
`hlmod_native_hook_ensure_installed(findex, native->t)` before installing the
Python callback; the detour is only ever installed once per findex
(`g_installed_native_hooks` tracks that), and it's idempotent - later hooks
on an already-detoured native just add another entry to the same Python hook
chain used for bytecode functions (`modcore._hooks._HookChain`).

Installing the detour itself goes through a few steps, in order:

1. **Resolve the real target.** `resolve_jmp_chain` walks past any 5-byte
   `jmp rel32` thunk MSVC's `/INCREMENTAL` linking inserts in front of a
   function in Debug/RelWithDebInfo builds, so both the thunk and any direct
   internal caller end up intercepted the same way.
2. **Decode a safe prologue.** A conservative length disassembler
   (`safe_prologue_len_ex`/`decode_one`) walks instructions one at a time
   from the native's entry point until it has accounted for at least 14
   bytes (`HLMOD_JUMP_SIZE`) of linear, non-branching prologue - exactly
   enough to safely overwrite with the `jmp qword ptr [rip+0]` detour it's
   about to write. It only recognizes a narrow, explicit set of encodings
   compilers actually emit in function prologues: register push/pop,
   `mov`/`lea` with common addressing modes, `endbr64`, small immediate
   loads, and a handful of SSE/SSE2 load-store-zero forms for
   float-returning natives. Anything it doesn't recognize, or any
   control-flow instruction (`ret`, `jmp`, a conditional jump, `call`
   through a register) reached before 14 bytes are covered, aborts the scan
   rather than guessing at where the next instruction starts.
3. **Build a resume trampoline.** The decoded prologue bytes are copied
   verbatim into a small block of freshly allocated executable memory,
   followed by a jump back to the native's own code right after the copied
   bytes. Any RIP-relative reference inside those bytes - a `call rel32`, or
   a `[rip+disp32]` load of a constant or global - gets its displacement
   recomputed for the trampoline's new address, since x86-64 RIP-relative
   addressing is only valid relative to *where the instruction actually is*.
   This trampoline becomes what `call_original`/`call_next` eventually call
   through; it's tracked as `HlmodNativeHookCtx.original`.
4. **Generate the landing stub.** `hl_jit_native_hook_adapter` (in `jit.c`,
   right alongside the bytecode-side `hl_jit_python_adapter` it mirrors)
   emits a small stub matching the native's real platform calling
   convention. On entry it marshals the incoming call into hlmod's ordinary
   findex hook dispatch (`jit_dispatch_hook`) - the exact same dispatch and
   Python hook chain machinery already used for bytecode functions - and
   when nothing in the chain short-circuits with `call_original`, it
   eventually calls back into `hookctx->original` (the trampoline from step
   3) via HL's generic dynamic-call machinery, the same mechanism
   `HlHook.call_original` uses on the bytecode side.
5. **Patch the entry point.** The native's own memory page is made writable
   (`VirtualProtect`/`mprotect`), the detour jump to the landing stub is
   written over the bytes the disassembler accounted for, and the page is
   restored to executable. Every existing compiled caller, and every future
   one, now lands in the stub without recompiling anything.

Everything after that point is identical to the bytecode path: `call_next`
walks the rest of the Python hook chain, `call_original` calls straight
through to the trampoline, hooks compose by priority the same way, and
`HookContext` behaves the same regardless of which kind of function you
hooked.

## What can go wrong, and what it says when it does

This is deliberately a fail-closed subsystem: if hlmod isn't confident it can
patch a given native's entry point correctly, it refuses and raises rather
than patch blind. The concrete failure modes, and their exact messages:

- **Unsupported architecture.** Native hooking is compiled in only for
  x86-64, non-console builds. Anywhere else (aarch64, console targets), the
  stub function is a one-liner that always raises:
  `RuntimeError: Native hooking requires an x86-64 build of hlmod`.
- **Native not resolved yet.** If `functions_ptrs[findex]` is still null -
  the native hasn't been linked into the running module - hooking raises
  `RuntimeError: This native has not been resolved yet`.
- **No safe prologue found.** If the length disassembler can't confidently
  account for at least 14 bytes of linear, non-branching instructions, it
  raises `RuntimeError: Cannot safely hook this native: no recognizable
  >=14 byte prologue at its entry point`, along with the first 8 raw bytes
  it was looking at, so you can see exactly what it choked on.
- **Too many relocations.** The disassembler tracks up to
  `HLMOD_MAX_RELOCATIONS` (4) RIP-relative references inside the prologue
  it's copying; a fifth one aborts the scan the same way an unrecognized
  instruction would, rather than silently dropping a fixup.
- **Relocation out of range.** If recomputing a RIP-relative displacement
  for the trampoline's new address would overflow a 32-bit signed
  displacement (astronomically unlikely given the two are allocated near
  each other, but checked anyway), hooking raises `RuntimeError: Cannot
  safely hook this native: a relocated RIP-relative reference's target is
  out of 32-bit displacement range`.
- **Unwindable `call` in the prologue, Windows only.** If the copied
  prologue contains a `call rel32` (typically a `__chkstk` stack probe for a
  native with large stack locals), the resume trampoline becomes a non-leaf
  frame that Windows SEH needs unwind metadata for - metadata hlmod can
  hand-build for its own fixed-shape landing stub, but not for an arbitrary
  copied prologue. Rather than risk `STATUS_BAD_FUNCTION_TABLE` tearing down
  the process the first time an exception needs to unwind through it, this
  case is refused outright with `RuntimeError: Cannot safely hook this
  native on Windows: its prologue contains a call (e.g. a stack probe)...`.
- **Can't make the page writable.** If `VirtualProtect`/`mprotect` fails on
  the native's own code page, hooking raises `RuntimeError: Failed to make
  the native function's memory page writable for hooking`.
- **Out of memory.** Allocating the trampoline, the landing stub, or the
  bookkeeping struct can each independently raise `MemoryError`.

See [Known issues](./known-issues.md#native-hooking-is-x86-64-only-and-it-fails-loudly-on-purpose)
for the practical fallout of this - mostly "the native you wanted isn't
hookable right now, use a bytecode-level call site instead if one exists."
None of these are bugs waiting to be filed; they're the disassembler
correctly declining to do something it can't prove is safe. The alternative
- patching blind and hoping the boundary lands right - produces corrupted
machine code that crashes some unrelated number of instructions later, which
is a genuinely miserable thing to debug compared to a `RuntimeError` at the
call to `hook()`.

## See also

- [Known issues](./known-issues.md) for the x86-64-only limitation stated as
  a standing constraint rather than mechanism.
- [Design philosophy](./design-philosophy.md) for why this whole engine
  errs so hard toward refusing over guessing.
- [Mods, hooks and events](./mods-hooks-events.md) for the shared
  `call_next`/`call_original`/priority composition model both hook paths use.
