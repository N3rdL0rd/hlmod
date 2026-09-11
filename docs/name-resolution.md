---
sidebar_position: 11
---

# Resolving names to indices

`hlmod.findex_for_name("$Class.method")` resolves a bytecode function; the
companion `hlmod.type_index_for_name("Class")` resolves an obj/struct/enum
type the same way, for `alloc_obj`, `create_subclass`, `enum_new`, and
anywhere else a type index is otherwise a hardcoded magic number. A third
function, `hlmod.native_findex(lib, name)`, does the same job for `@:hlNative`
declarations, which live in their own table and aren't addressable by the
other two. All three exist for the same reason: a bytecode function index or
type index is a position in an array the Haxe compiler built *this time it
ran*. Add a method to an unrelated class, reorder an import, bump the compiler
version - and every findex after that point can silently shift. A mod that
hardcodes `hlmod.call(4821, args)` today is one recompile away from calling
something else entirely, with no error, just a game update that mysteriously
started acting up. Resolving by name at mod-load time trades a number that's
only valid for one exact build for a string that's valid for as long as the
class and method keep their names, which - for a modder targeting a game that
gets patched - is the only kind of stability worth having.

## How it works

All three functions are linear scans over tables that are already sitting in
memory, done once at the point you call them - there's no name index built
up front, because mods typically resolve a handful of names at load time and
then never again.

`findex_for_name` walks `g_code->functions` and, for every function that has
both an owning type and a field name, builds `"<obj name>.<field name>"` and
compares it against what you passed in. If nothing matches by the end of the
table, it raises `NameError: No such function!`. Functions with no owning
type or no field name (anonymous closures, mostly) are skipped entirely and
can never be resolved this way - if you need a findex for one of those,
you'll have gotten it from somewhere other than a name lookup in the first
place (`inspect_native`, a hook's own findex, and so on).

The `$` prefix isn't an hlmod convention, it's Haxe's: HL bytecode doesn't
have a separate concept of "static methods" the way you might expect. The
compiler puts them on a synthetic companion type named `$ClassName` instead,
and that's the type your static method's `obj` field actually points to.
So `"$BridgeBase.staticCompute"` resolves the *static* `staticCompute`, while
plain `"BridgeBase.compute"` (no `$`) would resolve an *instance* method
defined directly on `BridgeBase` - if you ever have a reason to grab its raw
findex instead of just calling it virtually.

`type_index_for_name` walks `g_code->types` looking for an `HOBJ`, `HSTRUCT`,
or `HENUM` whose name (from `obj->name` or `tenum->name` respectively)
matches exactly, returning the index into that table on a hit. Nothing else
carries a type index, so this is a flat table, not a `Class.field`-style
qualified name. It's the same name `inspect_native(...)["name"]` reports for
that type, so if you're not sure what a class is actually called in
bytecode (nested types, nested-module renames, and Haxe's own naming quirks
can all produce something other than what you'd guess), inspecting a live
instance is the fastest way to find out. A miss raises `KeyError`, not
`NameError` - type lookups and function lookups are different C functions
with different failure conventions, so don't assume they line up.

`native_findex(lib, name)` is a similar scan, but over `code->natives`
instead, matching both the library string and the native's own name (the two
arguments to Haxe's `@:hlNative(lib, name)` annotation). A miss there also
raises `KeyError`. All three require hlmod to actually be initialized
(`g_code`/`g_module` populated from the loaded bytecode) before they'll do
anything; calling one too early raises `RuntimeError: hlmod is not
initialized.` - not something you'll normally hit from inside a mod, since
mods only run once initialization has already happened.

## Using it

Most of the time you don't call `findex_for_name` yourself.
`modcore.hook()`/`register_hook()` accept a name string directly and resolve
it internally the same way:

```python
from modcore import hook

@hook("$BridgeFixture.compute")
def on_compute(context, delta):
    return context.call_next(delta) + 1
```

and the generated stub classes in `stubs/` do the same lazily for static
methods - the first call resolves the findex and caches it, so you're not
paying for the scan on every call. Where you *do* reach for the raw
functions is anywhere that wants a findex or type index directly - `call`,
`register_hook`'s lower-level form, or the allocation/enum APIs:

```python
import hlmod

# Resolving a static method and calling it directly.
compute = hlmod.findex_for_name("$BridgeBase.staticCompute")
result = hlmod.call(compute, (5,))

# Resolving an enum type to build one of its cases by hand.
choice_type = hlmod.type_index_for_name("ValueChoice")
# ValueChoice's constructors, in declaration order: Empty, Payload, Nested.
payload = hlmod.enum_new(choice_type, 1, (42, "hello"))

# Resolving a native and hooking it - see ./native-hooks.md for the
# detour mechanics this triggers.
frozen = hlmod.native_findex("std", "sys_time")
hlmod.register_hook(frozen, lambda native_context: 0.0)
```

`type_index_for_name` combines with `alloc_obj` and `create_subclass` the
same way - anywhere the SDK expects a type index as a plain `int`, resolving
it by name instead of copying a number out of a debugger session is the
difference between a mod that survives the next patch and one that doesn't.

:::note
Enum constructor indices themselves aren't resolved by name - there's no
`constructor_index_for_name`, because Haxe enum case names aren't guaranteed
unique across an enum's ancestors the way type and method names are.
`enum_new`'s `constructor_index` is positional, matching declaration order
in the source; `inspect_native` on an existing instance of the enum (or on
the type itself) is the reliable way to check that order without guessing.
:::

## See also

- [Hooking native functions](./native-hooks.md) - what happens after
  `native_findex` gives you a findex to hook.
- [Python subclasses and native values](./subclassing.md) - `create_subclass`
  and friends, the usual consumers of `type_index_for_name`.
