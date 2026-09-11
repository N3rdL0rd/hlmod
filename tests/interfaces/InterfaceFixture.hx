interface Greeter {
    function greet(name: String): String;
    function shout(name: String): String;
}

// Implements Greeter for real, so the *existing* override path (a Python
// subclass overriding an already-declared ancestor method) keeps composing
// correctly alongside brand-new interface-only methods below.
class NativeGreeter implements Greeter {
    public function new() {}
    public function greet(name: String): String {
        return "native-hi " + name;
    }
    public function shout(name: String): String {
        return "native-hello " + name.toUpperCase();
    }
}

// Deliberately does NOT implement Greeter and declares no greet()/shout()
// methods at all - the "brand-new interface method" case, not an override.
class PlainBase {
    public var tag: Int;
    public function new() {
        tag = 42;
    }
}

class InterfaceFixture {
    @:keep
    static function callThrough(g: Greeter, name: String): String {
        return g.greet(name) + "/" + g.shout(name);
    }

    static function main() {
        var native = new NativeGreeter();
        trace(callThrough(native, "vanilla"));
        trace("INTERFACE_FIXTURE_OK");
    }
}
