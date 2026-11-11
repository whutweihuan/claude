import os
import tempfile
import unittest
from pathlib import Path

import share_core as core


class SanitizeFilenameTests(unittest.TestCase):
    def test_keeps_chinese_space_and_emoji(self):
        self.assertEqual(core.sanitize_filename("🎬 视频 片段.mp4"), "🎬 视频 片段.mp4")

    def test_strips_directories(self):
        self.assertEqual(core.sanitize_filename("../../etc/passwd"), "passwd")
        self.assertEqual(core.sanitize_filename(r"C:\temp\a.mp4"), "a.mp4")

    def test_removes_windows_forbidden_chars(self):
        self.assertEqual(core.sanitize_filename('a<b>c:d"e|f?g*h.txt'), "abcdefgh.txt")

    def test_reserved_device_name_gets_prefix(self):
        self.assertEqual(core.sanitize_filename("CON.txt"), "file-CON.txt")
        self.assertEqual(core.sanitize_filename("lpt1"), "file-lpt1")

    def test_empty_or_dots_becomes_file(self):
        self.assertEqual(core.sanitize_filename("   ..."), "file")

    def test_truncates_to_200_chars_keeping_suffix(self):
        result = core.sanitize_filename("a" * 300 + ".txt")
        self.assertLessEqual(len(result), 200)
        self.assertTrue(result.endswith(".txt"))


class ResolveSharedPathTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "sub").mkdir()
        (self.root / "sub" / "a.txt").write_text("x", encoding="utf-8")

    def tearDown(self):
        self._tmp.cleanup()

    def test_accepts_nested_relative_path(self):
        got = core.resolve_shared_path(self.root, "sub/a.txt")
        self.assertEqual(got, (self.root / "sub" / "a.txt").resolve())

    def test_accepts_backslash_separator(self):
        self.assertEqual(core.resolve_shared_path(self.root, r"sub\a.txt").name, "a.txt")

    def test_rejects_parent_traversal(self):
        with self.assertRaises(core.UnsafePath):
            core.resolve_shared_path(self.root, "../../secret.txt")

    def test_rejects_absolute_and_drive_paths(self):
        for bad in ("/etc/passwd", r"C:\Windows\win.ini", "C:relative"):
            with self.subTest(bad=bad):
                with self.assertRaises(core.UnsafePath):
                    core.resolve_shared_path(self.root, bad)

    def test_rejects_null_byte(self):
        with self.assertRaises(core.UnsafePath):
            core.resolve_shared_path(self.root, "a\x00b")

    @unittest.skipIf(os.name == "nt", "Windows 创建符号链接需要额外权限")
    def test_rejects_symlink_escape(self):
        with tempfile.TemporaryDirectory() as outside:
            os.symlink(outside, str(self.root / "link"))
            with self.assertRaises(core.UnsafePath):
                core.resolve_shared_path(self.root, "link/secret.txt")
