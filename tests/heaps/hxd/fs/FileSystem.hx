package hxd.fs;

// Mirrors the real Heaps hxd.fs.FileSystem interface shape closely enough to
// test hlmod's generic overlay against, without a runtime dependency on the
// real Heaps/fmt native libraries (fmt.hdll needs image/audio codec libs
// this CI environment can't always provide) - hlmod's overlay only ever
// touches this interface boundary, so the same mechanism works identically
// against the real classes.
interface FileSystem {
    function getRoot(): FileEntry;
    function get(path: String): FileEntry;
    function exists(path: String): Bool;
    function dispose(): Void;
}
