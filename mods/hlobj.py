"""
Abstract base classes for accessing HL types in Python.
"""

import hlmod
from hlmod import register_hlobj, HlPtr
from typing import Any, Callable, ClassVar, Generic, Iterable, Iterator, Type, TypeVar, get_args, get_origin
from hlvalues import HlBytes, HlDynObject, HlEnum, HlRef, inspect_native

F = TypeVar("F", bound=Callable[..., Any])


def hlfunction(findex: int) -> Callable[[F], F]:
    """Mark a generated callable as a native hook target without wrapping it."""
    def decorate(function: F) -> F:
        setattr(function, "__hl_findex__", findex)
        return function
    return decorate

T = TypeVar("T", bound=object)

def hltype(idx: int) -> Callable[[Type[T]], Type[T]]:
    """
    Register a HlObject to be created as a proxy for a specific tIndex in the bytecode.
    """

    def decorator(cls: Type[T]) -> Type[T]:
        """The actual decorator that registers the class."""
        register_hlobj(idx, cls)
        type.__setattr__(cls, "_hl_type_index", idx)
        return cls
        
    return decorator

class HlObjectMeta(type):
    """
    Metaclass that forwards class-level access to a type's HL static object when one exists.
    """

    def __new__(mcls, name, bases, namespace, **kwargs):
        cls = super().__new__(mcls, name, bases, namespace, **kwargs)
        if namespace.get("_hl_generated", False):
            return cls
        native_bases = [base for base in bases if isinstance(base, HlObjectMeta)
                        and getattr(base, "_hl_type_index", None) is not None]
        if not native_bases:
            return cls
        if len(native_bases) != 1:
            raise TypeError("A Python HL subclass must have exactly one native base")
        base = native_bases[0]
        native_fields = base._hl_fields.keys() - base._hl_methods.keys()
        for klass in cls.__mro__:
            if klass is base:
                break
            shadowed = native_fields & klass.__dict__.keys()
            if shadowed:
                raise TypeError(f"Python class attributes cannot shadow native fields: {', '.join(sorted(shadowed))}")
        overrides = {}
        for python_name, native_name in base._hl_methods.items():
            implementation = next(klass.__dict__[python_name] for klass in cls.__mro__
                                  if python_name in klass.__dict__)
            inherited = next(klass.__dict__[python_name] for klass in base.__mro__
                             if python_name in klass.__dict__)
            if implementation is inherited:
                continue
            if not callable(implementation) or isinstance(implementation, (staticmethod, classmethod)):
                raise TypeError(f"HL override {python_name!r} must be an instance method")
            overrides[native_name] = implementation
        native_type = hlmod.create_subclass(base._hl_type_index, cls, overrides)
        type.__setattr__(cls, "_hl_type_index", native_type)
        type.__setattr__(cls, "_hl_generated", False)
        type.__setattr__(cls, "_hl_static_obj", None)
        return cls

    def __call__(cls, *args: Any, **kwargs: Any) -> Any:
        native_type = type.__getattribute__(cls, "_hl_type_index")
        if native_type is None:
            return super().__call__(*args, **kwargs)
        new = cls.__new__
        instance = new(cls) if new is object.__new__ else new(cls, *args, **kwargs)
        if not isinstance(instance, cls):
            return instance
        ptr = hlmod.alloc_obj(native_type)
        object.__setattr__(instance, "_hlmod_ptr", ptr)
        if isinstance(native_type, HlPtr):
            hlmod.bind_instance(ptr, instance)
        result = cls.__init__(instance, *args, **kwargs)
        if result is not None:
            raise TypeError("__init__() must return None")
        return instance

    def _hlmod_call_static(cls, name: str, *args: Any) -> Any:
        try:
            static_obj = cls._hlmod_ensure_static()
        except RuntimeError:
            return _HlStaticCallable(cls, name, cls._hl_static_methods[name])(*args)
        # Bypass the public static forwarding method when this is a standalone
        # static type: the actual HL function is stored in the companion field.
        field = type(static_obj)._hl_fields.get(name)
        if field is not None:
            return hlmod.get_obj_field(static_obj._hlmod_ptr, field)(*args)
        method = type(static_obj).__dict__.get(name)
        if isinstance(method, staticmethod):
            return _HlStaticCallable(cls, name, cls._hl_static_methods[name])(*args)
        return getattr(static_obj, name)(*args)

    def _hlmod_ensure_static(cls) -> Any:
        tindex = type.__getattribute__(cls, "_hl_static_tindex")
        if tindex is None:
            raise AttributeError(f"type object '{cls.__name__}' has no static HL companion")

        cached = type.__getattribute__(cls, "_hl_static_obj")
        static_obj = hlmod.ensure_global(tindex)
        if static_obj is None:
            raise RuntimeError(f"HL static object for '{cls.__name__}' is unavailable")

        if cached is not None:
            cached_ptr = getattr(cached, "_hlmod_ptr", None)
            new_ptr = getattr(static_obj, "_hlmod_ptr", None)
            if cached_ptr is not None and new_ptr is not None and cached_ptr.ptr == new_ptr.ptr:
                return cached

        type.__setattr__(cls, "_hl_static_obj", static_obj)
        return static_obj

    def _hlmod_static_default(cls, name: str) -> Any:
        """Return a sensible default for an uninitialized static data field."""
        for klass in cls.__mro__:
            if not isinstance(klass, HlObjectMeta):
                continue
            annots = klass.__dict__.get("__annotations__", {})
            if name in annots:
                ann = annots[name]
                break
        else:
            return None

        if isinstance(ann, str):
            ann = ann.strip('"\'')
            for prefix in ("ClassVar[", "typing.ClassVar["):
                if ann.startswith(prefix) and ann.endswith("]"):
                    ann = ann[len(prefix):-1].strip().strip('"\'')
                    break
            if ann == "bool":
                return False
            if ann in ("int", "float"):
                return 0
            return None

        if get_origin(ann) is ClassVar:
            ann = get_args(ann)[0]

        if isinstance(ann, type):
            if issubclass(ann, bool):
                return False
            if issubclass(ann, int):
                return 0
            if issubclass(ann, float):
                return 0.0
        return None

    def __getattr__(cls, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(f"type object '{cls.__name__}' has no attribute '{name}'")

        if name == "STATIC":
            return cls._hlmod_ensure_static()

        static_fields = type.__getattribute__(cls, "_hl_static_fields")
        if name in static_fields:
            try:
                static_obj = cls._hlmod_ensure_static()
            except RuntimeError:
                return cls._hlmod_static_default(name)
            return getattr(static_obj, name)

        try:
            static_obj = cls._hlmod_ensure_static()
        except RuntimeError:
            static_methods = type.__getattribute__(cls, "_hl_static_methods")
            if name in static_methods:
                return _HlStaticCallable(cls, name, static_methods[name])
            raise
        return getattr(static_obj, name)

    def __setattr__(cls, name: str, value: Any) -> None:
        if not name.startswith("_") and name != "STATIC":
            static_fields = type.__getattribute__(cls, "_hl_static_fields")
            if name in static_fields:
                setattr(cls._hlmod_ensure_static(), name, value)
                return

            try:
                static_obj = cls._hlmod_ensure_static()
            except (AttributeError, RuntimeError):
                static_obj = None

            if static_obj is not None and name in type(static_obj)._hl_fields:
                setattr(static_obj, name, value)
                return

        if name in cls._hl_fields and name not in cls._hl_methods:
            raise TypeError(f"Python class attributes cannot shadow native field {name!r}")

        super().__setattr__(name, value)


class HlObject(metaclass=HlObjectMeta):
    """
    The base class for all generated Haxe object stubs.
    
    This class uses Python's magic methods to proxy attribute access 
    (getting and setting) directly to the live Haxe object in memory.
    This allows for natural, Pythonic syntax like `player.health = 100`.
    """
    
    _hl_fields: dict[str, int] = {}
    _hl_type_index: int | HlPtr | None = None
    _hl_methods: dict[str, str] = {}
    _hl_bound_fields: dict[str, int] = {}
    _hlmod_ptr: 'HlPtr'
    _hl_static_tindex: int | None = None
    _hl_static_obj: Any = None
    _hl_static_fields: dict[str, int] = {}
    _hl_static_methods: dict[str, int | str] = {}

    def __init__(self) -> None:
        """Initialize an object without a native constructor."""

    @classmethod
    def _hlmod_wrap(cls: Type[T], ptr: HlPtr) -> T:
        """Wrap an existing object without allocating or running Python init."""
        instance = object.__new__(cls)
        object.__setattr__(instance, "_hlmod_ptr", ptr)
        return instance

    def __getattribute__(self, name: str) -> Any:
        # Normal dynamic-method access must follow the mutable native closure.
        # Explicit Base.method(self) and super().method bypass this lookup and
        # therefore retain the generated original/base implementation.
        cls = object.__getattribute__(self, "__class__")
        field_index = type.__getattribute__(cls, "_hl_bound_fields").get(name)
        if field_index is not None:
            return hlmod.get_obj_field(object.__getattribute__(self, "_hlmod_ptr"), field_index)
        return object.__getattribute__(self, name)

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

    def __dir__(self) -> list[str]:
        """Include native fields and methods so completion sees the real API."""
        cls = object.__getattribute__(self, "__class__")
        names = set(object.__dir__(self))
        names.update(type.__getattribute__(cls, "_hl_fields"))
        names.update(type.__getattribute__(cls, "_hl_methods"))
        return sorted(names)
            
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
    @classmethod
    def _hlmod_wrap(cls: Type[T], ptr: HlPtr) -> T:
        instance = object.__new__(cls)
        object.__setattr__(instance, "_hlmod_ptr", ptr)
        object.__setattr__(instance, "_hl_dynamic_fields", None)
        return instance


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


Element = TypeVar("Element")


class HlArray(Generic[Element]):
    """A live, typed HL array; writes affect the original native array."""

    def __init__(self, ptr: HlPtr) -> None:
        self._hlmod_ptr = ptr

    @classmethod
    def create(cls, element_type_index: int, values: Iterable[Element] = ()) -> "HlArray[Element]":
        return cls(hlmod.array_new(element_type_index, values))

    @property
    def element_type_index(self) -> int | None:
        return hlmod.array_element_type(self._hlmod_ptr)

    def __len__(self) -> int:
        return hlmod.array_length(self._hlmod_ptr)

    def __getitem__(self, index: int) -> Element:
        return hlmod.array_get(self._hlmod_ptr, index)

    def __setitem__(self, index: int, value: Element) -> None:
        hlmod.array_set(self._hlmod_ptr, index, value)

    def __iter__(self) -> Iterator[Element]:
        for index in range(len(self)):
            yield self[index]

    def __repr__(self) -> str:
        return f"<HlArray length={len(self)} ptr=0x{self._hlmod_ptr.ptr:X}>"
