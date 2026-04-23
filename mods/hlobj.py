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

class HlObjectMeta(type):
    """
    Metaclass that forwards class-level access to a type's HL static object when one exists.
    """

    def _hlmod_get_static(cls) -> Any:
        try:
            tindex = type.__getattribute__(cls, "_hl_static_tindex")
        except AttributeError as exc:
            raise AttributeError(f"type object '{cls.__name__}' has no attribute 'STATIC'") from exc

        if tindex is None:
            raise AttributeError(f"type object '{cls.__name__}' has no static HL companion")

        cached = type.__getattribute__(cls, "_hl_static_obj")
        if cached is not None:
            return cached

        static_obj = hlmod.get_global(tindex)
        if static_obj is None:
            raise RuntimeError(f"HL static object for '{cls.__name__}' is unavailable")

        type.__setattr__(cls, "_hl_static_obj", static_obj)
        return static_obj

    def __getattr__(cls, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(f"type object '{cls.__name__}' has no attribute '{name}'")

        try:
            static_obj = cls._hlmod_get_static()
        except RuntimeError:
            static_methods = type.__getattribute__(cls, "_hl_static_methods")
            if name in static_methods:
                return _HlStaticCallable(cls, name, static_methods[name])
            raise
        if name == "STATIC":
            return static_obj
        return getattr(static_obj, name)

    def __setattr__(cls, name: str, value: Any) -> None:
        if not name.startswith("_") and name != "STATIC":
            try:
                static_obj = cls._hlmod_get_static()
            except (AttributeError, RuntimeError):
                static_obj = None

            if static_obj is not None and name in type(static_obj)._hl_fields:
                setattr(static_obj, name, value)
                return

        super().__setattr__(name, value)


class HlObject(metaclass=HlObjectMeta):
    """
    The base class for all generated Haxe object stubs.
    
    This class uses Python's magic methods to proxy attribute access 
    (getting and setting) directly to the live Haxe object in memory.
    This allows for natural, Pythonic syntax like `player.health = 100`.
    """
    
    _hl_fields: dict[str, int] = {}
    _hlmod_ptr: 'HlPtr'
    _hl_static_tindex: int | None = None
    _hl_static_obj: Any = None
    _hl_static_methods: dict[str, int] = {}

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


class HlVirtual:
    """
    Base class for HashLink virtual interface values.

    Concrete generated virtual stubs register with `@hltype(...)` the same way
    object stubs do. When no specific stub has been imported yet, hlmod falls
    back to this generic wrapper and resolves field names lazily from the
    underlying virtual metadata.
    """

    _hl_fields: dict[str, int] = {}
    _hlmod_ptr: 'HlPtr'

    def __init__(self, ptr: 'HlPtr') -> None:
        object.__setattr__(self, "_hlmod_ptr", ptr)
        object.__setattr__(self, "_hl_dynamic_fields", None)

    def _hlmod_field_map(self) -> dict[str, int]:
        if type(self) is not HlVirtual:
            return type(self)._hl_fields

        cached = object.__getattribute__(self, "_hl_dynamic_fields")
        if cached is not None:
            return cached

        fields: dict[str, int] = {}
        count = hlmod.get_virtual_field_count(self._hlmod_ptr)
        for index in range(count):
            fields[hlmod.get_virtual_field_name(self._hlmod_ptr, index)] = index
        object.__setattr__(self, "_hl_dynamic_fields", fields)
        return fields

    def __getattr__(self, name: str) -> Any:
        field_index = self._hlmod_field_map().get(name)
        if field_index is not None:
            return hlmod.get_virtual_field(self._hlmod_ptr, field_index)
        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")

    def __setattr__(self, name: str, value: Any) -> None:
        field_index = self._hlmod_field_map().get(name)
        if field_index is not None:
            hlmod.set_virtual_field(self._hlmod_ptr, field_index, value)
        else:
            object.__setattr__(self, name, value)

    def fields(self) -> tuple[str, ...]:
        return tuple(self._hlmod_field_map().keys())

    def items(self) -> list[tuple[str, Any]]:
        return [(name, getattr(self, name)) for name in self.fields()]

    def to_dict(self) -> dict[str, Any]:
        return dict(self.items())

    def __repr__(self) -> str:
        ptr_val = self._hlmod_ptr.ptr if self._hlmod_ptr else 0
        return f"<{self.__class__.__name__} pointing to 0x{ptr_val:X}>"


class HlEnum(IntEnum):
    """Base class for HL enums that have no parameters."""
    pass

class HlEnumObject(HlObject):
    """Base class for HL enum constructors that have parameters."""
    pass


class _HlStaticCallable:
    """
    Fallback wrapper for static methods before their companion global is materialized.
    """

    def __init__(self, owner: type[HlObject], name: str, findex: int | str) -> None:
        self._owner = owner
        self._name = name
        self._findex = findex

    def _hlmod_resolve_findex(self) -> int:
        if isinstance(self._findex, str):
            self._findex = hlmod.findex_for_name(self._findex)
        return self._findex

    def __call__(self, *args: Any) -> Any:
        return hlmod.call(self._hlmod_resolve_findex(), args)

    def __repr__(self) -> str:
        target = self._findex if isinstance(self._findex, str) else f"f@{self._findex}"
        return f"<static {self._owner.__name__}.{self._name} {target}>"

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
