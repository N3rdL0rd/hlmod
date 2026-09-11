MOD_INFO = {"id": "interface_fixture", "dependencies": []}

import hlmod
from stubs import NativeGreeter, PlainBase


def call(name, *args):
    return hlmod.call(hlmod.findex_for_name("$InterfaceFixture." + name), args)


def raises(error, function, *args):
    try:
        function(*args)
    except error:
        return
    raise AssertionError(f"Expected {error!r} from {function.__name__}")


def initialize():
    call_through = hlmod.findex_for_name("$InterfaceFixture.callThrough")
    call_through_type = hlmod.function_type_index(call_through)
    info = hlmod.inspect_native(call_through_type)
    greeter_type = info["arguments"][0]["type_index"]

    # The existing override path still works: a Python subclass of a class
    # that genuinely implements Greeter overrides its real ancestor methods.
    class PythonGreeter(NativeGreeter):
        def greet(self, name):
            return "py-hi " + name

        def shout(self, name):
            return "py-hello " + name.upper()

    overridden = PythonGreeter()
    assert call("callThrough", overridden, "world") == "py-hi world/py-hello WORLD"
    print("OVERRIDE_PATH_OK", flush=True)

    # The new path: PlainBase declares no greet()/shout() at all, so these
    # are brand-new native proto entries synthesized from the Greeter
    # interface, not overrides of anything.
    class PyGreeter(PlainBase, implements=[greeter_type]):
        def greet(self, name):
            return "new-hi " + name

        def shout(self, name):
            return "new-hello " + name.upper()

    instance = PyGreeter()
    result = hlmod.call(call_through, (instance, "world"))
    assert result == "new-hi world/new-hello WORLD", result
    print("NEW_INTERFACE_METHOD_OK", flush=True)

    # A second instance of the same synthesized type dispatches independently.
    second = PyGreeter()
    result2 = hlmod.call(call_through, (second, "again"))
    assert result2 == "new-hi again/new-hello AGAIN", result2
    print("SECOND_INSTANCE_OK", flush=True)

    # A synthesized interface method's Python side can still raise, and it
    # propagates as a catchable HL exception, same as any other hook/override.
    class RaisingGreeter(PlainBase, implements=[greeter_type]):
        def greet(self, name):
            raise ValueError("intentional")

        def shout(self, name):
            return name

    raises(Exception, hlmod.call, call_through, (RaisingGreeter(), "x"))
    print("EXCEPTION_PROPAGATION_OK", flush=True)

    print("INTERFACE_MOD_OK", flush=True)
