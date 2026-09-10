"""
Internal, low-level module to interface more directly with hlmod. You should use `modcore` for 99% of cases, which provides much higher-level abstractions over this module!
"""

from typing import Any, Callable, Iterable, Optional, Protocol, Tuple
from hlobj import HlCallable

class HlPtr:
    """
    Opaque native pointer carrying its HashLink type and GC provenance.
    Raw Python-created addresses are not accepted by typed conversion APIs.
    Generated proxies expose their trusted pointer as ``_hlmod_ptr``.
    """

    def __init__(self, ptr: int, kind: int = 0) -> None:
        """Create an untrusted raw address, not a typed native object."""
        ...
    
    @property
    def ptr(self) -> int:
        """
        The raw value of the pointer, as an int.
        """
        ...
        
    @property
    def kind(self) -> int:
        """
        The HL type kind of this pointer.
        """
        ...

    @property
    def type_index(self) -> int | None:
        """Bytecode type index, or None for a runtime-only type."""
        ...

    @property
    def trusted(self) -> bool:
        """Whether native code supplied this pointer and its type."""
        ...
    

class Hook:
    """
    A hook context object passed to functions that hook HL code as the first argument, offsetting the rest.
    """
    
    findex: int
    """
    The function index this hook was invoked for. Can also be resolved to a name with `hlmod.findex_for_name` and the like.
    """
    
    def call_original(self, *args: Any) -> Any:
        """
        Calls the original function that was hooked with the passed arguments.
        """
        ...

    def as_closure(self) -> HlCallable:
        """
        Returns the original hooked function as an `hlobj.HlCallable`.
        """
        ...

        
class HookCallback(Protocol):
    """
    Callback signature: (hook: hlmod.Hook, *args: Any)
    """
    def __call__(self, hook: Hook, *args: Any) -> Any:
        ...


def register_hook(
    findex: int, 
    callback: HookCallback
) -> None:
    """
    Hooks a JIT-compiled Hashlink function, redirecting its call to a Python
    callback.

    Args:
        findex: The unique integer index of the Hashlink function to hook.
        callback: A Python function that will be executed when the hook is
                  triggered. Will be passed an hlmod.Hook object and the original args from the function call.
    """
    ...

def unregister_hook(findex: int, callback: HookCallback | None = None) -> bool:
    """Remove a hook only when the optional callback matches the registered owner."""
    ...

def get_obj_field(obj: HlPtr, field: int) -> Any:
    """
    Gets a field from a Obj* by index.
    """
    ...
    
def set_obj_field(obj: HlPtr, field: int, value: Any) -> None:
    """
    Sets a field in an Obj* by index.
    """
    ...

def get_virtual_field(obj: HlPtr, field: int) -> Any:
    """
    Gets a field from a Virtual* by index.
    """
    ...

def set_virtual_field(obj: HlPtr, field: int, value: Any) -> None:
    """
    Sets a field in a Virtual* by index.
    """
    ...

def get_virtual_field_count(obj: HlPtr) -> int:
    """
    Gets the number of fields exposed by a Virtual*.
    """
    ...

def get_virtual_field_name(obj: HlPtr, field: int) -> str:
    """
    Gets the field name for a Virtual* field index.
    """
    ...
    
def get_fixed_prng() -> bool:
    """
    Gets if the HL PRNG is currently set to be fixed or not.
    """
    ...
    
def set_fixed_prng(value: bool) -> None:
    """
    Sets if the HL PRNG should be fixed or not.
    When fixed, the seed is set to 4644546 and the PID is spoofed to 0.
    """
    ...
    
def register_hlobj(tindex: int, typ: type) -> None:
    """
    Registers a given type as the Python stub for a given tindex.
    """
    ...
    
def assert_code_sha(expected: str) -> None:
    """
    Asserts the bytecode SHA256, exiting if it mismatches. Useful for making sure the running bytecode matches what's expected.
    """
    ...
    
def call(findex: int, args: Tuple[Any, ...]) -> Any:
    """
    Calls a bytecode function by findex with the passed args. Returns the result.
    """
    ...

def get_global(tindex: int) -> Optional[Any]:
    """
    Gets the global instance of a type by index. Useful for static types.
    """
    ...

def ensure_global(tindex: int) -> Optional[Any]:
    """
    Returns the existing global instance of a type by index, or None if it has
    not been allocated yet. Does not force allocation.
    """
    ...

def dump_stack() -> None:
    """
    Prints the current HL stack to the console. Requires an active HL thread, don't call during init!
    """
    ...

def findex_for_name(name: str) -> int:
    """
    Gets the corresponding findex for a given function's name. Most likely, you want to just use `modcore.hook()` with a string argument and hlmod will resolve it for you. You're welcome!
    """
    ...

def type_index_for_name(name: str) -> int:
    """
    Gets the bytecode type index of an obj/struct/enum class by its full name (as it
    appears in `inspect_native(...)["name"]`). Pass the result to `alloc_obj`,
    `create_subclass`, `enum_new`, etc. Raises `KeyError` if no such type exists.
    """
    ...

def native_findex(lib: str, name: str) -> int:
    """
    Gets the findex of an `@:hlNative(lib, name)` function declared in the loaded bytecode.
    Pass the result straight to `modcore.hook()`/`register_hook()`; hooking a native lazily
    installs a low-level x86-64 detour the first time it is hooked, so composition,
    `call_next`, and `call_original` behave identically to hooking a bytecode function.
    Raises `KeyError` if no such native exists, and `RuntimeError` if hlmod cannot find a
    safely overwritable prologue at the native's entry point (x86-64 only).
    """
    ...

def call_closure(vclosure: HlPtr, args: Tuple[Any,...]) -> Any:
    """
    Calls a closure by its pointer with the given arguments.
    """
    ...

def profile_start(sample_count: int = 1000) -> None:
    """
    Starts the HL sampling profiler at sample_count samples/sec.
    Call profile_end() to stop and write hlprofile.dump.
    Safe to call from inside a hook callback.
    """
    ...

def profile_end() -> None:
    """
    Stops the profiler and writes hlprofile.dump to the working directory.
    The dump can be converted to a Chrome-readable flamegraph JSON with ProfileGen.hx.
    """
    ...
def gc_major() -> None:
    """
    Forces a full GC collection cycle, blocking the calling thread until it completes.
    """
    ...

def gc_stats() -> dict[str, float]:
    """
    Returns a dict with total_allocated, allocation_count, and current_memory (all in bytes/count,
    accumulated since process start except current_memory).
    """
    ...

def gc_enable(enabled: bool) -> None:
    """
    Enables or disables the GC. Disabling stops collection but allocation keeps working;
    memory only grows until re-enabled and a collection runs.
    """
    ...

def is_gc_ptr(pointer: HlPtr) -> bool:
    """
    Returns whether an HlPtr's address is managed by HL's GC (as opposed to e.g. a static
    global, stack address, or foreign/native allocation).
    """
    ...

def gc_memsize(pointer: HlPtr) -> Optional[int]:
    """
    Returns the GC allocation's size in bytes, or None if the pointer is not GC-managed
    (see is_gc_ptr).
    """
    ...



def create_subclass(base_type: int | HlPtr, cls: type,
                    overrides: dict[str, Callable[..., Any]]) -> HlPtr:
    """Register a native subtype. Override keys are original HL method names."""
    ...

def alloc_obj(native_type: int | HlPtr) -> HlPtr:
    """Allocate an object without running its constructor."""
    ...


def init_obj(ptr: HlPtr, constructor_findex: int, args: tuple[Any, ...]) -> None:
    """Run a native initializer or allocating constructor on this receiver."""
    ...
def bind_instance(ptr: HlPtr, instance: object) -> None:
    """Associate a Python instance with its native object for callback identity."""
    ...

def make_callback(callback: Callable[..., Any], signature: int | HlPtr) -> HlPtr:
    """Create a rooted HL closure with the supplied native function signature."""
    ...

def array_new(element_type_index: int, values: Iterable[Any]) -> HlPtr:
    """Allocate a live HL array with an explicit native element type."""
    ...

def array_length(ptr: HlPtr) -> int: ...
def array_get(ptr: HlPtr, index: int) -> Any: ...
def array_set(ptr: HlPtr, index: int, value: Any) -> None: ...
def array_element_type(ptr: HlPtr) -> int | None: ...

def bytes_new(size: int) -> HlPtr:
    """Allocate zeroed, GC-owned native bytes."""
    ...

def bytes_from(data: bytes | bytearray | memoryview) -> HlPtr:
    """Copy a Python buffer into new GC-owned native bytes."""
    ...

def bytes_capacity(ptr: HlPtr) -> int | None:
    """Allocation size in bytes, or None when HL does not own the buffer."""
    ...

def bytes_read(ptr: HlPtr, offset: int, length: int) -> bytes:
    """Read a range bounded by the real allocation size."""
    ...

def bytes_write(ptr: HlPtr, offset: int, data: bytes | bytearray | memoryview) -> None:
    """Write a range bounded by the real allocation size."""
    ...

def enum_info(pointer: HlPtr) -> dict[str, Any]: ...
def enum_new(type_index: int, constructor_index: int, parameters: Iterable[Any]) -> HlPtr: ...
def dynobj_new() -> HlPtr: ...
def dynobj_keys(pointer: HlPtr) -> tuple[str, ...]: ...
def dynobj_get(pointer: HlPtr, key: str) -> Any: ...
def dynobj_set(pointer: HlPtr, key: str, value: Any) -> None: ...
def dynobj_delete(pointer: HlPtr, key: str) -> None: ...
def ref_new(type_index: int, value: Any) -> HlPtr: ...
def ref_get(pointer: HlPtr) -> Any: ...
def ref_set(pointer: HlPtr, value: Any) -> None: ...
def inspect_native(value: object | int) -> dict[str, Any]: ...

version: str
