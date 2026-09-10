import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import requests

from hlmod_sdk import installer


class RunSelectionTests(unittest.TestCase):
    def test_picks_first_successful_match_not_last(self):
        callbacks = installer.InstallCallbacks()
        fake_response = MagicMock()
        fake_response.raise_for_status = lambda: None
        fake_response.json.return_value = {
            "workflow_runs": [
                {"name": "Nightly Build", "conclusion": "success", "id": 999},  # newest
                {"name": "Nightly Build", "conclusion": "success", "id": 111},  # older re-run
            ]
        }
        with patch("hlmod_sdk.installer.requests.get", return_value=fake_response):
            _, run_id = installer.resolve_run_id("abc123", callbacks)
        self.assertEqual(run_id, 999)

    def test_no_successful_run_raises_install_error(self):
        callbacks = installer.InstallCallbacks()
        fake_response = MagicMock()
        fake_response.raise_for_status = lambda: None
        fake_response.json.return_value = {"workflow_runs": []}
        with patch("hlmod_sdk.installer.requests.get", return_value=fake_response):
            with self.assertRaises(installer.InstallError):
                installer.resolve_run_id("abc123", callbacks)

    def test_network_failure_raises_install_error(self):
        callbacks = installer.InstallCallbacks()
        bad_response = MagicMock()
        bad_response.raise_for_status.side_effect = requests.RequestException("boom")
        with patch("hlmod_sdk.installer.requests.get", return_value=bad_response):
            with self.assertRaises(installer.InstallError):
                installer.resolve_run_id("latest", callbacks)


class CancellationTests(unittest.TestCase):
    def test_check_cancelled_raises_install_cancelled(self):
        callbacks = installer.InstallCallbacks(should_cancel=lambda: True)
        with self.assertRaises(installer.InstallCancelled):
            callbacks.check_cancelled()

    def test_install_raises_cancelled_before_any_network_call(self):
        callbacks = installer.InstallCallbacks(should_cancel=lambda: True)
        with self.assertRaises(installer.InstallCancelled):
            installer.install("/tmp", "Linux-gcc-Release", callbacks=callbacks)


class DetectTweaksTests(unittest.TestCase):
    def test_sdl_detected_regardless_of_platform(self):
        with tempfile.TemporaryDirectory() as d:
            open(os.path.join(d, "sdl.hdll"), "w").close()
            tweaks = installer.detect_tweaks(d)
            self.assertIn(installer.Tweak.USE_EXISTING_SDL, tweaks)

    def test_no_hints_means_no_tweaks(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(installer.detect_tweaks(d), [])


class InstallFilesTests(unittest.TestCase):
    def _make_extract_dir(self, base: str) -> str:
        extract_dir = os.path.join(base, "hlmod")
        ex_mods = os.path.join(extract_dir, "mods")
        os.makedirs(ex_mods)
        for name in ("hl", "hl.bin"):
            open(os.path.join(extract_dir, name), "w").close()
        for name in ("hlobj.py", "hlobj.pyi", "hlvalues.py", "hlmod.pyi"):
            open(os.path.join(ex_mods, name), "w").close()
        os.makedirs(os.path.join(ex_mods, "modcore"))
        open(os.path.join(ex_mods, "modcore", "__init__.py"), "w").close()
        return extract_dir

    def test_preserves_pre_existing_user_mods(self):
        with tempfile.TemporaryDirectory() as d:
            mods_dir = os.path.join(d, "mods")
            os.makedirs(mods_dir)
            with open(os.path.join(mods_dir, "my_custom_mod.py"), "w") as f:
                f.write('MOD_INFO = {"id": "custom"}')
            extract_dir = self._make_extract_dir(d)

            installer.install_files(d, extract_dir, [])

            installed = sorted(os.listdir(mods_dir))
            self.assertIn("my_custom_mod.py", installed)
            for name in ("hlobj.py", "hlobj.pyi", "hlvalues.py", "hlmod.pyi", "modcore"):
                self.assertIn(name, installed)

    def test_reinstall_still_preserves_user_mods(self):
        with tempfile.TemporaryDirectory() as d:
            mods_dir = os.path.join(d, "mods")
            os.makedirs(mods_dir)
            with open(os.path.join(mods_dir, "my_custom_mod.py"), "w") as f:
                f.write('MOD_INFO = {"id": "custom"}')
            extract_dir = self._make_extract_dir(d)

            installer.install_files(d, extract_dir, [])
            installer.install_files(d, extract_dir, [])  # simulate an update

            self.assertIn("my_custom_mod.py", os.listdir(mods_dir))

    def test_no_base_mods_skips_framework_but_keeps_hlmod_pyi(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "mods"))
            extract_dir = self._make_extract_dir(d)

            installer.install_files(d, extract_dir, [installer.Tweak.NO_BASE_MODS])

            installed = set(os.listdir(os.path.join(d, "mods")))
            self.assertNotIn("hlobj.py", installed)
            self.assertNotIn("modcore", installed)
            self.assertIn("hlmod.pyi", installed)

    def test_writes_platform_launch_script(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "mods"))
            extract_dir = self._make_extract_dir(d)
            installer.install_files(d, extract_dir, [])
            if os.name == "posix":
                self.assertTrue(os.path.exists(os.path.join(d, "run_hlmod.sh")))
            else:
                self.assertTrue(os.path.exists(os.path.join(d, "run_hlmod.bat")))


class InstallEndToEndTests(unittest.TestCase):
    """Exercises `install()` with the network mocked, verifying the full
    pipeline wires callbacks/tweaks/registry recording together correctly."""

    def test_full_install_records_registry_entry(self):
        with tempfile.TemporaryDirectory() as d, tempfile.TemporaryDirectory() as reg_dir:
            reg_path = Path(reg_dir) / "installs.json"

            def fake_extract(zip_path, directory, callbacks):
                extract_dir = os.path.join(directory, "hlmod")
                ex_mods = os.path.join(extract_dir, "mods")
                os.makedirs(ex_mods)
                for name in ("hl", "hl.bin"):
                    open(os.path.join(extract_dir, name), "w").close()
                for name in ("hlobj.py", "hlobj.pyi", "hlvalues.py", "hlmod.pyi"):
                    open(os.path.join(ex_mods, name), "w").close()
                os.makedirs(os.path.join(ex_mods, "modcore"))
                open(os.path.join(ex_mods, "modcore", "__init__.py"), "w").close()
                return extract_dir

            with patch.object(installer, "resolve_run_id", return_value=("deadbeef", 123)), \
                 patch.object(installer, "download", return_value="/fake.zip"), \
                 patch.object(installer, "extract", side_effect=fake_extract), \
                 patch("hlmod_sdk.registry.registry_path", return_value=reg_path):
                installer.install(d, "Linux-gcc-Release", auto_detect=True)

            from hlmod_sdk.registry import list_installs
            installs = list_installs(reg_path)
            self.assertEqual(len(installs), 1)
            self.assertEqual(installs[0].version, "deadbeef")
            self.assertEqual(installs[0].build_type, "Linux-gcc-Release")


if __name__ == "__main__":
    unittest.main()
