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


class RangeTests(unittest.TestCase):
    def test_no_header_returns_none(self):
        self.assertIsNone(core.parse_range(None, 100))

    def test_closed_range(self):
        self.assertEqual(core.parse_range("bytes=10-19", 100), (10, 19))

    def test_open_ended_and_suffix(self):
        self.assertEqual(core.parse_range("bytes=90-", 100), (90, 99))
        self.assertEqual(core.parse_range("bytes=-10", 100), (90, 99))

    def test_clamps_end_to_size(self):
        self.assertEqual(core.parse_range("bytes=90-200", 100), (90, 99))

    def test_unsatisfiable_or_invalid(self):
        for header in ("bytes=100-", "bytes=200-300", "bytes=5-2", "bytes=0-1,3-4", "items=0-1"):
            with self.subTest(header=header):
                with self.assertRaises(core.RangeNotSatisfiable) as ctx:
                    core.parse_range(header, 100)
                self.assertEqual(ctx.exception.size, 100)

    def test_zero_size_file_has_no_valid_range(self):
        with self.assertRaises(core.RangeNotSatisfiable):
            core.parse_range("bytes=0-", 0)


class ListFilesTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "sub").mkdir()
        (self.root / "a.txt").write_text("abc", encoding="utf-8")
        (self.root / "sub" / "b.mp4").write_bytes(b"x" * 10)
        (self.root / ".hidden").write_text("no", encoding="utf-8")
        (self.root / "~$temp.docx").write_text("no", encoding="utf-8")
        (self.root / ".sharefile-tmp").mkdir()
        (self.root / ".sharefile-tmp" / "upload-1.part").write_bytes(b"x")

    def tearDown(self):
        self._tmp.cleanup()

    def test_returns_relative_posix_paths_and_metadata(self):
        files = core.iter_files(self.root)
        self.assertEqual([f["path"] for f in files], ["a.txt", "sub/b.mp4"])
        self.assertEqual(files[0]["size"], 3)
        self.assertEqual(files[0]["name"], "a.txt")
        self.assertIsInstance(files[0]["mtime"], int)

    def test_sorted_case_insensitively(self):
        (self.root / "B.txt").write_text("b", encoding="utf-8")
        paths = [f["path"] for f in core.iter_files(self.root)]
        self.assertEqual(paths, ["a.txt", "B.txt", "sub/b.mp4"])


class NameAndSizeTests(unittest.TestCase):
    def test_numbered_name(self):
        self.assertEqual(core.numbered_name("a.txt", 0), "a.txt")
        self.assertEqual(core.numbered_name("a.txt", 1), "a (1).txt")
        self.assertEqual(core.numbered_name("archive.tar.gz", 2), "archive.tar (2).gz")

    def test_format_size(self):
        self.assertEqual(core.format_size(0), "0 B")
        self.assertEqual(core.format_size(1536), "1.5 KB")
        self.assertEqual(core.format_size(5 * 1024 * 1024), "5.0 MB")
