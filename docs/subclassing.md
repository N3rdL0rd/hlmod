---
sidebar_position: 14
---

# Python subclasses and native values

Generated object classes can be constructed and subclassed normally:

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

## Conversion and ownership rules

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
