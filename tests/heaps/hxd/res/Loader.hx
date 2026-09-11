package hxd.res;

import hxd.fs.FileSystem;

class Loader {
    public var fs: FileSystem;
    public function new(fs: FileSystem) {
        this.fs = fs;
    }
    public function load(path: String): haxe.io.Bytes {
        return fs.get(path).getBytes();
    }
}
