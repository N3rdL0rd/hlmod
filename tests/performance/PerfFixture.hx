@:keep
class PerfObject {
    public var value:Int;
    public function new(value:Int) { this.value = value; }
    public function compute(delta:Int):Int { return value + delta; }
}

@:keep
class PerfFixture {
    static function step(value:Int):Int { return value + 1; }
    static function pythonWork():Void {}
    static function loop(count:Int):Int {
        var total = 0;
        for (i in 0...count) total = step(total);
        return total;
    }
    static function main():Void {
        var iterations = 20000000;
        var start = Sys.cpuTime();
        var total = loop(iterations);
        var unhooked = Sys.cpuTime() - start;
        if (total != iterations) throw "invalid benchmark result";
        Sys.println("NATIVE_SECONDS=" + unhooked);
        Sys.println("NATIVE_NS_PER_CALL=" + (unhooked * 1e9 / iterations));
        pythonWork();
        var hookedIterations = 200000;
        start = Sys.cpuTime();
        loop(hookedIterations);
        var hooked = Sys.cpuTime() - start;
        Sys.println("HOOKED_NS_PER_CALL=" + (hooked * 1e9 / hookedIterations));
    }
}
