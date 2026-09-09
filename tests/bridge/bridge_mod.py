MOD_INFO = {"id": "bridge_fixture", "dependencies": []}

import gc
import weakref

import hlmod
from stubs import BridgeBase, BridgeNativeChild, BridgeOther

from hlobj import HlArray, HlCallable
# Mods load before the Haxe static initializer runs.
assert BridgeBase.STATIC_VALUE == 0

def call(name, *args):
    return hlmod.call(hlmod.findex_for_name("$BridgeFixture." + name), args)


def hook(name):
    def register(function):
        hlmod.register_hook(hlmod.findex_for_name("$BridgeFixture." + name), function)
        return function
    return register


def raises(error, function, *args):
    try:
        function(*args)
    except error:
        return
    raise AssertionError(f"Expected {error!r} from {function.__name__}")


class PythonChild(BridgeBase):
    def __init__(self, value):
        super().__init__(value)
        self.python_state = {"offset": 100}

    def compute(self, delta):
        return super().compute(delta) + self.python_state["offset"]

    def direct(self, delta):
        return super().direct(delta) + 200


class PythonGrandchild(PythonChild):
    def compute(self, delta):
        return super().compute(delta) + 1000


class PythonOnNative(BridgeNativeChild):
    def compute(self, delta):
        return super().compute(delta) + 100


@hook("intHook")
def int_hook(context):
    return 123456789


@hook("boolHook")
def bool_hook(context):
    return True


@hook("floatHook")
def float_hook(context):
    return 3.25


@hook("singleHook")
def single_hook(context):
    return 1.25


@hook("i64Hook")
def i64_hook(context):
    return 0x1234567876543210


@hook("makePython")
def make_python(context, value):
    return PythonChild(value)


@hook("pythonChecks")
def python_checks(context, native):
    assert type(native) is BridgeNativeChild, type(native)
    assert native.compute(3) == 20
    assert BridgeBase.STATIC_VALUE == 8
    PythonChild.STATIC_VALUE = 19
    assert BridgeBase.staticCompute(2) == 21
    dynamic_native = call("echoDynamic", native)
    assert type(dynamic_native) is BridgeNativeChild
    assert dynamic_native._hlmod_ptr.ptr == native._hlmod_ptr.ptr
    assert call("echoBase", None) is None
    assert call("echoDynamic", None) is None
    assert call("nullable", None) is None
    assert call("nullable", -23) == -23
    for value in (-2147483648, 2147483647):
        assert call("echoInt", value) == value
    for value in (-9223372036854775808, 9223372036854775807):
        assert call("echoI64", value) == value
    raises(OverflowError, call, "echoInt", 2147483648)
    raises(OverflowError, call, "echoInt", -2147483649)
    raises(OverflowError, call, "echoI64", 9223372036854775808)
    for value in (True, False, 17, -19, 3.25, "héllo\U0001f680\0end"):
        assert call("echoDynamic", value) == value
    assert call("echoString", "\ufeffliteral BOM\0\U0001f680") == "\ufeffliteral BOM\0\U0001f680"
    assert call("echoSingle", 1.25) == 1.25
    raises(TypeError, call, "echoBase", BridgeOther())
    raises(TypeError, call, "echoBase", 1234)
    raises((IndexError, ValueError), hlmod.call, -1, ())
    raises(TypeError, hlmod.get_obj_field, hlmod.HlPtr(1, 11), 0)
    raises(TypeError, hlmod.call_closure, native._hlmod_ptr, ())
    raises((IndexError, ValueError), hlmod.register_hlobj, -1, BridgeBase)

    first = PythonChild(11)
    second = PythonChild(22)
    grandchild = PythonGrandchild(33)
    first.python_state["offset"] = 300
    assert call("invoke", first, 4) == 315
    assert call("invoke", second, 4) == 126
    assert call("invoke", grandchild, 4) == 1137
    assert call("invokeThread", first, 5) == 316
    assert call("invokeDirect", first, 2) == 209
    assert call("invoke", PythonOnNative(5), 3) == 116
    assert first.argumentCollision(7) == 18
    mutable = BridgeBase(9)
    assert mutable.changeable(1) == 510
    mutable.changeable = lambda delta: delta * 7
    assert mutable.changeable(2) == 14
    assert call("invokeDynamicField", mutable, 3) == 21
    assert call("echoBase", first) is first
    assert call("echoDynamic", first) is first
    first.peer = second
    assert first.peer is second
    first.peer = None
    assert first.peer is None
    raises(TypeError, setattr, first, "peer", BridgeOther())
    first.text = "Python\0\U0001f680"
    first.tiny = 255
    assert first.neighbor == 34 and first.flag is True
    first.flag = False
    assert first.tiny == 255 and first.neighbor == 34
    raises(OverflowError, setattr, first, "tiny", 256)
    assert first.text == "Python\0\U0001f680"
    assert call("invokeCallback", lambda value: value * 3, 7) == 21
    assert call("invokeCallback", first.compute, 4) == 315
    assert call("invokeMixed", lambda a, b, c, d, e: a + b + c + d + e) == 15.75
    assert call("invokeSingle", lambda value: value + 2.5) == 3.75
    values = call("makeNativeArray")
    assert list(values) == [2, 4, 6]
    values[1] = 9
    assert call("arrayTotal", values) == 17
    created = HlArray.create(values.element_type_index, [8, 9])
    assert call("arrayTotal", created) == 17
    raises(IndexError, created.__getitem__, 2)
    raises(TypeError, call, "arrayTotal", [8, 9])
    call("collect")
    raises(TypeError, call, "invokeCallback", call("makeStringCallback"), 1)

    def fail(value):
        raise ValueError("Python callback failure")

    assert call("catchCallback", fail) is True
    assert call("catchCallback", lambda value: BridgeOther()) is True
    raises(RuntimeError, call, "invokeCallback", fail, 1)
    record = call("makeVirtual")
    assert record.value == 42 and record.text == "structural"
    record.value = 73
    assert call("virtualValue", record) == 73
    record_roundtrip = call("echoDynamic", record)
    assert record_roundtrip.value == 73
    virtual_method = call("asVirtual", first)
    assert virtual_method.compute(2) == 313
    raises(TypeError, setattr, virtual_method, "compute", lambda value: value)
    virtual_callable = call("makeVirtualCallable")
    assert virtual_callable.apply(2) == 12
    virtual_callable.apply = lambda value: value * 5
    assert call("invokeVirtualCallable", virtual_callable, 3) == 15
    assert first.value == 11 and first.python_state["offset"] == 300
    assert call("echoDynamic", first) is first

    class StatefulCallback:
        def __call__(self, value):
            return value + 900

    callback = StatefulCallback()
    global callback_ref, callback_cycle_ref
    callback_ref = weakref.ref(callback)
    call("retainCallback", callback)
    del callback
    gc.collect()
    call("collect")
    assert callback_ref() is not None
    assert call("invokeRetainedCallback", 7) == 907

    cyclic = StatefulCallback()
    callback_cycle_ref = weakref.ref(cyclic)
    signature = call("makeIntCallback")._hlmod_ptr.type_index
    cyclic.closure = HlCallable(hlmod.make_callback(cyclic, signature))
    assert cyclic.closure(8) == 908
    del cyclic

    global native_container, contained_ref
    native_container = BridgeBase(70)
    contained = PythonChild(71)
    native_container.peer = contained
    contained.container = native_container
    contained_ref = weakref.ref(contained)
    del contained
    gc.collect()
    call("collect")
    assert native_container.peer is contained_ref()
    assert native_container.peer.python_state == {"offset": 100}

    call("retain", first)
    global retained_ref
    retained_ref = weakref.ref(first)
    del first
    gc.collect()
    call("collect")
    retained = call("getRetained")
    assert retained is retained_ref()
    assert retained.python_state == {"offset": 300}
    assert call("invoke", retained, 1) == 312
    del retained
    print("PYTHON_BRIDGE_CHECKS_OK", flush=True)


@hook("afterCollection")
def after_collection(context):
    global native_container
    assert native_container.peer is contained_ref()
    assert native_container.peer.python_state == {"offset": 100}
    del native_container
    assert call("getRetained") is retained_ref()
    call("release")
    assert call("invokeRetainedCallback", 9) == 909
    call("releaseCallback")
    # Conservative HL stack scanning may defer reclamation to a later collection.
    for _ in range(8):
        call("collect")
        gc.collect()
    assert retained_ref() is None, "unreachable Python/HL instance retained permanently"
    assert callback_ref() is None, "unreachable callback retained permanently"
    assert callback_cycle_ref() is None, "Python/native callback cycle was not collected"
    assert contained_ref() is None, "native container / Python child cycle was not collected"
    print("PYTHON_BRIDGE_GC_OK", flush=True)
