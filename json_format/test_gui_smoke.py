# -*- coding: utf-8 -*-
"""GUI 冒烟测试：在子进程里开启与 main() 相同的 DPI 感知后实例化界面。

遵循仓库经验（.claude/CLAUDE.md）：应用开启 DPI 感知时，布局测试不能
在同一测试进程里直接创建 Tk，必须子进程先设置 DPI 再建窗口。
"""
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))

SCRIPT = """
import ctypes, os, sys
sys.path.insert(0, os.path.abspath(%(here)r))
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass
import tkinter as tk
from json_format_app import JsonFormatApp

root = tk.Tk()
app = JsonFormatApp(root)
root.update_idletasks()

# 1) 格式化：中文保持原样
app.input_text.insert("1.0", '{"名字":"张三","b":[1,2]}')
app.do_format()
out = app.output_text.get("1.0", "end-1c")
assert '"名字": "张三"' in out, out
assert "\\\\u" not in out, out

# 2) 压缩：单行
app.input_text.delete("1.0", "end")
app.input_text.insert("1.0", '{ "a" : 1 }')
app.do_minify()
out = app.output_text.get("1.0", "end-1c")
assert out == '{"a":1}', out

# 3) 非法 JSON：结果区不被破坏，状态栏报行列
app.input_text.delete("1.0", "end")
app.input_text.insert("1.0", '{"a": 1,,}')
app.do_format()
out = app.output_text.get("1.0", "end-1c")
assert out == '{"a":1}', out
status = app.status_var.get()
assert "第 1 行" in status, status

# 4) 清空
app.do_clear()
assert app.input_text.get("1.0", "end-1c") == ""
assert app.output_text.get("1.0", "end-1c") == ""

# 5) 布局：按钮文字在 DPI 放大后不被裁切（Python 3.8 无 winfo_font，用字体名测量）
import tkinter.font as tkfont
from tkinter import ttk
button_font = ttk.Style().lookup("TButton", "font")
font = tkfont.nametofont(button_font) if button_font else tkfont.nametofont("TkDefaultFont")
for btn in app.buttons:
    need = font.measure(btn["text"]) + 10
    assert need <= btn.winfo_reqwidth() + 1, (btn["text"], need, btn.winfo_reqwidth())

print("GUI_OK")
"""


class GuiSmokeTests(unittest.TestCase):
    def test_gui_flow_with_real_dpi_awareness(self):
        fd, path = tempfile.mkstemp(suffix=".py", text=True)
        code = SCRIPT % {"here": HERE}
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(code)
        try:
            proc = subprocess.run(
                [sys.executable, path],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=60,
            )
        finally:
            os.remove(path)
        output = proc.stdout.decode("utf-8", "replace")
        self.assertEqual(proc.returncode, 0, output)
        self.assertIn("GUI_OK", output)


if __name__ == "__main__":
    unittest.main()
