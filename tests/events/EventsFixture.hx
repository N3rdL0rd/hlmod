@:keep
class FixtureGame {
    public var ticks:Int;
    public function new() { ticks = 0; }
    public function update():Void { ticks++; }
}

@:keep
class EventsFixture {
    static function verify(game:FixtureGame):Void {
        throw "event fixture controller did not run";
    }

    static function caughtUpdate(game:FixtureGame):Bool {
        try { game.update(); } catch (error:Dynamic) { return true; }
        return false;
    }

    static function main():Void {
        var game = new FixtureGame();
        game.update();
        game.update();
        game.update();
        if (game.ticks != 3) throw "composed hooks repeated native execution";
        verify(game);
        Sys.println("EVENTS_FIXTURE_OK");
    }
}
