package hxd.fs;

// The "base game" filesystem: a fixed, hardcoded set of built-in resources,
// standing in for a real EmbedFileSystem/LocalFileSystem/pak FileSystem -
// hlmod's overlay must not care which concrete class this is.
class GameFileSystem implements FileSystem {
    public function new() {}
    public function getRoot(): FileEntry {
        return new GameFileEntry("", "");
    }
    public function get(path: String): FileEntry {
        return switch (path) {
            case "title.txt": new GameFileEntry(path, "Base Game Title");
            case "credits.txt": new GameFileEntry(path, "Base Game Credits");
            default: throw "File not found: " + path;
        }
    }
    public function exists(path: String): Bool {
        return path == "title.txt" || path == "credits.txt";
    }
    public function dispose(): Void {}
}
