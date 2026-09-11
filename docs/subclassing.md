---
sidebar_position: 14
---

# Python subclasses and native values

Generated object stubs aren't typed accessors bolted onto opaque pointers - they're real Python classes, and hlmod means that literally. Subclass one, and `HlObjectMeta` mints an actual native HL type behind it, wires your overrides into the real dispatch machinery, and then gets out of the way. You write ordinary Python; the metaclass is what convinces the native runtime to believe it.

```python
from stubs import BridgeBase

class Offset(BridgeBase):
    def __init__(self, value: int):
        super().__init__(value)  # Runs the native constructor on this instance.
        self.offset = 100       # Python-only state.

    def compute(self, delta: int) -> int:
        return super().compute(delta) + self.offset

obj = Offset(10)
obj.value = 20                  # Writes the inherited native field.
```

Passing `obj` to a compatible HL parameter passes a real native subtype. HL method
calls reach its Python overrides; returning it through a base-class or `Dynamic`
value recovers the original Python instance, including Python-only state. Native
instances of the base class are unaffected. Wrapping an existing native object
does not run Python `__init__`. Ordinary Python mixins are supported, but multiple
native bases are rejected.

Native fields keep their HL layout and types. New Python attributes are not new
HL fields; class defaults/properties that shadow native data fields are rejected.
Native dynamic-method fields are live: assigning a compatible Python callable
changes subsequent calls from both languages. Explicit base calls and `super()`
still execute the selected base implementation. Calls already inlined by Haxe
cannot be intercepted after compilation.

## How `HlObjectMeta` actually pulls this off

Generated stub classes carry `_hl_generated = True` and are excused from all of
this at import time - they already went through it once, at codegen time, by
construction. A mod-authored subclass hasn't, so `HlObjectMeta.__new__` runs the
real logic: it scans `bases` for anything that's itself governed by
`HlObjectMeta` and already has a `_hl_type_index` - that's what "has a native
ancestor" means concretely. Exactly one base is allowed to qualify; HL's object
model has one native parent per type, and two would leave nothing coherent for
the native type descriptor to extend, hence the `TypeError` if you try.

With that single native base in hand, `HlObjectMeta.__new__` does two passes over
the MRO between your class and it. First, it forbids any Python class attribute -
a default value, a property, whatever - from colliding with a name the native
type already uses for a real data field; second, it looks for methods your
subclass actually overrode, meaning the bound implementation found by walking
your MRO differs from the one found by walking the base's MRO. Redeclaring a
method that just forwards to `super()` doesn't count as an override, and doesn't
get charged an extra JIT trampoline for nothing.

That override dict, your class object, and the native base's type index all get
handed to `hlmod.create_subclass`, which is where "real native type" stops being
a metaphor. On the C side it allocates a genuine `hl_obj` type descriptor chained
via `.super` to the base, and for every overridden method it JIT-compiles a small
trampoline into Python and threads it into the actual dispatch machinery: the
proto vtable slot at every level of the ancestor chain that could reach that
method by name, any non-closure static binding pointing at it, and the special
`__string`/`__compare`/`__cast`/`__get_field` hooks if you happened to override
one of those. It's the same philosophy as the JIT hooking engine described in
[Design philosophy](./design-philosophy.md) - a small, provably-correct patch
site at every call path that could reach the old code, rather than trying to
reason your way through every possible caller from Python.

Instantiation goes through `HlObjectMeta.__call__`, which intercepts
`MySubclass(...)` before your `__init__` ever runs. It allocates a raw native
object of the freshly-minted subtype with `hlmod.alloc_obj`, stores the pointer
as `_hlmod_ptr`, and - because the value `create_subclass` handed back is itself
a typed native pointer - registers the instance in hlmod's native-to-Python peer
table via `hlmod.bind_instance`. That peer table, plus a hidden field every
native subtype gets purely to carry a GC finalizer, is the actual mechanism
behind "returning it through a base-class or `Dynamic` value recovers the
original Python instance": when HL hands a value back to Python, the runtime
checks that table for an existing peer before falling back to constructing a
fresh generic wrapper. Only after all of that does `__call__` run your real
`__init__`. And a generated stub's `__init__` - the one `super().__init__(value)`
reaches in the example above - isn't magic either: it's rendered code that calls
`hlmod.init_obj` on that same, already-allocated pointer with the native
constructor's function index, so the constructor body runs against an object
that is already correctly typed as your subtype, not the base.

Everyday attribute access is unrelated to any of the above and doesn't care
whether a class is native-backed by subclassing or just wraps one: `HlObject`
overrides `__getattr__`/`__setattr__` to check the class's `_hl_fields` table
(a plain name-to-index dict, generated at stub-render time, never hand-written)
and proxy hits through `hlmod.get_obj_field`/`set_obj_field`. Everything else
falls through to ordinary Python attribute lookup, which is exactly how a
non-overridden method call ends up running the generated stub's own
`hlmod.call(findex, ...)` body.

## Overriding a live `dynamic` field without subclassing at all

Haxe's `dynamic function` methods are a different animal from ordinary virtual
methods: the compiler backs them with a real object field holding a closure,
instead of a fixed vtable slot, specifically so the closure can be swapped out
at runtime. hlmod exposes that field exactly like any other field - which means
changing one doesn't need `HlObjectMeta`, an override dict, or a subclass at
all. Given a Haxe class with a field declared this way:

```haxe
public dynamic function changeable(delta:Int):Int {
    return value + delta + 500;
}
```

any Python code holding a compatible instance can just assign a plain callable
to the attribute:

```python
from stubs import BridgeBase

mutable = BridgeBase(9)
assert mutable.changeable(1) == 510           # the native implementation

mutable.changeable = lambda delta: delta * 7  # swap the closure in place
assert mutable.changeable(2) == 14
```

Because `changeable` is a real HL field of function type, that assignment goes
through the ordinary native-field path in `__setattr__`, which converts the
Python callable into a genuine HL closure through the same JIT-compiled adapter
`hlmod.make_callback` uses for typed `Dynamic` callbacks. The result is an actual
closure pointer sitting in that field's memory slot, so it doesn't matter who
calls it next - Haxe code elsewhere in the game that invokes
`mutable.changeable(3)` on this exact object gets your lambda's answer too, with
no coordination required on either side. Reads go through the matching half of
the mechanism: `HlObject.__getattribute__` checks the class's `_hl_bound_fields`
table before falling back to ordinary lookup, specifically so that reading the
attribute always returns whatever closure is installed *right now*, not whatever
the class body originally declared.

This is deliberately narrower than subclassing: it changes one field, on however
many instances you choose to assign it to, and only for members Haxe actually
declared `dynamic`. An ordinary virtual method has no field to swap - overriding
one of those needs a real subclass and the vtable-patching machinery above.

## Conversion and ownership rules

Every one of the facts below exists because there are two garbage collectors
that don't know about each other, two number models, two competing ideas of
what a null value is, and two different representations of an array, and none
of that gets to stay ambiguous at the point where a value actually crosses from
one runtime into the other. Every conversion either follows an exact, specified
rule or raises instead of guessing - this list is that specification:

- Native object, virtual, closure, and array wrappers carry their actual HL type
  and keep their native allocations alive. HL-held Python objects and callbacks
  retain their Python state; unreachable cross-runtime cycles are collected.
- `None` represents null pointer/nullable values, not scalar zero. Pointer-value
  annotations include `None`, since bytecode does not retain non-null guarantees.
- Integers are range-checked, including signed 64-bit values. `Bool` requires a
  Python `bool`. Strings preserve UTF-16 contents, embedded NULs, and leading BOM
  characters. Incompatible object and closure types raise `TypeError`.
- `HlArray` is a live native-array proxy, not a copied Python list. Its indexing
  reads/writes native storage; `HlArray.create(type_index, values)` creates
  an array with an explicit element type. Plain lists are not implicitly cast to
  HL native arrays: an `HARRAY` signature does not encode its element type.
- Python callables become typed HL closures when the receiving signature is
  known. Ambiguous `Dynamic` callbacks need an explicit signature through
  `hlmod.make_callback`. Python callback exceptions become catchable HL exceptions;
  HL exceptions in calls from Python become `RuntimeError`.
- Raw `HlPtr(address, kind)` values are opaque and untrusted. Integer addresses
  and untrusted pointers cannot be used as typed objects, arrays, or closures.
- `HlEnum`, `HlDynObject`, `HlRef[T]` and `HlBytes` wrap native enums, dynamic
  records, references and byte buffers; `inspect_native` reports real runtime
  fields, methods and enum constructors. Abstracts stay opaque `HlPtr` values by
  design. Packed/GUID values and unsupported struct/callback layouts raise
  explicit errors rather than guessing memory layout.
- Enum values compare structurally, like `Type.enumEq`: HL shares pointers only
  for compiler-created constants. Constructor *parameter names* are absent from
  bytecode, so parameters are positional.
- `HlBytes` bounds every read and write by the buffer's real allocation. HL
  bytes carry no length, so a wrapper knows its length only when Python
  allocated it, otherwise it reports the allocation size; buffers HL never
  allocated have no discoverable size and stay unreadable. Passing `bytes`
  where HL expects `hl.Bytes` copies into a GC-owned buffer, so pass `HlBytes`
  when both sides must share storage.
- Calls through HL's dynamic dispatcher accept at most nine arguments, counting
  a bound receiver. Native fields/static globals still follow HL initialization:
  import-time static reads may expose default values before Haxe initialization.

## See also

- [Design philosophy](./design-philosophy.md) - why hlmod prefers small, provable
  patch sites over guessing at call graphs, on both the JIT-hook and subclassing
  paths.
- [Hooking native functions](./native-hooks.md) - the sibling mechanism for
  intercepting code that has no Python subclass to override in the first place.
- [Editor support](./editor-support.md) - how the generated `.pyi` stubs make
  subclass constructors, overrides, and field types type-check correctly.
