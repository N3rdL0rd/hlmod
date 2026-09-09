@:keep
enum ValueChoice {
    Empty;
    Payload(count:Int, text:String);
    Nested(value:ValueChoice);
}

@:keep
enum OtherChoice {
    Other;
}

@:keep
class ValueBase {
    public var inherited:Int;
    public function new() { inherited = 17; }
    public function inheritedMethod(delta:Int):Int { return inherited + delta; }
}

@:keep
class ValueChild extends ValueBase {
    public var own:Bool;
    public function new() { super(); own = true; }
    public function ownMethod():Bool { return own; }
}

@:keep
class ValueFixture {
    static function check(ok:Bool, message:String):Void {
        if (!ok) throw message;
    }

    static function pythonChecks(choice:ValueChoice, record:Dynamic, child:ValueChild):Void {}
    static function pythonRef():hl.Ref<Int> { var storage = 0; return storage; }
    static function pythonRefChecks(value:hl.Ref<Int>):Void {}
    static function echoChoice(value:ValueChoice):ValueChoice { return value; }
    static function makeOther():OtherChoice { return Other; }
    static function echoDynamic(value:Dynamic):Dynamic { return value; }
    static function echoRef(value:hl.Ref<Int>):hl.Ref<Int> { return value; }
    static function floatRef(value:hl.Ref<Float>):Float { return value.get(); }
    static function writeRef(value:hl.Ref<Int>, number:Int):Int {
        value.set(number);
        return value.get();
    }
    static function makeRefWriter():hl.Ref<Int>->Int->Int { return writeRef; }
    static function echoInt(value:Int):Int { return value; }
    static function makeCallback():Int->Int { return echoInt; }
    static function unsafeRef():hl.Ref<Int> { var storage = 19; return storage; }
    static function makeRecord():Dynamic {
        var value:Dynamic = {};
        Reflect.setField(value, "count", 12);
        Reflect.setField(value, "remove", true);
        Reflect.setField(value, "nested", Payload(9, "nested"));
        return value;
    }
    static function makeBytes():hl.Bytes {
        var bytes = new hl.Bytes(4);
        bytes.setI32(0, 0x04030201);
        return bytes;
    }
    static function readByte(bytes:hl.Bytes, offset:Int):Int { return bytes.getUI8(offset); }
    static function echoBytes(bytes:hl.Bytes):hl.Bytes { return bytes; }
    static function pythonBytes():hl.Bytes { return new hl.Bytes(1); }
    static function bytesTotal(bytes:hl.Bytes, length:Int):Int {
        var total = 0;
        for (i in 0...length) total += bytes.getUI8(i);
        return total;
    }

    static function main():Void {
        var record = makeRecord();
        pythonChecks(Payload(42, "native"), record, new ValueChild());
        check(Reflect.field(record, "count") == "changed", "Python dynamic write not visible");
        check(!Reflect.hasField(record, "remove"), "Python deletion not visible");
        var callback:Int->Int = Reflect.field(record, "callback");
        check(callback(31) == 31, "Typed dynamic callback not retained");
        var reference = pythonRef();
        check(reference.get() == 73, "Python reference allocation not visible");
        reference.set(81);
        pythonRefChecks(reference);
        check(reference.get() == 99, "Python reference write not visible");
        var fromPython = pythonBytes();
        check(bytesTotal(fromPython, 3) == 6, "Python-allocated bytes not visible in HL");
        Sys.println("VALUE_FIXTURE_OK");
    }
}
