@:keep
class BridgeBase {
    public static var STATIC_VALUE:Int = 8;
    public static function staticCompute(delta:Int):Int {
        return STATIC_VALUE + delta;
    }
    public var value:Int;
    public var peer:BridgeBase;
    public var text:String;

    public var tiny:hl.UI8;
    public var neighbor:hl.UI8;
    public var flag:Bool;
    public function new(value:Int) {
        this.value = value;
        this.text = "native";
        this.tiny = 12;
        this.neighbor = 34;
        this.flag = true;
    }

    public function compute(delta:Int):Int {
        return value + delta;
    }

    public function direct(delta:Int):Int {
        return value - delta;
    }
    public function staticmethod():Int {
        return 42;
    }
    public function argumentCollision(hlmod:Int):Int {
        return value + hlmod;
    }
    public dynamic function changeable(delta:Int):Int {
        return value + delta + 500;
    }

    public function identity():BridgeBase {
        return this;
    }
}

@:keep
class BridgeNativeChild extends BridgeBase {
    public function new(value:Int) {
        super(value);
    }

    override public function compute(delta:Int):Int {
        return super.compute(delta) * 2;
    }
}

@:keep
class BridgeOther {
    public function new() {}
}

@:keep
class BridgeHelper {
    public static function compute(value:BridgeBase):Int {
        return 999;
    }
}

@:keep
class BridgeFixture {
    static var retained:BridgeBase;
    static var retainedCallback:Int->Int;

    static function check(ok:Bool, message:String):Void {
        if (!ok) throw message;
    }

    static function makePython(value:Int):BridgeBase {
        return new BridgeBase(value);
    }

    static function pythonChecks(native:BridgeBase):Void {}
    static function afterCollection():Void {}
    static function invokeDynamicField(value:BridgeBase, delta:Int):Int {
        return value.changeable(delta);
    }
    static function invokeThread(value:BridgeBase, delta:Int):Int {
        var done = new sys.thread.Lock();
        var result = -999;
        sys.thread.Thread.create(function() {
            try { result = value.compute(delta); } catch (error:Dynamic) { result = -998; }
            done.release();
        });
        if (!done.wait(5)) throw "Python override worker timed out";
        return result;
    }
    static function intHook():Int { return -1; }
    static function boolHook():Bool { return false; }
    static function floatHook():Float { return -1; }
    static function singleHook():hl.F32 { return -1; }
    static function i64Hook():hl.I64 { return 0; }
    static function nullable(value:Null<Int>):Null<Int> { return value; }
    static function echoBase(value:BridgeBase):BridgeBase { return value; }
    static function echoDynamic(value:Dynamic):Dynamic { return value; }
    static function echoString(value:String):String { return value; }
    static function echoInt(value:Int):Int { return value; }
    static function echoI64(value:hl.I64):hl.I64 { return value; }
    static function echoSingle(value:hl.F32):hl.F32 { return value; }
    static function invoke(value:BridgeBase, delta:Int):Int { return value.compute(delta); }
    static function invokeDirect(value:BridgeBase, delta:Int):Int { return value.direct(delta); }
    static function invokeCallback(callback:Int->Int, value:Int):Int { return callback(value); }
    static function invokeMixed(callback:Int->Float->Bool->Int->Float->Float):Float {
        return callback(2, 3.25, true, 4, 5.5);
    }
    static function invokeSingle(callback:hl.F32->hl.F32):hl.F32 {
        return callback(1.25);
    }
    static function makeIntCallback():Int->Int {
        return echoInt;
    }
    static function invokeRetainedCallback(value:Int):Int {
        return retainedCallback(value);
    }
    static function retain(value:BridgeBase):Void { retained = value; }
    static function catchCallback(callback:Int->Int):Bool {
        try { callback(1); } catch (error:Dynamic) { return true; }
        return false;
    }
    static function makeStringCallback():String->String {
        return echoString;
    }
    static function makeVirtual():{value:Int, text:String} {
        return {value: 42, text: "structural"};
    }
    static function virtualValue(record:{value:Int, text:String}):Int {
        return record.value;
    }
    static function asVirtual(value:BridgeBase):{function compute(delta:Int):Int;} {
        return value;
    }
    static function makeVirtualCallable():{apply:Int->Int} {
        return {apply: function(value:Int):Int { return value + 10; }};
    }
    static function invokeVirtualCallable(record:{apply:Int->Int}, value:Int):Int {
        return record.apply(value);
    }
    static function release():Void { retained = null; }
    static function getRetained():BridgeBase { return retained; }
    static function retainCallback(callback:Int->Int):Void { retainedCallback = callback; }
    static function releaseCallback():Void { retainedCallback = null; }
    static function collect():Void { hl.Gc.major(); }
    static function makeNativeArray():hl.NativeArray<Int> {
        var values = new hl.NativeArray<Int>(3);
        values[0] = 2;
        values[1] = 4;
        values[2] = 6;
        return values;
    }
    static function arrayTotal(values:hl.NativeArray<Int>):Int {
        var result = 0;
        for (i in 0...values.length) result += values[i];
        return result;
    }
    static function main():Void {
        check(intHook() == 123456789, "integer hook returned wrong value");
        check(boolHook(), "boolean hook returned wrong value");
        check(floatHook() == 3.25, "float hook returned wrong value");
        check(singleHook() == 1.25, "float32 hook returned wrong value");
        check(i64Hook() == ((0x12345678:hl.I64) << 32 | 0x76543210), "int64 hook returned wrong value");
        var native:BridgeBase = new BridgeNativeChild(7);
        pythonChecks(native);
        var python:BridgeBase = makePython(10);
        check(python.value == 10, "native constructor was not called");
        check(python.compute(3) == 113, "virtual override did not reach Python");
        check(python.direct(3) == 207, "direct override did not reach Python");
        check(BridgeHelper.compute(python) == 999, "unrelated static helper was intercepted");
        var bound = python.compute;
        check(bound(4) == 114, "bound override did not reach Python");
        var dynamicValue:Dynamic = python;
        check(dynamicValue.compute(5) == 115, "dynamic override did not reach Python");
        check(Std.isOfType(python, BridgeBase), "Python subtype is not an HL base instance");
        check(python.identity() == python, "native identity changed");
        check(native.compute(3) == 20, "Python override affected native instance");
        python = null;
        dynamicValue = null;
        bound = null;
        Sys.println("HLMOD_DEBUG before collect");
        collect();
        Sys.println("HLMOD_DEBUG after collect");
        afterCollection();
        Sys.println("BRIDGE_FIXTURE_OK");
    }
}
