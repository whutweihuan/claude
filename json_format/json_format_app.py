# -*- coding: utf-8 -*-
"""JSON 字符串格式化工具（Tkinter 界面）。

左输入右输出双栏；支持格式化、压缩、复制结果、清空；
非法 JSON 在底部状态栏提示出错行列，不破坏上次结果。
"""
import ctypes
import tkinter as tk
from tkinter import ttk

from json_tool import format_json


class JsonFormatApp:
    def __init__(self, root):
        self.root = root
        root.title("JSON 格式化工具")
        root.geometry("960x700")
        root.minsize(720, 420)

        # 顶部按钮栏：自然宽度排列，不用固定 width（DPI 放大后避免裁切）
        bar = ttk.Frame(root)
        bar.pack(side="top", fill="x", padx=8, pady=(8, 4))
        self.buttons = []
        for text, command in (
            ("格式化", self.do_format),
            ("压缩", self.do_minify),
            ("复制结果", self.do_copy),
            ("清空", self.do_clear),
        ):
            btn = ttk.Button(bar, text=text, command=command)
            btn.pack(side="left", padx=(0, 6))
            self.buttons.append(btn)

        # 中部双栏
        body = ttk.Frame(root)
        body.pack(side="top", fill="both", expand=True, padx=8, pady=4)
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(1, weight=1)

        ttk.Label(body, text="输入").grid(row=0, column=0, sticky="w")
        ttk.Label(body, text="结果").grid(row=0, column=1, sticky="w")

        self.input_text = self._make_text(body, 0)
        self.output_text = self._make_text(body, 1)
        self.output_text.configure(state="disabled")

        # 底部状态栏
        self.status_var = tk.StringVar(value="就绪")
        status = ttk.Label(root, textvariable=self.status_var, anchor="w")
        status.pack(side="bottom", fill="x", padx=8, pady=(2, 6))
        self.status_label = status

    def _make_text(self, parent, column):
        frame = ttk.Frame(parent)
        frame.grid(row=1, column=column, sticky="nsew", padx=(0, 4) if column == 0 else (4, 0))
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        text = tk.Text(frame, wrap="none")
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=text.yview)
        text.configure(yscrollcommand=scrollbar.set)
        text.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        return text

    # ---- 动作 ----

    def _run(self, indent):
        raw = self.input_text.get("1.0", "end-1c")
        ok, out, err = format_json(raw, indent=indent)
        if not ok:
            self.status_var.set("JSON 非法，" + err)
            return
        self._set_output(out)
        self.status_var.set("完成")

    def do_format(self):
        self._run(indent=2)

    def do_minify(self):
        self._run(indent=None)

    def do_copy(self):
        text = self.output_text.get("1.0", "end-1c")
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.status_var.set("已复制结果" if text else "结果区为空")

    def do_clear(self):
        self.input_text.delete("1.0", "end")
        self._set_output("")
        self.status_var.set("就绪")

    def _set_output(self, text):
        self.output_text.configure(state="normal")
        self.output_text.delete("1.0", "end")
        self.output_text.insert("1.0", text)
        self.output_text.configure(state="disabled")


def main():
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    root = tk.Tk()
    JsonFormatApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
