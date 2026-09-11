package hxd;

// Mirrors real Heaps' hxd.Res: a static holder exposing exactly the three
// init entry points hlmod's `mods/heaps` overlay hooks by name.
class Res {
    public static var loader: hxd.res.Loader;

    public static function initLocal(): Void {
        loader = new hxd.res.Loader(new hxd.fs.GameFileSystem());
    }

    public static function initEmbed(): Void {
        loader = new hxd.res.Loader(new hxd.fs.GameFileSystem());
    }

    public static function initPak(): Void {
        loader = new hxd.res.Loader(new hxd.fs.GameFileSystem());
    }
}
