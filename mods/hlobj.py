"""
Abstract base classes for accessing HL types in Python.
"""

from enum import IntEnum
import hlmod
from hlmod import register_hlobj, HlPtr
from typing import Any, Callable, Type, TypeVar

T = TypeVar("T", bound=object)

def hltype(idx: int) -> Callable[[Type[T]], Type[T]]:
    """
    Register a HlObject to be created as a proxy for a specific tIndex in the bytecode.
    """

    def decorator(cls: Type[T]) -> Type[T]:
        """The actual decorator that registers the class."""
        register_hlobj(idx, cls)
        return cls
        
    return decorator

class HlObject:
    """
    The base class for all generated Haxe object stubs.
    
    This class uses Python's magic methods to proxy attribute access 
    (getting and setting) directly to the live Haxe object in memory.
    This allows for natural, Pythonic syntax like `player.health = 100`.
    """
    
    _hl_fields: dict[str, int] = {}
    _hlmod_ptr: 'HlPtr'

    def __init__(self, ptr: 'HlPtr') -> None:
        """
        Initializes the Python stub with a pointer to the live Haxe object.
        This is typically called by hlmod itself, not by the user - but if you feel like it, you can call this yourself.
        """
        object.__setattr__(self, "_hlmod_ptr", ptr)

    def __getattr__(self, name: str) -> Any:
        """
        Handles reading an attribute from the object (e.g., `value = obj.field`).
        
        This method is called by Python as a fallback when a regular attribute 
        lookup fails.
        """
        field_index = self._hl_fields.get(name)
        
        if field_index is not None:
            return hlmod.get_obj_field(self._hlmod_ptr, field_index)
        
        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")

    def __setattr__(self, name: str, value: Any) -> None:
        """
        Handles writing an attribute to the object (e.g., `obj.field = value`).
        
        This method is called for *every* attribute assignment.
        """
        field_index = self._hl_fields.get(name)

        if field_index is not None:
            hlmod.set_obj_field(self._hlmod_ptr, field_index, value)
        else:
            object.__setattr__(self, name, value)
            
    def __repr__(self) -> str:
        ptr_val = self._hlmod_ptr.ptr if self._hlmod_ptr else 0
        return f"<{self.__class__.__name__} pointing to 0x{ptr_val:X}>"

    def _hlmod_call_findex(self, findex: int, *args: Any) -> Any:
        return hlmod.call(findex, (self, *args))
        

class HlEnum(IntEnum):
    """Base class for HL enums that have no parameters."""
    pass

class HlEnumObject(HlObject):
    """Base class for HL enum constructors that have parameters."""
    pass

class HlCallable:
    """
    A proxy to a HL closure that can be passed as a reference and called.
    """
    
    def __init__(self, ptr: 'HlPtr') -> None:
        """
        Creates a new HlCallable.
        
        This is typically called by hlmod itself, not by the user - but if you feel like it, you can call this yourself with a compatible HlPtr. Careful for memory safety!
        """
        self._hlmod_ptr = ptr

    @property
    def ptr(self) -> int:
        return self._hlmod_ptr.ptr
    
    def __call__(self, *args: Any) -> Any:
        return hlmod.call_closure(self._hlmod_ptr, args)

    def __repr__(self) -> str:
        return f"<HlCallable ptr=0x{self.ptr:X}>"
