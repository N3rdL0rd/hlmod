@:keep
class DevLoopFixture {
    static function verify():Void {
        throw "devloop fixture controller did not run";
    }

    static function main():Void {
        verify();
    }
}
