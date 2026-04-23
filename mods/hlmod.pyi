"""
Internal, low-level module to interface more directly with hlmod. You should use `modcore` for 99% of cases, which provides much higher-level abstractions over this module!
"""

from typing import Any, Optional, Protocol, Tuple
from hlobj import HlCallable

class HlPtr:
    """
    Light wrapper on a raw void* to an HL object.
    Only accessible directly from failed or unexpected HL -> Python marshalling, and cannot be created from Python.
    You can also get the underlying HlPtr to any HLObject instance from Python with `object._hlmod_ptr`.
    """
    
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
    

class Hook:
    """
    A hook context object passed to functions that hook HL code as the first argument, offsetting the rest.
    """
    
    findex: int
    """
    The function index this hook was invoked for. Can also be resolved to a name with `hlmod.findex_for_name` and the like.
    """
    
    def call_original(*args: Any) -> Any:
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
    
def call(findex: int, args: Tuple[Any]) -> Any:
    """
    Calls a bytecode function by findex with the passed args. Returns the result.
    """
    ...

def get_global(tindex: int) -> Optional[Any]:
    """
    Gets the global instance of a type by index. Useful for static types.
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

version: str
