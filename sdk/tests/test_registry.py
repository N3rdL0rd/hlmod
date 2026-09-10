import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from hlmod_sdk import registry


class ConfigDirTests(unittest.TestCase):
    def test_linux_uses_xdg_config_home(self):
        env = {"XDG_CONFIG_HOME": "/custom/config"}
        self.assertEqual(registry.config_dir(env, "linux"), Path("/custom/config/hlmod"))

    def test_linux_falls_back_to_dot_config(self):
        self.assertEqual(registry.config_dir({}, "linux"), Path.home() / ".config" / "hlmod")

    def test_windows_uses_appdata(self):
        env = {"APPDATA": "C:/Users/nerd/AppData/Roaming"}
        self.assertEqual(registry.config_dir(env, "win32"), Path("C:/Users/nerd/AppData/Roaming/hlmod"))

    def test_macos_uses_application_support(self):
        self.assertEqual(registry.config_dir({}, "darwin"), Path.home() / "Library" / "Application Support" / "hlmod")


class RecordInstallTests(unittest.TestCase):
    def test_round_trips_through_list_installs(self):
        with tempfile.TemporaryDirectory() as d:
            reg_path = Path(d) / "installs.json"
            with tempfile.TemporaryDirectory() as game_dir:
                registry.record_install(game_dir, version="abc123", build_type="Linux-gcc-Release", path=reg_path)
                installs = registry.list_installs(reg_path)
                self.assertEqual(len(installs), 1)
                self.assertEqual(installs[0].path, str(Path(game_dir).resolve()))
                self.assertEqual(installs[0].mods_dir, str(Path(game_dir).resolve() / "mods"))
                self.assertEqual(installs[0].version, "abc123")
                self.assertEqual(installs[0].build_type, "Linux-gcc-Release")

    def test_updating_an_existing_install_overwrites_its_entry(self):
        with tempfile.TemporaryDirectory() as d:
            reg_path = Path(d) / "installs.json"
            with tempfile.TemporaryDirectory() as game_dir:
                registry.record_install(game_dir, version="old", build_type="Linux-gcc-Release", path=reg_path)
                registry.record_install(game_dir, version="new", build_type="Linux-clang-Debug", path=reg_path)
                installs = registry.list_installs(reg_path)
                self.assertEqual(len(installs), 1)
                self.assertEqual(installs[0].version, "new")
                self.assertEqual(installs[0].build_type, "Linux-clang-Debug")

    def test_two_different_installs_both_persist(self):
        with tempfile.TemporaryDirectory() as d:
            reg_path = Path(d) / "installs.json"
            with tempfile.TemporaryDirectory() as game_a, tempfile.TemporaryDirectory() as game_b:
                registry.record_install(game_a, version="a", build_type="Linux-gcc-Release", path=reg_path)
                registry.record_install(game_b, version="b", build_type="Windows-mingw-Release", path=reg_path)
                installs = registry.list_installs(reg_path)
                self.assertEqual({i.path for i in installs}, {str(Path(game_a).resolve()), str(Path(game_b).resolve())})


class ListInstallsTests(unittest.TestCase):
    def test_missing_registry_returns_empty(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(registry.list_installs(Path(d) / "nope.json"), [])

    def test_corrupt_registry_returns_empty(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "installs.json"
            path.write_text("not json", encoding="utf-8")
            self.assertEqual(registry.list_installs(path), [])

    def test_parses_entries_and_sorts_newest_first(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "installs.json"
            path.write_text(json.dumps({
                "schema_version": 1,
                "installs": {
                    "/games/old": {"mods_dir": "/games/old/mods", "version": "aaa", "build_type": "Linux-gcc-Release", "installed_at": "2020-01-01T00:00:00+00:00"},
                    "/games/new": {"mods_dir": "/games/new/mods", "version": "bbb", "build_type": "Windows-mingw-Release", "installed_at": "2025-01-01T00:00:00+00:00"},
                },
            }), encoding="utf-8")
            installs = registry.list_installs(path)
            self.assertEqual([i.path for i in installs], ["/games/new", "/games/old"])


class FindInstallTests(unittest.TestCase):
    def setUp(self):
        self.installs = [
            registry.Install("/games/alpha", "/games/alpha/mods", "aaa", "Linux-gcc-Release", "2025-01-01T00:00:00+00:00"),
            registry.Install("/games/beta", "/games/beta/mods", "bbb", "Windows-mingw-Release", "2025-01-02T00:00:00+00:00"),
        ]

    def test_by_index(self):
        self.assertIs(registry.find_install("2", self.installs), self.installs[1])

    def test_by_exact_path(self):
        self.assertIs(registry.find_install("/games/alpha", self.installs), self.installs[0])

    def test_by_unique_substring(self):
        self.assertIs(registry.find_install("beta", self.installs), self.installs[1])

    def test_index_out_of_range_raises(self):
        with self.assertRaises(LookupError):
            registry.find_install("99", self.installs)

    def test_ambiguous_substring_raises(self):
        with self.assertRaises(LookupError):
            registry.find_install("games", self.installs)

    def test_no_match_raises(self):
        with self.assertRaises(LookupError):
            registry.find_install("nowhere", self.installs)

    def test_empty_registry_raises(self):
        with self.assertRaises(LookupError):
            registry.find_install("1", [])


if __name__ == "__main__":
    unittest.main()
