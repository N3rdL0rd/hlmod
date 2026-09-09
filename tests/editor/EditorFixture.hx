@:keep
class BridgeBase {
    public var value:Int;
    public var peer:BridgeBase;
    public var values:hl.NativeArray<Int>;
    public static var total:Int = 1;

    public function new(value:Int) {
        this.value = value;
        this.values = new hl.NativeArray<Int>(1);
        this.values[0] = value;
    }

    public function compute(delta:Int):Int { return value + delta; }
    public dynamic function changeable(delta:Int):Int { return value + delta; }
    public function nullable(value:Null<Int>):Null<Int> { return value; }
    public function array():hl.NativeArray<Int> { return values; }
    public static function twice(value:Int):Int { return value * 2; }
}

@:keep
class BridgeChild extends BridgeBase {
    public function new(value:Int) { super(value); }
    override public function compute(delta:Int):Int { return super.compute(delta) * 2; }
}

@:keep
class EditorFixture {
    static function main():Void {
        var value = new BridgeChild(1);
        if (value.compute(1) != 4) throw "bad editor fixture";
        Sys.println("EDITOR_FIXTURE_OK");
    }
}
