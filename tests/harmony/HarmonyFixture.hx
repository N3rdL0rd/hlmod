@:keep
class Calculator {
    public static function add(a:Int, b:Int):Int {
        return a + b;
    }

    public static function multiply(a:Int, b:Int):Int {
        return a * b;
    }

    public var total:Int;

    public function new(start:Int) {
        total = start;
    }

    public function accumulate(delta:Int):Int {
        total += delta;
        return total;
    }

    public function chained(value:Int):Int {
        return value;
    }
}

@:keep
class HarmonyFixture {
    static function verify():Void {
        throw "harmony fixture controller did not run";
    }

    static function nativeTime():Float {
        return Sys.time();
    }

    static function main():Void {
        verify();
        Sys.println("HARMONY_FIXTURE_OK");
    }
}
