---
sidebar_position: 13
---

# Editor support

Generated proxies ship with `.pyi` interfaces, so a type checker infers
`BridgeBase(1)` as `BridgeBase`, checks constructor and method arguments, field
types, overrides, hook signatures and event payloads. This isn't a
best-effort annotation pass bolted onto a dynamic API - the interfaces are
derived directly from the same HL bytecode metadata the runtime proxies are
built from, so what Pyright (or Pylance, which is Pyright with a VS Code
costume on) tells you matches what the VM will actually accept. No game
process, no import-time introspection, no stub-generation script you have to
remember to re-run by hand.

## Generating the SDK

`hl --generate-stubs game.hl` writes the whole Python SDK - `hlobj.py`,
`hlvalues.py`, `modcore/`, and the per-class `stubs/` tree - without loading
or running the game. It's the same code path the normal `hl game.hl` startup
uses to (re)generate `mods/stubs/` before the game boots, just invoked
standalone so an editor or a packaging script can call it without spinning up
a window. See [Building](./building.md) for how this fits into the rest of
the runtime layout, and note the same warning applies here: proxies under
`mods/stubs/` are generated for one specific bytecode file and are not
portable between applications, even two builds of the same game.

Generation is cached. Each run computes a signature over the bytecode's
content hash, the loaded Haxe doc comments, and the contents of
`typing_overlays.json`, and compares it against `mods/stubs/.hlmod_generated.json`
from the last run. If nothing relevant changed and every previously-generated
file is still present, you get `[hlmod] Python proxy signature matches;
skipping generation.` and nothing is rewritten. Change the overlay file,
change the bytecode, or delete a generated file out from under it, and the
signature stops matching, so it regenerates - and only ever deletes files
*it* generated last time, never anything else living in `mods/`.

## Pointing your editor at it

Pyright (and therefore Pylance) needs to know where `stubs`, `modcore`,
`hlobj`, and `hlmod` actually live, via `extraPaths` in `pyrightconfig.json`.
If you scaffolded your mod with `hlmod-sdk new` (see [hlmod-sdk](./hlmod-sdk.md)),
this is already done - the scaffolded config points `extraPaths` at the
target install's `mods/` directory absolutely, so editor intellisense works
from your own project folder without copying anything into the game's `mods/`:

```json
{
  "include": ["my_mod.py"],
  "extraPaths": ["/path/to/game/mods"],
  "pythonVersion": "3.12",
  "typeCheckingMode": "standard"
}
```

Writing a mod directly inside the install's `mods/` folder works the same
way with a relative path instead - `"extraPaths": ["mods"]` from a config
sitting next to it, which is exactly what hlmod's own editor acceptance test
uses against an isolated fixture. Either way, once `extraPaths` resolves,
`from stubs import BridgeBase`, `from modcore import hook, register_hook,
Event, HookContext`, and `import hlmod` all resolve with full type
information, not `Any`.

## What actually lands in a `.pyi`

Every generated class gets two files: a real `.py` module that forwards
calls into the native VM at runtime, and a `.pyi` companion that a type
checker reads instead of executing. The `.pyi` is not a hand-maintained
parallel API - it's produced by parsing the generated `.py` module's own AST
and stripping everything that isn't declaration shape: assignments are
dropped, function bodies become a docstring (if one exists) followed by
`...`, and only real classes and functions survive. A few things worth
knowing when you're staring at a generated interface wondering why it looks
the way it does:

- **Parameters are positional-only.** HL calls are positional; a Haxe
  argument name is not part of its contract, and generated parameter names
  are often synthesized (`arg0`, `arg1`, ...) when the bytecode didn't carry
  real ones. So every parameter in a `.pyi` signature is forced
  positional-only, which mostly matters for hook callbacks - you can name
  your handler's parameters whatever you want without a type checker
  insisting they match the proxy's.
- **Dynamically-reassignable fields become `Callable`-typed attributes**, not
  methods. If a field on the native type holds a function value (the kind
  HL calls a "field method" or closure slot, like `changeable` in the
  example below), the interface exposes it as a plain annotated attribute of
  type `Callable[[...], ...]` rather than a bound method, since it's
  something you can genuinely read and reassign, unlike a real method.
- **Types with no native constructor get a synthetic one that rejects every
  call.** If a class has no `new` binding and no separately-tracked
  constructor `findex`, the runtime `.py` raises `TypeError` from
  `__init__`. The `.pyi` goes further and replaces its variadic catch-all
  parameters with a single required parameter typed `Never`, so calling it
  is a type error you catch at edit time instead of a `TypeError` you catch
  at runtime.
- **Static companions show up as `STATIC: ClassVar[...]`.** Haxe static
  fields and static methods live on a paired native type; the generator
  models that pairing by exposing a `STATIC` class variable typed as the
  companion class, plus copies of purely-static members with
  `@staticmethod`, so both `BridgeBase.twice(2)` and `BridgeBase.STATIC.twice(2)`
  type-check.
- **Nothing is guaranteed non-null unless the bytecode says so.** HL doesn't
  encode non-null guarantees for pointer-ish values in its type metadata, so
  bytes, arrays, refs, objects, virtuals, enums, dynamic objects, structs,
  and even `Callable`-typed fields and returns get a trailing `| None` by
  default unless the generator already knows the value can't exist (a
  rejected call, for instance, types as `Never` instead). This is the
  single biggest source of "why does this field type have `| None` on it"
  surprise, and it's not a generator bug - it's an honest reflection of what
  the bytecode can and can't promise. Haxe's own `Null<T>` wrapper type is
  unwrapped the same way, producing `T | None` rather than a distinct
  wrapper class.
- **Haxe doc comments come along for the ride, when available.** If a
  `haxe_docs.json` file is present (checked in the working directory, in
  `mods/`, and under `std_doc/`), field and method doc comments are threaded
  through as real docstrings, with a trailing `file:line` pointer back to
  the native source appended underneath - so hovering a generated method in
  your editor can show you the original Haxe documentation, not just its
  signature.
- **Runtime wiring is stripped.** The real `.py` module decorates every
  class with `@hltype(index)` and every method with `@hlfunction(findex)` to
  tie generated code back to native metadata; none of that is typing
  information, so the `.pyi` drops it (aside from `@staticmethod`, which the
  type checker actually needs).

## `typing_overlays.json`

Bytecode metadata is not always precise enough to infer a useful type on its
own. The clearest example is native arrays: HL's own array kind doesn't
carry its Haxe-side element type in a form the generator can recover, so
without help every native array defaults to `HlArray[Any]`. That's a type
checker giving up, not a type checker being honest - the element type *is*
`int`, or `pr.Player | None`, or whatever the Haxe source actually declared,
it's just not sitting in the metadata anymore by the time the generator sees
it. `typing_overlays.json` exists to hand that detail back, as a small,
strictly-validated JSON patch file that only ever touches the `.pyi` -
never the runtime `.py`, so it can't change what the VM actually does, only
what your editor believes about it:

```json
{
  "version": 1,
  "imports": {"NativeArray": "hlobj.HlArray"},
  "types": {
    "pr.Game": {"fields": {"players": "NativeArray[int] | None"}}
  }
}
```

The schema has exactly three top-level keys, and the generator rejects
anything else outright:

- **`version`** - must be present-and-1 if the file is non-empty, or absent
  entirely for an empty overlay. There's only ever been one overlay format;
  this exists so a future breaking change to the schema has somewhere to
  land without silently misinterpreting an old file.
- **`imports`** - a map of alias to a dotted source name, expanded into
  `from <module> import <name> as <alias>` at the top of the affected
  `.pyi` files. The source has to resolve to something the generator
  already knows how to export: a generated class (`pr.Game`, addressed the
  same way it appears under `types`), one of `hlobj`'s public wrapper types
  (`HlArray`, `HlBytes`, `HlObject`, `HlVirtual`, `HlEnum`, `HlDynObject`,
  `HlRef`, `HlCallable`), `hlmod.HlPtr`, or anything from `typing.__all__`.
  Anything else - a typo, a real third-party module, a relative import - is
  an "Unknown overlay import" error. The alias itself also has to be a
  legal, non-dunder, non-keyword identifier that doesn't collide with a
  generated class name or a builtin.
- **`types`** - a map keyed by the *native* type name exactly as it appears
  in bytecode metadata (`"pr.Game"`, not `"Game"` and not the escaped Python
  identifier), pointing at a patch object with only `fields` and/or
  `methods` keys.
  - `fields` maps a real field name to a replacement annotation string. The
    field has to already exist on that native type and not already be a
    method - patching a name that doesn't correspond to a real field, or a
    typo'd one, raises `Unknown overlay field: pr.Game.playres` (or
    similar) and generation fails outright rather than silently ignoring
    the entry.
  - `methods` maps a method name - or the literal name `"new"` for the
    constructor - to `{"args": [...], "returns": "..."}`. The number of
    entries in `args` has to match the native signature's arity exactly
    (after accounting for the implicit `self`/bound-method parameter), and
    a `"new"` overlay's `returns` has to be `"None"`, matching what a real
    `__init__` is allowed to return. Getting the arity wrong, or overlaying
    a method that doesn't exist on that type, is a hard error for the same
    reason a bad field name is.

Every annotation string is parsed as a Python expression and walked before
it's trusted, on purpose: only `Name`, `Subscript`, `Tuple`, `List`,
`BinOp`/`BitOr` (for `X | Y` unions), and `Constant` nodes are allowed, and
the only constants permitted are `None` and `...` - no string literals, no
numbers, nothing that could smuggle a forward-reference string past the type
checker and into something `eval`-able. Every bare name has to come from a
fixed allowlist - `Any`, `Callable`, `Never`, the obvious builtins
(`int`, `str`, `float`, `bool`, `bytes`, `list`, `dict`, `tuple`, `set`,
`frozenset`, `object`, `type`), the `hlobj`/`hlmod` wrapper types, or
whatever you declared under `imports` - or it's rejected as an "Unknown
overlay annotation name." The overlay file is data, not code: at no point
does the generator import or execute anything a mod author writes into it,
which is deliberate given it's loaded automatically on every game launch.

A bad overlay - unknown version, malformed JSON shape, a field or method
name that doesn't exist, an arity mismatch, a forbidden annotation - makes
`hl --generate-stubs`/`hl game.hl` fail loudly with a `ValueError` instead of
generating a wrong-but-plausible interface. That's the same "fail closed"
instinct documented in [Design philosophy](./design-philosophy.md): a
stub generator that silently drops an invalid patch would hand you a `.pyi`
that quietly disagrees with what you asked for, which is a much worse place
to end up than a generation failure with a message pointing at the exact
key that's wrong.

`HLMOD_TYPING_OVERLAY` overrides the overlay path (default
`mods/typing_overlays.json`, next to `mods/stubs/`) if you need to point at
a different file - mainly useful for isolated test fixtures, not something a
mod author normally needs to set.

## Verifying it actually works

`tests/editor/run.py` is the acceptance test that keeps every claim on this
page honest: it compiles a small fixture, runs `hl --generate-stubs` against
it with a real overlay, and drives Pyright with `--outputjson` over a
`pyrightconfig.json` shaped exactly like the one above. It asserts a battery
of `assert_type(...)` checks pass on valid code (constructor and method
argument/return types, field types, hook `ctx.call_next`/`call_original`
signatures, `Event[[...]].emit`/`subscribe` payload types, `HlArray`/`HlRef`
generics), and that a parallel set of intentionally-wrong programs each
produce the specific diagnostic rule they should -
`reportArgumentType`, `reportCallIssue`, `reportAttributeAccessIssue`,
`reportIncompatibleMethodOverride` - not just "some error, somewhere." It
also exercises the generation cache directly: an unchanged bytecode/overlay
pair should log "skipping generation," and an overlay edit (changing an
array element type from `int` to `str`) should invalidate the cache and
change what `assert_type` infers on the next run. If you're extending the
renderer or the overlay schema, this is the file to run, not something to
take on faith from this page.

## See also

- [Building](./building.md) for how `mods/stubs/` fits into the rest of a
  packaged mod, and the `HLMOD_MODS_DIR` override.
- [hlmod-sdk](./hlmod-sdk.md) for the CLI that scaffolds a working
  `pyrightconfig.json` for you.
- [Mods, hooks, and events](./mods-hooks-events.md) and
  [Hooking native functions](./native-hooks.md) for what the hook and event
  signatures checked here actually do at runtime.
