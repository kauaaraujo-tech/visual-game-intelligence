"""Exercise the release gate against disposable real files, never real credentials."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_release.py"


class ReleaseGateTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.write("README.md", "# VGI\nSynthetic test project.\n")

    def write(self, name, content):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content if isinstance(content, bytes) else content.encode("utf-8"))
        return path

    def run_gate(self, *extra):
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--root", str(self.root), *extra],
            capture_output=True, text=True, encoding="utf-8",
        )

    def assert_rejected(self, code):
        result = self.run_gate("--all-files")
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn(code, result.stdout)
        self.assertNotIn("Traceback", result.stderr)
        return result

    def test_clean_source_and_placeholder_paths_pass(self):
        self.write("urd/core.py", "value = 1\n")
        self.write("docs/setup.md", "Use C:/Users/<USER>/Games or %USERPROFILE%.\n")
        result = self.run_gate("--all-files")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_synthetic_csv_and_ppm_with_manifest_pass(self):
        self.write("examples/SYNTHETIC-demo/session.json", json.dumps({"synthetic": True}))
        self.write("examples/SYNTHETIC-demo/frames.csv", "frame,frametime_ms\n1,16\n")
        self.write("examples/SYNTHETIC-demo/image.ppm", b"P6\n1 1\n255\n\x00\xff\x00")
        result = self.run_gate("--all-files")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_synthetic_label_does_not_replace_manifest_declaration(self):
        self.write("examples/SYNTHETIC-demo/session.json", '{"synthetic": false}')
        self.write("examples/SYNTHETIC-demo/frames.csv", "frame,ms\n1,16\n")
        self.assert_rejected("example-not-synthetic")

    def test_ppm_needs_a_synthetic_session_or_report(self):
        self.write("examples/SYNTHETIC-demo/image.ppm", b"P6\n1 1\n255\n\0\0\0")
        self.assert_rejected("unmarked-example-data")

    def test_proprietary_and_executable_extensions_are_rejected(self):
        for filename in ("game.rom", "game.iso", "dump.bin", "tool.exe", "capture.png", "archive.zip"):
            with self.subTest(filename=filename):
                path = self.write("examples/" + filename, b"not public source")
                self.assert_rejected("unapproved-file-type")
                path.unlink()

    def test_text_extension_does_not_hide_binary_content(self):
        self.write("docs/notes.md", b"private\x00dump")
        self.assert_rejected("non-text-content")

    def test_concrete_windows_user_paths_are_rejected_without_echoing_content(self):
        for separator in ("/", "\\", "\\\\"):
            with self.subTest(separator=separator):
                private_path = separator.join(("C:", "Users", "private-person", "Games"))
                self.write("docs/setup.md", private_path)
                result = self.assert_rejected("personal-windows-path")
                self.assertNotIn("private-person", result.stdout)

    def test_recognizable_credentials_are_rejected_and_redacted(self):
        samples = (
            "ghp_" + "A" * 36,
            "AKIA" + "A" * 16,
            "-----BEGIN " + "RSA PRIVATE KEY-----",
            "sk-proj-" + "a" * 40,
            'api_key = "' + "a1b2c3d4" * 5 + '"',
        )
        for sample in samples:
            with self.subTest(prefix=sample[:4]):
                self.write("docs/notes.md", sample)
                result = self.assert_rejected("credential-pattern")
                self.assertNotIn(sample, result.stdout)

    def test_dotenv_is_rejected_even_if_text(self):
        self.write(".env", "DEBUG=true\n")
        self.assert_rejected("unapproved-path")

    def test_local_output_and_git_metadata_are_excluded_from_tree_mode(self):
        self.write(".git/private", b"\x00private")
        self.write("output/game.iso", b"private")
        self.write("local-sessions/raw.log", b"private")
        self.write("urd/__pycache__/core.pyc", b"\x00cache")
        result = self.run_gate("--all-files")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    @unittest.skipUnless(shutil.which("git"), "Git needed for tracked-file selection")
    def test_default_scans_tracked_files_and_ignores_untracked_notes(self):
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        subprocess.run(["git", "-C", str(self.root), "add", "README.md"], check=True)
        self.write("private-notes.txt", "not part of release")
        result = self.run_gate()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.write("docs/leak.md", "ghp_" + "A" * 36)
        subprocess.run(["git", "-C", str(self.root), "add", "docs/leak.md"], check=True)
        result = self.run_gate()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("credential-pattern", result.stdout)

    def test_default_fails_closed_without_a_git_checkout(self):
        result = self.run_gate()
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("--all-files", result.stderr)

    def test_missing_root_fails_without_traceback(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--root", str(self.root / "missing"), "--all-files"],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_symlink_is_rejected_without_reading_target(self):
        target = self.write("outside.txt", "private")
        link = self.root / "docs" / "linked.md"
        link.parent.mkdir()
        try:
            link.symlink_to(target)
        except OSError:
            self.skipTest("Symlinks unavailable")
        target.unlink()
        self.assert_rejected("symlink")
