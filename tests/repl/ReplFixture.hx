class ReplFixture {
    // Hooked by repl_mod.py so the REPL's `hooks` command has something
    // real to report; never called directly by this fixture.
    static function target(x: Int): Int {
        return x;
    }

    static function main() {
        target(1);
        // Long enough for a handful of sequential REPL round-trips to
        // complete after "REPL listening" prints, short enough to keep the
        // test fast and to bound how long a shutdown-hang regression could
        // make this test run before its own timeout catches it.
        Sys.sleep(5.0);
    }
}
