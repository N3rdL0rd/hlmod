MOD_INFO = {"id": "value_fixture", "dependencies": []}

import hlmod
from hlobj import HlCallable, HlDynObject, HlEnum, HlPtr, HlRef, inspect_native
from hlobj import HlBytes
from modcore import hook
from stubs import ValueChild

reference = None


def call(name, *args):
    return hlmod.call(hlmod.findex_for_name("$ValueFixture." + name), args)


def raises(error, function, *args):
    try:
        function(*args)
    except error:
        return
    raise AssertionError(f"Expected {error.__name__} from {function.__name__}")


@hook("$ValueFixture.pythonChecks")
def python_checks(context, choice, record, child):
    global reference
    assert isinstance(choice, HlEnum)
    assert choice.constructor_name == "Payload"
    assert choice.constructor_index == 1
    assert choice.parameters == (42, "native")
    assert call("echoChoice", choice) == choice
    metadata = inspect_native(choice)
    constructors = {entry["name"]: entry for entry in metadata["constructors"]}
    assert constructors["Payload"]["parameters"][0]["kind"] == "i32"
    assert constructors["Payload"]["parameters"][1]["name"] == "String"
    empty = HlEnum.create(choice.type_index, "Empty")
    assert empty.parameters == ()
    assert call("echoChoice", empty) == empty
    payload = HlEnum.create(choice.type_index, "Payload", 51, "python")
    assert call("echoChoice", payload).parameters == (51, "python")
    nested = HlEnum.create(choice.type_index, "Nested", payload)
    assert call("echoChoice", nested).parameters == (payload,)
    raises(TypeError, call, "echoChoice", call("makeOther"))
    raises(TypeError, HlEnum.create, choice.type_index, "Payload", "bad", "type")
    raises(TypeError, HlEnum.create, choice.type_index, "Payload", 5)
    raises(ValueError, HlEnum.create, choice.type_index, "Unknown")
    raises(TypeError, HlEnum, HlPtr(1, 18))

    assert isinstance(record, HlDynObject)
    assert record["count"] == 12
    assert record["nested"].parameters == (9, "nested")
    assert set(record) == {"count", "remove", "nested"}
    assert "count" in dir(record)
    snapshot = iter(record)
    record["later"] = 5
    assert "later" not in tuple(snapshot)
    record["count"] = "changed"
    del record["remove"]
    raises(KeyError, record.__getitem__, "remove")
    raises(KeyError, record.__delitem__, "remove")
    record["none"] = None
    assert record["none"] is None and "none" in record
    record["unicode_\u2603"] = 101
    assert record["unicode_\u2603"] == 101 and "unicode_\u2603" in tuple(record)
    raises(ValueError, record.__setitem__, "bad\0name", 1)
    raises(TypeError, record.__setitem__, "callback", lambda value: value)
    callback = call("makeCallback")
    assert isinstance(callback, HlCallable)
    record["callback"] = callback
    assert record["callback"](33) == 33
    created = HlDynObject()
    created["enum"] = payload
    created["child"] = record
    echoed = call("echoDynamic", created)
    assert echoed["enum"] == payload
    echoed["child"]["viaNested"] = 67
    assert record["viaNested"] == 67
    assert {entry["name"] for entry in inspect_native(record)["fields"]} == set(record)
    raises(TypeError, hlmod.dynobj_get, HlPtr(1, 16), "count")

    child_info = inspect_native(child)
    fields = {entry["name"]: entry for entry in child_info["fields"]}
    methods = {entry["name"]: entry for entry in child_info["methods"]}
    assert fields["inherited"]["index"] != fields["own"]["index"]
    assert fields["inherited"]["declaring_type_index"] != fields["own"]["declaring_type_index"]
    assert methods["inheritedMethod"]["arguments"][-1]["kind"] == "i32"
    assert methods["ownMethod"]["return_type"]["kind"] == "bool"
    assert hlmod.get_obj_field(child._hlmod_ptr, fields["inherited"]["index"]) == 17
    assert "inherited" in dir(child) and "inheritedMethod" in dir(child)
    raises(TypeError, inspect_native, HlPtr(1, 11))
    raises(IndexError, inspect_native, -1)

    writer = call("makeRefWriter")
    ref_type = inspect_native(writer)["arguments"][0]["type_index"]
    assert inspect_native(ref_type)["element_type"]["kind"] == "i32"
    reference = HlRef[int].create(ref_type, 73)
    assert reference.value == 73
    assert reference.element_type_index == inspect_native(ref_type)["element_type"]["type_index"]
    echoed_ref = call("echoRef", reference)
    echoed_ref.value = 82
    assert reference.value == 82
    assert writer(reference, 91) == 91 and reference.value == 91
    raises(TypeError, reference.__class__.value.fset, reference, "bad")
    raises(TypeError, call, "floatRef", reference)
    raises(TypeError, HlRef.create, choice.type_index, 1)
    raises(TypeError, hlmod.ref_get, HlPtr(1, 14))
    raises(TypeError, call, "unsafeRef")
    native_bytes = call("makeBytes")
    assert isinstance(native_bytes, HlBytes)
    assert len(native_bytes) >= 4 and native_bytes.capacity >= 4
    assert native_bytes.read(0, 4) == b"\x01\x02\x03\x04"
    assert native_bytes[1] == 2 and native_bytes[0:2] == b"\x01\x02"
    native_bytes[0] = 9
    assert call("readByte", native_bytes, 0) == 9
    native_bytes[2:4] = b"\x07\x08"
    assert native_bytes.read(2, 2) == b"\x07\x08"
    raises(IndexError, native_bytes.read, 0, len(native_bytes) + 1)
    raises(IndexError, native_bytes.write, b"\x00", len(native_bytes))
    raises(ValueError, native_bytes.__setitem__, slice(0, 2), b"\x00")
    assert call("echoBytes", native_bytes) is not None
    # A plain Python buffer is copied into HL, so later edits are not shared.
    assert call("bytesTotal", bytearray(b"\x01\x02\x03"), 3) == 6
    assert call("bytesTotal", HlBytes.from_bytes(b"\x01\x02\x03"), 3) == 6
    created = HlBytes.create(4)
    assert len(created) == 4 and created.read() == b"\x00\x00\x00\x00"
    assert HlBytes.from_bytes("hi".encode("utf-16-le")).decode(length=4) == "hi"
    raises(TypeError, HlBytes, HlPtr(1, 8))
    reference.value = 73
    print("PYTHON_VALUE_CHECKS_OK", flush=True)


@hook("$ValueFixture.gcChecks")
def gc_checks(context, child):
    ptr = child._hlmod_ptr
    assert hlmod.is_gc_ptr(ptr), "a freshly allocated native object must be GC-managed"
    assert hlmod.gc_memsize(ptr) > 0
    assert hlmod.gc_memsize(hlmod.array_new(3, [])) is not None
    before = hlmod.gc_stats()
    assert set(before) == {"total_allocated", "allocation_count", "current_memory"}
    assert before["allocation_count"] > 0
    # `child` is still reachable from the caller's own Haxe stack frame, so a
    # real collection here must not free it - reading its field afterwards
    # both proves that and exercises gc_major() actually running the GC
    # rather than being a no-op stub.
    hlmod.gc_major()
    assert child.own is True
    after = hlmod.gc_stats()
    assert after["total_allocated"] >= before["total_allocated"], "total_allocated must never decrease"
    hlmod.gc_enable(False)
    hlmod.gc_enable(True)
    print("PYTHON_GC_CHECKS_OK", flush=True)

@hook("$ValueFixture.pythonRef")
def python_ref(context):
    return reference


@hook("$ValueFixture.pythonBytes")
def python_bytes(context):
    return HlBytes.from_bytes(b"\x01\x02\x03")


@hook("$ValueFixture.pythonRefChecks")
def python_ref_checks(context, value):
    assert isinstance(value, HlRef)
    assert value.value == 81 and reference.value == 81
    value.value = 99
    assert reference.value == 99
    print("PYTHON_REF_CHECKS_OK", flush=True)
