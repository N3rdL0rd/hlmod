"""Generic Heaps/hxd resource-filesystem overlay.

Every Heaps game picks one of three ways to initialize its resource loader
at compile time (`hxd.Res.initEmbed`, `.initLocal`, or `.initPak`), and the
concrete `hxd.fs.FileSystem` each of those produces is a different class -
compiled-in bytes, loose files on disk, or a packed `.pak` archive. Mods
don't need to know or care which one a given game uses: `hxd.res.Loader.fs`
is always some object implementing the `hxd.fs.FileSystem` interface, and
that interface is the one thing every Heaps game keeps regardless of which
init path it took (`hxd.res.Loader` can't work without it, and DCE can't
strip an interface something else still dispatches through).

This module hooks whichever `initEmbed`/`initLocal`/`initPak` the loaded
game's bytecode actually has, and wraps `Loader.fs` in an overlay that
checks a list of mod-registered directories for a matching loose file before
falling back to the game's own filesystem - the same "loose files shadow
the packed/embedded originals" workflow Heaps itself uses for local dev
builds, just generalized to any number of independently-installed mods.

Only `FileEntry.getBytes()` is implemented for overridden paths - every
built-in Heaps resource type (Image, Model, Sound, Font, ...) ultimately
reads through it. Streaming reads (`readBytes`/`open`) and directory
listing on an overridden entry are not: nothing in this module needs them,
and faking them well requires knowing a lot more about a specific target
game than this package assumes.
"""

from pathlib import Path

import hlmod
from hlobj import HlObject, HlObjectMeta, hltype

MOD_INFO = {"id": "heaps", "dependencies": ["modcore"]}

_INIT_NAMES = ("hxd.$Res.initEmbed", "hxd.$Res.initLocal", "hxd.$Res.initPak")

_overlay_dirs: list[Path] = []
_installed = False
_OverlayFileSystem: type | None = None
_OverlayFileEntry: type | None = None
_bytes_fields: tuple[int, int] | None = None


def add_overlay_dir(path: str | Path) -> None:
    """Register a directory of loose override files, checked in registration
    order (first-registered wins) before the game's own resources. Safe to
    call before the game's resource loader exists yet - the directory is
    just queued until `hxd.Res.init*()` actually runs."""
    resolved = Path(path)
    if resolved not in _overlay_dirs:
        _overlay_dirs.append(resolved)


def _field_index(type_index: int, name: str) -> int | None:
    """A plain data field's index by name, or None if `name` isn't one (it
    may not exist at all, or may be a property with no backing field)."""
    for field in hlmod.inspect_native(type_index)["fields"]:
        if field["name"] == name:
            return field["index"]
    return None


def _field_type_index(type_index: int, name: str) -> int | None:
    """The declared type of a data field by name, or None if `name` isn't
    one - used for `Loader.fs`, where the *declared* type (the
    `hxd.fs.FileSystem` interface) is what `create_subclass`'s `interfaces=`
    needs, not whatever concrete class happens to be assigned to it."""
    for field in hlmod.inspect_native(type_index)["fields"]:
        if field["name"] == name:
            return field["type"]["type_index"]
    return None


def _interface_method_return_type(interface_type_index: int, name: str) -> int:
    """A named method's return type, for a method declared on an HVIRTUAL
    (Haxe interface) type. Interface members show up under `"fields"`, each
    naming a separate HMETHOD/HFUN type that itself has to be inspected to
    read `arguments`/`return_type` - unlike a real class's own methods,
    which `inspect_native` already expands inline under `"methods"`."""
    for field in hlmod.inspect_native(interface_type_index)["fields"]:
        if field["name"] == name:
            return hlmod.inspect_native(field["type"]["type_index"])["return_type"]["type_index"]
    raise LookupError(f"No member named {name!r} on interface type index {interface_type_index}")


def _call_through(findex: int):
    """A call-through method body identical in shape to what the generated
    stubs emit for an ordinary instance method: it calls the original
    bytecode function directly by findex, bypassing virtual dispatch, so
    it works both as `_bind`'s placeholder "inherited" implementation and
    as what a subclass's `super().method()` actually reaches."""
    def method(self, *args):
        return hlmod.call(findex, (self, *args))
    return method


def _bind(type_index: int) -> type:
    """A Python wrapper for an existing native type, purely so it can serve
    as a `create_subclass` base. `HlObjectMeta` only recognizes a method as
    overridable when it appears in the base's own `_hl_methods` *and* has a
    real callable of the same name somewhere in the base's own MRO (used as
    the "inherited" implementation to diff overrides against) - the
    generated stubs get this for free from their per-method bodies, so a
    from-scratch bind needs to synthesize the same call-through bodies from
    `inspect_native` instead of importing a stub module."""
    info = hlmod.inspect_native(type_index)
    fields = {field["name"]: field["index"] for field in info["fields"]}
    methods = {method["name"]: method["name"] for method in info["methods"] if method["name"] != "new"}
    namespace = {name: _call_through(method["findex"]) for method in info["methods"]
                 for name in (method["name"],) if name != "new"}
    namespace["_hl_fields"] = fields
    namespace["_hl_methods"] = methods

    return hltype(type_index)(HlObjectMeta("_Bound", (HlObject,), namespace))


def _make_bytes(data: bytes) -> hlmod.HlPtr:
    """A real `haxe.io.Bytes` instance wrapping `data`, built directly from
    its two fields (length: Int, b: hl.Bytes) rather than through a Haxe
    factory function, so arbitrary binary content round-trips exactly -
    `Bytes.ofString` would corrupt anything that isn't valid UTF-8."""
    global _bytes_fields
    if _bytes_fields is None:
        bytes_type = hlmod.type_index_for_name("haxe.io.Bytes")
        length_field = _field_index(bytes_type, "length")
        raw_field = _field_index(bytes_type, "b")
        if length_field is None or raw_field is None:
            raise RuntimeError("haxe.io.Bytes does not have the expected length/b fields")
        _bytes_fields = (bytes_type, length_field, raw_field)
    bytes_type, length_field, raw_field = _bytes_fields
    instance = hlmod.alloc_obj(bytes_type)
    hlmod.set_obj_field(instance, length_field, len(data))
    hlmod.set_obj_field(instance, raw_field, hlmod.bytes_from(data))
    return instance


def _build_overlay_classes(fs_type_index: int, entry_type_index: int) -> None:
    """Synthesizes the overlay's FileSystem and FileEntry classes the first
    time they're needed. FileSystem implements `hxd.fs.FileSystem` fresh
    (see create_subclass's `interfaces=`) rather than subclassing any
    particular concrete Heaps class, so this never depends on which of
    initEmbed/initLocal/initPak - or which third-party FileSystem a mod
    itself ships - happens to survive dead-code elimination in this game's
    build. FileEntry is an ordinary override instead: `hxd.fs.FileEntry` is
    a real base class, not an interface, so overriding `getBytes` on a
    direct subclass needs nothing new."""
    global _OverlayFileSystem, _OverlayFileEntry

    loader_carrier = _bind(hlmod.type_index_for_name("hxd.res.Loader"))
    entry_base = _bind(entry_type_index)
    path_field = _field_index(entry_type_index, "path")

    class OverlayFileEntry(entry_base):
        def __init__(self, path: str, data: bytes):
            super().__init__()
            if path_field is not None:
                hlmod.set_obj_field(self._hlmod_ptr, path_field, path)
            self._data = data

        def getBytes(self):
            return _make_bytes(self._data)

    class OverlayFileSystem(loader_carrier, implements=[fs_type_index]):
        def __init__(self, base_fs):
            super().__init__()
            self._base_fs = base_fs

        def _find_override(self, path):
            for directory in _overlay_dirs:
                candidate = directory / path
                if candidate.is_file():
                    return candidate
            return None

        def get(self, path):
            candidate = self._find_override(path)
            if candidate is not None:
                return OverlayFileEntry(path, candidate.read_bytes())
            return self._base_fs.get(path)

        def exists(self, path):
            return self._find_override(path) is not None or self._base_fs.exists(path)

        def getRoot(self):
            return self._base_fs.getRoot()

        def dispose(self):
            self._base_fs.dispose()

    _OverlayFileEntry = OverlayFileEntry
    _OverlayFileSystem = OverlayFileSystem


def _install() -> None:
    global _installed
    if _installed:
        return
    try:
        # A class with only static members (`hxd.Res` has no instance side)
        # compiles to a single hidden global instance of a companion type
        # named `pack.$Type`, not `pack.Type` - the dollar sign marks the
        # *last* path segment, so its static fields (like `loader`) are
        # ordinary object fields read off of that one global instance.
        res_type = hlmod.type_index_for_name("hxd.$Res")
    except KeyError:
        return  # this game doesn't use hxd.Res at all

    res_global = hlmod.get_global(res_type)
    if res_global is None:
        return

    loader_field = _field_index(res_type, "loader")
    if loader_field is None:
        return  # not the hxd.Res shape this module expects

    loader_ptr = hlmod.get_obj_field(res_global, loader_field)
    if loader_ptr is None:
        return  # hxd.Res.init*() hasn't run (yet); nothing to overlay onto

    loader_type = loader_ptr.type_index
    fs_field, fs_type_index = _field_index(loader_type, "fs"), _field_type_index(loader_type, "fs")
    if fs_field is None:
        return  # not the hxd.res.Loader shape this module expects

    base_fs = hlmod.get_obj_field(loader_ptr, fs_field)
    entry_type_index = _interface_method_return_type(fs_type_index, "get")

    if _OverlayFileSystem is None:
        _build_overlay_classes(fs_type_index, entry_type_index)

    overlay = _OverlayFileSystem(base_fs)
    hlmod.set_obj_field(loader_ptr, fs_field, overlay)
    _installed = True


def _try_install(result, *args):
    _install()


def initialize() -> None:
    from modcore import postfix_hook

    for name in _INIT_NAMES:
        try:
            findex = hlmod.findex_for_name(name)
        except NameError:
            continue
        postfix_hook(findex, priority=-1_000_000)(_try_install)
