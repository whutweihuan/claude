#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GUI 冒烟测试。运行: python -m unittest test_gui_smoke -v"""

import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

try:
    import tkinter as tk
except ImportError:
    tk = None

from PIL import Image
import compress_gui


class GuiSmokeTests(unittest.TestCase):
    @unittest.skipIf(tk is None, "Tkinter 不可用")
    def test_window_builds_and_file_list_updates(self):
        try:
            root = tk.Tk()
        except tk.TclError:
            self.skipTest("当前环境没有图形显示")
        root.withdraw()
        try:
            app = compress_gui.CompressApp(root)
            with tempfile.TemporaryDirectory() as tmp:
                src = Path(tmp) / "a.jpg"
                Image.new("RGB", (20, 20), (1, 2, 3)).save(src, "JPEG")
                app._append(src)
                self.assertEqual(len(app.tree.get_children()), 1)
            root.update_idletasks()
        finally:
            root.destroy()

    @unittest.skipIf(tk is None, "Tkinter 不可用")
    def test_flow_reports_kept_original_and_missing_file(self):
        try:
            root = tk.Tk()
        except tk.TclError:
            self.skipTest("当前环境没有图形显示")
        root.withdraw()
        try:
            app = compress_gui.CompressApp(root)
            with tempfile.TemporaryDirectory() as tmp:
                tmp = Path(tmp)
                tiny = tmp / "tiny.jpg"
                Image.new("RGB", (16, 16), (128, 128, 128)).save(
                    tiny, "JPEG", quality=1, optimize=True)
                missing = tmp / "gone.jpg"
                app._append(tiny)
                app._append(missing)
                app.output_var.set(str(tmp / "out"))
                app.level_var.set("轻度")
                app.format_var.set("保持原格式")

                with mock.patch.object(compress_gui.messagebox, "showinfo"), \
                        mock.patch.object(compress_gui.messagebox, "showwarning"), \
                        mock.patch.object(compress_gui.messagebox, "showerror"):
                    app.start()
                    deadline = time.time() + 20
                    while app.busy and time.time() < deadline:
                        root.update()
                        time.sleep(0.05)
                    root.update()

                self.assertFalse(app.busy)
                tiny_item = app.path_items[app._path_key(tiny)]
                missing_item = app.path_items[app._path_key(missing)]
                self.assertIn("保留原图", app.tree.set(tiny_item, "status"))
                self.assertEqual(app.tree.set(missing_item, "status"), "失败")
                self.assertTrue((tmp / "out" / "tiny_compressed.jpg").exists())
        finally:
            root.destroy()


if __name__ == "__main__":
    unittest.main()
