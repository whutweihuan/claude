#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
图片拼接工具 - 图形界面版
运行: python stitch_gui.py   （Windows 下也可以双击 run_gui.bat）
"""

import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import stitch

IMAGE_TYPES = [
    ("图片文件", "*.jpg *.jpeg *.png *.bmp *.gif *.webp *.tif *.tiff"),
    ("所有文件", "*.*"),
]
SAVE_TYPES = [
    ("PNG 图片", "*.png"),
    ("JPEG 图片", "*.jpg"),
    ("WebP 图片", "*.webp"),
    ("BMP 图片", "*.bmp"),
    ("TIFF 图片", "*.tif"),
]
FIT_LABELS = {
    "保持原尺寸": "none",
    "统一到最大尺寸": "max",
    "统一到第一张": "first",
}
ALIGN_LABELS = {
    "居中": "center",
    "靠前": "start",
    "靠后": "end",
}


class StitchApp:
    def __init__(self, root):
        self.root = root
        self.root.title("图片拼接工具")
        self.root.geometry("860x660")
        self.root.minsize(740, 560)

        self.files = []
        self.queue = queue.Queue()
        self.busy = False

        self._build_ui()

    # ---------- 界面 ----------
    def _build_ui(self):
        outer = ttk.Frame(self.root, padding=12)
        outer.pack(fill="both", expand=True)

        # 图片列表
        list_frame = ttk.LabelFrame(outer, text="图片列表（按列表顺序拼接）", padding=8)
        list_frame.pack(fill="both", expand=True, pady=(0, 10))

        list_body = ttk.Frame(list_frame)
        list_body.pack(fill="both", expand=True)

        self.listbox = tk.Listbox(
            list_body, selectmode="extended", activestyle="dotbox",
            exportselection=False, height=10,
        )
        vsb = ttk.Scrollbar(list_body, orient="vertical", command=self.listbox.yview)
        hsb = ttk.Scrollbar(list_body, orient="horizontal", command=self.listbox.xview)
        self.listbox.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.listbox.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        list_body.rowconfigure(0, weight=1)
        list_body.columnconfigure(0, weight=1)

        buttons = ttk.Frame(list_frame)
        buttons.pack(fill="x", pady=(8, 0))
        ttk.Button(buttons, text="添加图片", command=self.add_files).pack(side="left")
        ttk.Button(buttons, text="添加文件夹", command=self.add_folder).pack(side="left", padx=(6, 0))
        ttk.Button(buttons, text="删除选中", command=self.remove_selected).pack(side="left", padx=(6, 0))
        ttk.Button(buttons, text="上移", command=lambda: self.move_selected(-1)).pack(side="left", padx=(18, 0))
        ttk.Button(buttons, text="下移", command=lambda: self.move_selected(1)).pack(side="left", padx=(6, 0))
        ttk.Button(buttons, text="清空", command=self.clear_all).pack(side="left", padx=(18, 0))
        self.count_var = tk.StringVar(value="共 0 张")
        ttk.Label(buttons, textvariable=self.count_var).pack(side="right")

        # 拼接设置
        opts = ttk.LabelFrame(outer, text="拼接设置", padding=10)
        opts.pack(fill="x", pady=(0, 10))
        opts.columnconfigure(1, weight=1)
        opts.columnconfigure(4, weight=1)

        ttk.Label(opts, text="拼接方向").grid(row=0, column=0, sticky="w", pady=4)
        direction = ttk.Frame(opts)
        direction.grid(row=0, column=1, columnspan=2, sticky="w")
        self.direction_var = tk.StringVar(value="horizontal")
        ttk.Radiobutton(direction, text="横排", value="horizontal",
                        variable=self.direction_var).pack(side="left")
        ttk.Radiobutton(direction, text="竖排", value="vertical",
                        variable=self.direction_var).pack(side="left", padx=(12, 0))

        ttk.Label(opts, text="间距(像素)").grid(row=0, column=3, sticky="w", pady=4)
        self.gap_var = tk.StringVar(value="0")
        ttk.Spinbox(opts, from_=0, to=1000, width=8,
                    textvariable=self.gap_var).grid(row=0, column=4, sticky="w")

        ttk.Label(opts, text="背景色").grid(row=1, column=0, sticky="w", pady=4)
        self.bg_var = tk.StringVar(value="#ffffff")
        self.bg_entry = ttk.Entry(opts, textvariable=self.bg_var, width=14)
        self.bg_entry.grid(row=1, column=1, sticky="w")
        self.transparent_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(opts, text="透明背景", variable=self.transparent_var,
                        command=self._toggle_bg).grid(row=1, column=2, sticky="w", padx=(8, 0))

        ttk.Label(opts, text="缩放方式").grid(row=1, column=3, sticky="w", pady=4)
        self.fit_var = tk.StringVar(value="保持原尺寸")
        ttk.Combobox(opts, textvariable=self.fit_var, state="readonly",
                     values=list(FIT_LABELS)).grid(row=1, column=4, sticky="w")

        ttk.Label(opts, text="对齐方式").grid(row=2, column=0, sticky="w", pady=4)
        self.align_var = tk.StringVar(value="居中")
        ttk.Combobox(opts, textvariable=self.align_var, state="readonly",
                     values=list(ALIGN_LABELS)).grid(row=2, column=1, sticky="w")

        ttk.Label(opts, text="质量(1-100)").grid(row=2, column=3, sticky="w", pady=4)
        self.quality_var = tk.StringVar(value="95")
        ttk.Spinbox(opts, from_=1, to=100, width=8,
                    textvariable=self.quality_var).grid(row=2, column=4, sticky="w")

        ttk.Label(opts, text="输出文件").grid(row=3, column=0, sticky="w", pady=(10, 0))
        self.output_var = tk.StringVar(value="")
        ttk.Entry(opts, textvariable=self.output_var).grid(
            row=3, column=1, columnspan=3, sticky="ew", pady=(10, 0))
        ttk.Button(opts, text="浏览...", command=self.browse_output).grid(
            row=3, column=4, sticky="e", padx=(8, 0), pady=(10, 0))

        # 底部
        bottom = ttk.Frame(outer)
        bottom.pack(fill="x")
        self.start_btn = ttk.Button(bottom, text="开始拼接", command=self.start)
        self.start_btn.pack(side="left")
        self.status_var = tk.StringVar(value="先添加图片，再点击「开始拼接」。")
        ttk.Label(bottom, textvariable=self.status_var).pack(
            side="left", padx=(12, 0), fill="x", expand=True)

    def _toggle_bg(self):
        state = "disabled" if self.transparent_var.get() else "normal"
        self.bg_entry.configure(state=state)

    # ---------- 列表操作 ----------
    def add_files(self):
        paths = filedialog.askopenfilenames(title="选择图片", filetypes=IMAGE_TYPES)
        for raw in paths:
            self._append(Path(raw))

    def add_folder(self):
        folder = filedialog.askdirectory(title="选择包含图片的文件夹")
        if not folder:
            return
        found = stitch.expand_inputs([folder], recursive=False)
        if not found:
            messagebox.showinfo("提示", "这个文件夹里没有找到支持的图片。")
            return
        for path in found:
            self._append(path)

    def _append(self, path):
        keys = {str(p.resolve()).lower() for p in self.files}
        if str(path.resolve()).lower() in keys:
            return
        self.files.append(path)
        self.listbox.insert(tk.END, str(path))
        if not self.output_var.get():
            self.output_var.set(str(path.parent / "stitched.png"))
        self._update_count()

    def remove_selected(self):
        selection = list(self.listbox.curselection())
        for index in reversed(selection):
            self.listbox.delete(index)
            del self.files[index]
        self._update_count()

    def move_selected(self, step):
        selection = list(self.listbox.curselection())
        if len(selection) != 1:
            messagebox.showinfo("提示", "请先选中一张图片再移动。")
            return
        index = selection[0]
        target = index + step
        if target < 0 or target >= len(self.files):
            return
        self.files[index], self.files[target] = self.files[target], self.files[index]
        text = self.listbox.get(index)
        self.listbox.delete(index)
        self.listbox.insert(target, text)
        self.listbox.selection_set(target)

    def clear_all(self):
        self.files.clear()
        self.listbox.delete(0, tk.END)
        self._update_count()

    def _update_count(self):
        self.count_var.set("共 %d 张" % len(self.files))

    def browse_output(self):
        current = self.output_var.get().strip()
        initial = Path(current) if current else Path("stitched.png")
        path = filedialog.asksaveasfilename(
            title="保存拼接结果",
            defaultextension=".png",
            initialfile=initial.name,
            initialdir=str(initial.parent) if str(initial.parent) not in ("", ".") else None,
            filetypes=SAVE_TYPES,
        )
        if path:
            self.output_var.set(path)

    # ---------- 拼接 ----------
    def start(self):
        if self.busy:
            return
        if not self.files:
            messagebox.showinfo("提示", "请先添加图片。")
            return

        try:
            gap = int(self.gap_var.get())
            if gap < 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("参数错误", "间距必须是不小于 0 的整数。")
            return

        try:
            quality = int(self.quality_var.get())
            if not 1 <= quality <= 100:
                raise ValueError
        except ValueError:
            messagebox.showerror("参数错误", "质量必须是 1-100 的整数。")
            return

        output_text = self.output_var.get().strip()
        if not output_text:
            messagebox.showinfo("提示", "请先选择输出文件。")
            return
        output = Path(output_text)
        if output.exists():
            if not messagebox.askyesno("确认覆盖", "文件已存在，是否覆盖？\n" + str(output)):
                return

        bg = "transparent" if self.transparent_var.get() else self.bg_var.get().strip()
        if not bg:
            messagebox.showerror("参数错误", "背景色不能为空。")
            return

        params = dict(
            files=list(self.files),
            output=output,
            direction=self.direction_var.get(),
            gap=gap,
            align=ALIGN_LABELS.get(self.align_var.get(), "center"),
            bg=bg,
            fit=FIT_LABELS.get(self.fit_var.get(), "none"),
            quality=quality,
        )

        self.busy = True
        self.start_btn.configure(state="disabled")
        self.status_var.set("正在拼接，请稍候...")
        threading.Thread(target=self._worker, args=(params,), daemon=True).start()
        self.root.after(100, self._poll)

    def _worker(self, params):
        try:
            count, size = stitch.stitch_to_file(**params)
            skipped = len(params["files"]) - count
            message = "完成: %d 张图片 -> %s (%d x %d)" % (
                count, params["output"], size[0], size[1])
            self.queue.put(("ok", message, skipped))
        except stitch.ToolError as exc:
            self.queue.put(("error", str(exc), 0))
        except Exception as exc:  # noqa: BLE001
            self.queue.put(("error", "发生未知错误: %s" % exc, 0))

    def _poll(self):
        try:
            kind, message, skipped = self.queue.get_nowait()
        except queue.Empty:
            self.root.after(100, self._poll)
            return

        self.busy = False
        self.start_btn.configure(state="normal")
        self.status_var.set(message)
        if kind == "ok":
            if skipped:
                messagebox.showwarning(
                    "完成（部分图片被跳过）",
                    message + "\n\n有 %d 张图片无法读取，已跳过。" % skipped)
            else:
                messagebox.showinfo("完成", message)
        else:
            messagebox.showerror("拼接失败", message)


def main():
    root = tk.Tk()
    style = ttk.Style()
    if "vista" in style.theme_names():
        style.theme_use("vista")
    StitchApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
