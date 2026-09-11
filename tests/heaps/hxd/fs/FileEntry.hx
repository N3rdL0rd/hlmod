package hxd.fs;

class FileEntry {
    public var path(default, null): String;
    public function new(path: String) {
        this.path = path;
    }
    public function getBytes(): haxe.io.Bytes {
        throw "not implemented";
    }
}
