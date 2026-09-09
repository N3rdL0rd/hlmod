"""Live native values with runtime type provenance, not raw-address casts."""

from collections.abc import Iterator, MutableMapping
from typing import Any, Generic, TypeVar

import hlmod
from hlmod import HlPtr

T = TypeVar("T")


def _pointer(value: HlPtr, kind: int) -> HlPtr:
    if not isinstance(value, HlPtr) or not value.trusted or value.kind != kind:
        raise TypeError("Expected a native-created pointer of the matching value type")
    if not value.ptr:
        raise ValueError("Cannot wrap a null native pointer")
    return value


def inspect_native(value: object | int) -> dict[str, Any]:
    """Inspect a trusted native value or bytecode type index, without reading fields.

    Type descriptors contain ``name``, ``kind`` and ``type_index`` (None for
    runtime-only types). Results also contain ``fields`` and ``methods``;
    inherited members retain their declaring type and native field/function
    indices. Enums include constructor parameter types; refs/arrays include
    element types when available. Bytes stay opaque: allocation size is not a
    logical byte length. Caller-created raw addresses are never dereferenced.
    """
    return hlmod.inspect_native(value)


class HlEnum:
    """A native enum value. Creation uses the bytecode's exact constructor layout."""

    def __init__(self, pointer: HlPtr) -> None:
        self._hlmod_ptr = _pointer(pointer, 18)

    @classmethod
    def create(cls, type_index: int, constructor: str | int, *parameters: Any) -> "HlEnum":
        if isinstance(constructor, str):
            metadata = inspect_native(type_index)
            if metadata["kind"] != "enum":
                raise TypeError("Expected an enum type index")
            matches = [entry["index"] for entry in metadata["constructors"] if entry["name"] == constructor]
            if not matches:
                raise ValueError(f"Unknown enum constructor {constructor!r}")
            constructor = matches[0]
        return cls(hlmod.enum_new(type_index, constructor, parameters))

    @property
    def type_index(self) -> int | None:
        return self._hlmod_ptr.type_index

    @property
    def constructor_index(self) -> int:
        return hlmod.enum_info(self._hlmod_ptr)["constructor_index"]

    @property
    def constructor_name(self) -> str:
        return hlmod.enum_info(self._hlmod_ptr)["constructor_name"]

    @property
    def parameters(self) -> tuple[Any, ...]:
        return hlmod.enum_info(self._hlmod_ptr)["parameters"]

    def __eq__(self, other: object) -> bool:
        # Structural, like Haxe's Type.enumEq: HL only shares pointers for
        # compiler-created constants, so identity would report false negatives.
        if not isinstance(other, HlEnum):
            return NotImplemented
        if self._hlmod_ptr.ptr == other._hlmod_ptr.ptr:
            return True
        return (self.type_index == other.type_index
                and self.constructor_index == other.constructor_index
                and self.parameters == other.parameters)

    def __hash__(self) -> int:
        try:
            return hash((self.type_index, self.constructor_index, self.parameters))
        except TypeError:
            return hash((self.type_index, self.constructor_index))

    def __repr__(self) -> str:
        info = hlmod.enum_info(self._hlmod_ptr)
        return f"<HlEnum {info['constructor_name']}{info['parameters']!r}>"


class HlDynObject(MutableMapping[str, Any]):
    """A live dynamic record. Iteration snapshots keys; reads/writes stay live.

    Untyped Python callbacks cannot be assigned because Dynamic erases their
    signature. Assign a typed native HlCallable instead. Nested native values
    retain their normal wrappers and native identity.
    """

    def __init__(self, pointer: HlPtr | None = None) -> None:
        self._hlmod_ptr = _pointer(hlmod.dynobj_new() if pointer is None else pointer, 16)

    def __getitem__(self, key: str) -> Any:
        return hlmod.dynobj_get(self._hlmod_ptr, key)

    def __setitem__(self, key: str, value: Any) -> None:
        hlmod.dynobj_set(self._hlmod_ptr, key, value)

    def __delitem__(self, key: str) -> None:
        hlmod.dynobj_delete(self._hlmod_ptr, key)

    def __iter__(self) -> Iterator[str]:
        return iter(hlmod.dynobj_keys(self._hlmod_ptr))

    def __len__(self) -> int:
        return len(hlmod.dynobj_keys(self._hlmod_ptr))

    def __dir__(self) -> list[str]:
        return sorted(set(super().__dir__()) | set(self))

    def __repr__(self) -> str:
        return f"<HlDynObject keys={tuple(self)!r}>"


class HlRef(Generic[T]):
    """A live, heap-backed HL reference with its actual element type.

    Creation requires a reference (HREF) type index, not an inferred Python
    type. Stack-backed native borrows are rejected: retaining them past the
    native call would otherwise allow access to expired stack storage.
    """

    def __init__(self, pointer: HlPtr) -> None:
        self._hlmod_ptr = _pointer(pointer, 14)

    @classmethod
    def create(cls, type_index: int, value: T) -> "HlRef[T]":
        return cls(hlmod.ref_new(type_index, value))

    @property
    def element_type_index(self) -> int | None:
        return inspect_native(self)["element_type"]["type_index"]

    @property
    def value(self) -> T:
        return hlmod.ref_get(self._hlmod_ptr)

    @value.setter
    def value(self, value: T) -> None:
        hlmod.ref_set(self._hlmod_ptr, value)

    def __repr__(self) -> str:
        return f"<HlRef element_type_index={self.element_type_index}>"


class HlBytes:
    """A live native byte buffer bounded by its real allocation.

    HL bytes carry no logical length. This wrapper remembers the length it was
    created with, otherwise reports the allocation size, and refuses to read or
    write outside that allocation. Buffers HL did not allocate (for example a
    pointer handed over by a native library) have no discoverable size and stay
    unreadable rather than guessed.
    """

    def __init__(self, pointer: HlPtr, length: int | None = None) -> None:
        self._hlmod_ptr = _pointer(pointer, 8)
        # HL allocations round up, so remember the requested length when this
        # buffer was created here. Values arriving from HL have none.
        self._length = length

    @classmethod
    def create(cls, size: int) -> "HlBytes":
        return cls(hlmod.bytes_new(size), size)

    @classmethod
    def from_bytes(cls, data: bytes | bytearray | memoryview) -> "HlBytes":
        view = memoryview(data)
        return cls(hlmod.bytes_from(view), view.nbytes)

    @property
    def capacity(self) -> int | None:
        """Real allocation size, which may exceed the requested length."""
        return hlmod.bytes_capacity(self._hlmod_ptr)

    def __len__(self) -> int:
        if self._length is not None:
            return self._length
        capacity = self.capacity
        if capacity is None:
            raise TypeError("This bytes pointer has no known length or allocation size")
        return capacity

    def read(self, offset: int = 0, length: int | None = None) -> bytes:
        if length is None:
            length = len(self) - offset
        return hlmod.bytes_read(self._hlmod_ptr, offset, length)

    def write(self, data: bytes | bytearray | memoryview, offset: int = 0) -> None:
        hlmod.bytes_write(self._hlmod_ptr, offset, data)

    def decode(self, encoding: str = "utf-16-le", *, offset: int = 0, length: int | None = None) -> str:
        """Decode a byte range. HL strings are UTF-16 without a stored length."""
        return self.read(offset, length).decode(encoding)

    def __getitem__(self, index: int | slice) -> int | bytes:
        if isinstance(index, slice):
            start, stop, step = index.indices(len(self))
            if step != 1:
                raise ValueError("Native byte slices must be contiguous")
            return self.read(start, max(0, stop - start))
        offset = index + len(self) if index < 0 else index
        return self.read(offset, 1)[0]

    def __setitem__(self, index: int | slice, value: int | bytes | bytearray | memoryview) -> None:
        if isinstance(index, slice):
            start, stop, step = index.indices(len(self))
            if step != 1:
                raise ValueError("Native byte slices must be contiguous")
            data = bytes(value)  # type: ignore[arg-type]
            if len(data) != max(0, stop - start):
                raise ValueError("Native byte slice assignment cannot resize the allocation")
            self.write(data, start)
            return
        offset = index + len(self) if index < 0 else index
        self.write(bytes((value,)) if isinstance(value, int) else bytes(value), offset)

    def __repr__(self) -> str:
        capacity = self.capacity
        size = "unknown" if capacity is None else capacity
        return f"<HlBytes capacity={size} ptr=0x{self._hlmod_ptr.ptr:X}>"
