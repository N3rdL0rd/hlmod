class Benchmark {
    static var sink: Int = 0;

    static function work(x: Int): Int {
        return x * 2 + 1;
    }

    static function main() {
        final N = 1000000;

        var t0 = haxe.Timer.stamp();
        for (i in 0...N) {
            sink += work(i);
        }
        var elapsed = haxe.Timer.stamp() - t0;

        // Print in a machine-readable format: ns per call, plus sink to prevent DCE
        var ns_per_call = elapsed * 1e9 / N;
        Sys.println('BENCH_RESULT:${ns_per_call}|sink=${sink}');
    }
}
