package hxd.fs;

class GameFileEntry extends FileEntry {
    var content: String;
    public function new(path: String, content: String) {
        super(path);
        this.content = content;
    }
    public override function getBytes(): haxe.io.Bytes {
        return haxe.io.Bytes.ofString(content);
    }
}
