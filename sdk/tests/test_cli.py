import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from hlmod_sdk import cli, registry


class RegistryBackedCliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.reg_path = Path(self.tmp.name) / "installs.json"
        self.game_dir = Path(self.tmp.name) / "game"
        self.game_dir.mkdir()
        self._patcher = patch("hlmod_sdk.registry.registry_path", return_value=self.reg_path)
        self._patcher.start()
        self.addCleanup(self._patcher.stop)

    def _seed(self, **installs):
        self.reg_path.write_text(json.dumps({"schema_version": 1, "installs": installs}), encoding="utf-8")

    def test_list_with_no_installs(self):
        out = io.StringIO()
        with redirect_stdout(out):
            code = cli.main(["list"])
        self.assertEqual(code, 1)
        self.assertIn("No hlmod installs", out.getvalue())

    def test_list_shows_registered_installs(self):
        self._seed(**{
            str(self.game_dir): {"mods_dir": str(self.game_dir / "mods"), "version": "abcdefg", "build_type": "Linux-gcc-Release", "installed_at": "2025-01-01T00:00:00+00:00"},
        })
        out = io.StringIO()
        with redirect_stdout(out):
            code = cli.main(["list"])
        self.assertEqual(code, 0)
        self.assertIn(str(self.game_dir), out.getvalue())
        self.assertIn("Linux-gcc-Release", out.getvalue())

    def test_new_with_single_install_auto_selects_it(self):
        self._seed(**{
            str(self.game_dir): {"mods_dir": str(self.game_dir / "mods"), "version": "abc", "build_type": "Linux-gcc-Release", "installed_at": "2025-01-01T00:00:00+00:00"},
        })
        output_dir = Path(self.tmp.name) / "my_mod"
        code = cli.main(["new", "my_mod", "--dir", str(output_dir)])
        self.assertEqual(code, 0)
        self.assertTrue((output_dir / "my_mod.py").exists())
        config = json.loads((output_dir / "pyrightconfig.json").read_text())
        self.assertEqual(config["extraPaths"], [str(self.game_dir / "mods")])

    def test_new_with_multiple_installs_requires_selection(self):
        self._seed(**{
            str(self.game_dir): {"mods_dir": str(self.game_dir / "mods"), "version": "abc", "build_type": "Linux-gcc-Release", "installed_at": "2025-01-01T00:00:00+00:00"},
            str(self.game_dir) + "2": {"mods_dir": str(self.game_dir) + "2/mods", "version": "def", "build_type": "Windows-mingw-Release", "installed_at": "2025-01-02T00:00:00+00:00"},
        })
        err = io.StringIO()
        with redirect_stderr(err):
            code = cli.main(["new", "my_mod", "--dir", str(Path(self.tmp.name) / "my_mod")])
        self.assertEqual(code, 1)
        self.assertIn("multiple hlmod installs", err.getvalue())

    def test_new_with_explicit_install_selection_by_index(self):
        other_dir = Path(self.tmp.name) / "other_game"
        self._seed(**{
            str(self.game_dir): {"mods_dir": str(self.game_dir / "mods"), "version": "abc", "build_type": "Linux-gcc-Release", "installed_at": "2025-01-02T00:00:00+00:00"},
            str(other_dir): {"mods_dir": str(other_dir / "mods"), "version": "def", "build_type": "Windows-mingw-Release", "installed_at": "2025-01-01T00:00:00+00:00"},
        })
        output_dir = Path(self.tmp.name) / "my_mod"
        # index 1 = newest by installed_at, which is self.game_dir
        code = cli.main(["new", "my_mod", "--install", "1", "--dir", str(output_dir)])
        self.assertEqual(code, 0)
        config = json.loads((output_dir / "pyrightconfig.json").read_text())
        self.assertEqual(config["extraPaths"], [str(self.game_dir / "mods")])

    def test_new_refuses_to_overwrite_existing_directory(self):
        self._seed(**{
            str(self.game_dir): {"mods_dir": str(self.game_dir / "mods"), "version": "abc", "build_type": "Linux-gcc-Release", "installed_at": "2025-01-01T00:00:00+00:00"},
        })
        output_dir = Path(self.tmp.name) / "existing"
        output_dir.mkdir()
        err = io.StringIO()
        with redirect_stderr(err):
            code = cli.main(["new", "my_mod", "--dir", str(output_dir)])
        self.assertEqual(code, 1)
        self.assertIn("already exists", err.getvalue())

    def test_new_with_unresolvable_install_selector_errors(self):
        self._seed(**{
            str(self.game_dir): {"mods_dir": str(self.game_dir / "mods"), "version": "abc", "build_type": "Linux-gcc-Release", "installed_at": "2025-01-01T00:00:00+00:00"},
        })
        err = io.StringIO()
        with redirect_stderr(err):
            code = cli.main(["new", "my_mod", "--install", "/nowhere", "--dir", str(Path(self.tmp.name) / "my_mod")])
        self.assertEqual(code, 1)
        self.assertIn("No registered install matches", err.getvalue())


class InstallCliTests(unittest.TestCase):
    def test_unknown_build_type_errors(self):
        err = io.StringIO()
        with tempfile.TemporaryDirectory() as d:
            with redirect_stderr(err):
                code = cli.main(["install", d, "--type", "not-a-real-type"])
        self.assertEqual(code, 1)
        self.assertIn("unknown build type", err.getvalue())

    def test_unknown_tweak_errors(self):
        err = io.StringIO()
        with tempfile.TemporaryDirectory() as d:
            with redirect_stderr(err):
                code = cli.main(["install", d, "--tweak", "not-a-real-tweak"])
        self.assertEqual(code, 1)
        self.assertIn("unknown tweak", err.getvalue())

    def test_install_error_from_core_logic_surfaces_as_cli_error(self):
        from hlmod_sdk.installer import InstallError
        err = io.StringIO()
        with tempfile.TemporaryDirectory() as d:
            with patch("hlmod_sdk.cli.install", side_effect=InstallError("network is down")):
                with redirect_stderr(err):
                    code = cli.main(["install", d])
        self.assertEqual(code, 1)
        self.assertIn("network is down", err.getvalue())


if __name__ == "__main__":
    unittest.main()
