import hxd.Res;

class HeapsFixture {
    @:keep
    static function loadPath(path: String): String {
        return Res.loader.load(path).toString();
    }

    static function main() {
        Res.initLocal();
        trace(loadPath("title.txt"));
        trace("HEAPS_FIXTURE_OK");
    }
}
