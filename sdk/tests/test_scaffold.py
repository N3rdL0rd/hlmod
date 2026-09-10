import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from hlmod_sdk.registry import Install
from hlmod_sdk.scaffold import scaffold, slugify


class SlugifyTests(unittest.TestCase):
    def test_replaces_invalid_characters(self):
        self.assertEqual(slugify("My Cool Mod!"), "My_Cool_Mod")

    def test_leading_digit_gets_prefixed(self):
        self.assertEqual(slugify("2fast"), "_2fast")

    def test_empty_result_raises(self):
        with self.assertRaises(ValueError):
            slugify("!!!")


class ScaffoldTests(unittest.TestCase):
    def setUp(self):
        self.install = Install(
            path="/games/mygame",
            mods_dir="/games/mygame/mods",
            version="abc123",
            build_type="Linux-gcc-Release",
            installed_at="2025-01-01T00:00:00+00:00",
        )

    def test_writes_expected_files(self):
        with tempfile.TemporaryDirectory() as d:
            output_dir = Path(d) / "my_mod"
            written = scaffold("My Mod", self.install, output_dir)
            names = {p.name for p in written}
            self.assertEqual(names, {"My_Mod.py", "pyrightconfig.json", "README.md"})
            for path in written:
                self.assertTrue(path.exists())

    def test_pyright_config_points_at_install_mods_dir(self):
        with tempfile.TemporaryDirectory() as d:
            output_dir = Path(d) / "my_mod"
            scaffold("my_mod", self.install, output_dir)
            config = json.loads((output_dir / "pyrightconfig.json").read_text())
            self.assertEqual(config["extraPaths"], ["/games/mygame/mods"])
            self.assertEqual(config["include"], ["my_mod.py"])

    def test_mod_source_declares_mod_info(self):
        with tempfile.TemporaryDirectory() as d:
            output_dir = Path(d) / "my_mod"
            scaffold("my_mod", self.install, output_dir)
            source = (output_dir / "my_mod.py").read_text()
            self.assertIn('MOD_INFO = {"id": "my_mod"', source)

    def test_readme_uses_windows_batch_launcher_for_windows_installs(self):
        windows_install = Install(
            path="C:/games/mygame", mods_dir="C:/games/mygame/mods",
            version="abc", build_type="Windows-mingw-Release", installed_at="2025-01-01T00:00:00+00:00",
        )
        with tempfile.TemporaryDirectory() as d:
            output_dir = Path(d) / "my_mod"
            scaffold("my_mod", windows_install, output_dir)
            readme = (output_dir / "README.md").read_text()
            self.assertIn("run_hlmod.bat", readme)
            self.assertNotIn("run_hlmod.sh", readme)

    def test_readme_embeds_resolved_output_directory_not_a_placeholder(self):
        with tempfile.TemporaryDirectory() as d:
            output_dir = Path(d) / "my_mod"
            scaffold("my_mod", self.install, output_dir)
            readme = (output_dir / "README.md").read_text()
            self.assertIn(str(output_dir.resolve()), readme)
            self.assertNotIn("{directory containing this README}", readme)

    def test_refuses_to_overwrite_an_existing_directory(self):
        with tempfile.TemporaryDirectory() as d:
            output_dir = Path(d) / "my_mod"
            output_dir.mkdir()
            with self.assertRaises(FileExistsError):
                scaffold("my_mod", self.install, output_dir)


if __name__ == "__main__":
    unittest.main()
