#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""图片压缩工具 - 图形界面版。运行: python compress_gui.py"""

import os
import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import compress

IMAGE_TYPES = [
    ("图片文件", "*.jpg *.jpeg *.png *.bmp *.gif *.webp *.tif *.tiff *.heic *.heif"),
    ("所有文件", "*.*"),
]
LEVEL_LABELS = {
    "轻度": "light",
    "标准": "standard",
    "强力": "strong",
    "极限": "extreme",
}
FORMAT_LABELS = {
    "保持原格式": "keep",
    "JPG": "jpg",
    "WebP": "webp",
    "PNG": "png",
}


def _format_size(size):
    value = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            if unit == "B":
                return "%d B" % value
            return "%.1f %s" % (value, unit)
        value /= 1024.0


class CompressApp:
    def __init__(self, root):
        self.root = root
        self.root.title("图片压缩工具")
        self.root.geometry("940x700")
        self.root.minsize(800, 580)

        self.files = []
        self.item_paths = {}
        self.path_items = {}
        self.queue = queue.Queue()
        self.busy = False

        self._build_ui()

    # ---------- 界面 ----------
    def _build_ui(self):
        outer = ttk.Frame(self.root, padding=12)
        outer.pack(fill="both", expand=True)

        list_frame = ttk.LabelFrame(outer, text="图片列表", padding=8)
        list_frame.pack(fill="both", expand=True, pady=(0, 10))

        list_body = ttk.Frame(list_frame)
        list_body.pack(fill="both", expand=True)

        columns = ("original", "result", "status")
        self.tree = ttk.Treeview(
            list_body, columns=columns, show="tree headings", selectmode="extended")
        self.tree.heading("#0", text="文件")
        self.tree.heading("original", text="原始大小")
        self.tree.heading("result", text="压缩后")
        self.tree.heading("status", text="状态")
        self.tree.column("#0", width=520, minwidth=260, anchor="w")
        self.tree.column("original", width=100, minwidth=80, anchor="e")
        self.tree.column("result", width=100, minwidth=80, anchor="e")
        self.tree.column("status", width=220, minwidth=100, anchor="w")
        vsb = ttk.Scrollbar(list_body, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(list_body, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        list_body.rowconfigure(0, weight=1)
        list_body.columnconfigure(0, weight=1)

        buttons = ttk.Frame(list_frame)
        buttons.pack(fill="x", pady=(8, 0))
        ttk.Button(buttons, text="添加图片", command=self.add_files).pack(side="left")
        ttk.Button(buttons, text="添加文件夹", command=self.add_folder).pack(
            side="left", padx=(6, 0))
        self.recursive_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            buttons, text="包含子文件夹", variable=self.recursive_var,
        ).pack(side="left", padx=(6, 0))
        ttk.Button(buttons, text="删除选中", command=self.remove_selected).pack(
            side="left", padx=(18, 0))
        ttk.Button(buttons, text="清空", command=self.clear_all).pack(
            side="left", padx=(6, 0))
        self.count_var = tk.StringVar(value="共 0 张")
        ttk.Label(buttons, textvariable=self.count_var).pack(side="right")

        opts = ttk.LabelFrame(outer, text="压缩设置", padding=10)
        opts.pack(fill="x", pady=(0, 10))
        opts.columnconfigure(1, weight=1)
        opts.columnconfigure(4, weight=1)

        ttk.Label(opts, text="压缩档位").grid(row=0, column=0, sticky="w", pady=4)
        self.level_var = tk.StringVar(value="标准")
        ttk.Combobox(
            opts, textvariable=self.level_var, state="readonly",
            values=list(LEVEL_LABELS), width=12,
        ).grid(row=0, column=1, sticky="w")
        ttk.Label(
            opts, text="轻度画质优先，极限体积优先",
            foreground="#666666",
        ).grid(row=0, column=2, columnspan=3, sticky="w", padx=(10, 0))

        ttk.Label(opts, text="输出格式").grid(row=0, column=3, sticky="e", pady=4)
        self.format_var = tk.StringVar(value="保持原格式")
        ttk.Combobox(
            opts, textvariable=self.format_var, state="readonly",
            values=list(FORMAT_LABELS), width=12,
        ).grid(row=0, column=4, sticky="w", padx=(8, 0))

        ttk.Label(opts, text="尺寸调整").grid(row=1, column=0, sticky="w", pady=4)
        edge_frame = ttk.Frame(opts)
        edge_frame.grid(row=1, column=1, columnspan=2, sticky="w")
        self.limit_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            edge_frame, text="限制长边", variable=self.limit_var,
            command=self._toggle_max_edge,
        ).pack(side="left")
        self.max_edge_var = tk.StringVar(value="1920")
        self.max_edge_spin = ttk.Spinbox(
            edge_frame, from_=1, to=100000, width=8, textvariable=self.max_edge_var,
            state="disabled",
        )
        self.max_edge_spin.pack(side="left", padx=(8, 4))
        ttk.Label(edge_frame, text="像素（只缩小不放大）").pack(side="left")

        ttk.Label(opts, text="输出文件夹").grid(
            row=2, column=0, sticky="w", pady=(10, 0))
        self.output_var = tk.StringVar(value="")
        ttk.Entry(opts, textvariable=self.output_var).grid(
            row=2, column=1, columnspan=3, sticky="ew", pady=(10, 0))
        ttk.Button(opts, text="浏览...", command=self.browse_output).grid(
            row=2, column=4, sticky="e", padx=(8, 0), pady=(10, 0))
        ttk.Label(
            opts, text="原图不会被覆盖；输出文件自动加 _compressed 后缀。",
            foreground="#666666",
        ).grid(row=3, column=0, columnspan=5, sticky="w", pady=(8, 0))

        bottom = ttk.Frame(outer)
        bottom.pack(fill="x")
        self.start_btn = ttk.Button(bottom, text="开始压缩", command=self.start)
        self.start_btn.pack(side="left")
        self.progress = ttk.Progressbar(bottom, mode="determinate", length=220)
        self.progress.pack(side="left", padx=(12, 0))
        self.status_var = tk.StringVar(value="先添加图片，再点击「开始压缩」。")
        ttk.Label(bottom, textvariable=self.status_var).pack(
            side="left", padx=(12, 0), fill="x", expand=True)

    def _toggle_max_edge(self):
        self.max_edge_spin.configure(
            state="normal" if self.limit_var.get() else "disabled")

    # ---------- 列表操作 ----------
    @staticmethod
    def _path_key(path):
        return os.path.normcase(str(Path(path).resolve()))

    def add_files(self):
        paths = filedialog.askopenfilenames(title="选择图片", filetypes=IMAGE_TYPES)
        for raw in paths:
            self._append(Path(raw))

    def add_folder(self):
        folder = filedialog.askdirectory(title="选择包含图片的文件夹")
        if not folder:
            return
        try:
            found = compress.expand_inputs(
                [folder], recursive=self.recursive_var.get())
        except compress.ToolError as exc:
            messagebox.showerror("无法读取文件夹", str(exc))
            return
        if not found:
            messagebox.showinfo("提示", "这个文件夹里没有找到支持的图片。")
            return
        for path in found:
            self._append(path)

    def _append(self, path):
        path = Path(path)
        key = self._path_key(path)
        if key in self.path_items:
            return
        try:
            size = path.stat().st_size
        except OSError:
            size = 0
        item = self.tree.insert(
            "", "end", text=str(path),
            values=(_format_size(size), "", "等待"),
        )
        self.files.append(path)
        self.item_paths[item] = path
        self.path_items[key] = item
        if not self.output_var.get():
            self.output_var.set(str(path.parent / "compressed"))
        self._update_count()

    def remove_selected(self):
        selection = list(self.tree.selection())
        for item in selection:
            path = self.item_paths.pop(item, None)
            if path is not None:
                self.path_items.pop(self._path_key(path), None)
                self.files = [p for p in self.files if p is not path]
            self.tree.delete(item)
        self._update_count()

    def clear_all(self):
        self.files.clear()
        self.item_paths.clear()
        self.path_items.clear()
        self.tree.delete(*self.tree.get_children())
        self._update_count()

    def _update_count(self):
        self.count_var.set("共 %d 张" % len(self.files))

    def browse_output(self):
        current = self.output_var.get().strip()
        initial = current if current else str(Path.cwd())
        path = filedialog.askdirectory(title="选择输出文件夹", initialdir=initial)
        if path:
            self.output_var.set(path)

    # ---------- 压缩 ----------
    def start(self):
        if self.busy:
            return
        if not self.files:
            messagebox.showinfo("提示", "请先添加图片。")
            return

        output_text = self.output_var.get().strip()
        if not output_text:
            messagebox.showinfo("提示", "请先选择输出文件夹。")
            return

        max_edge = None
        if self.limit_var.get():
            try:
                max_edge = int(self.max_edge_var.get())
                if max_edge <= 0:
                    raise ValueError
            except ValueError:
                messagebox.showerror("参数错误", "长边必须是正整数。")
                return

        level = LEVEL_LABELS.get(self.level_var.get(), "standard")
        output_format = FORMAT_LABELS.get(self.format_var.get(), "keep")

        for item in self.tree.get_children():
            path = self.item_paths[item]
            try:
                original = _format_size(path.stat().st_size)
            except OSError:
                original = "0 B"
            self.tree.item(item, values=(original, "", "等待"))

        self.busy = True
        self.start_btn.configure(state="disabled")
        self.progress.configure(maximum=len(self.files), value=0)
        self.status_var.set("正在压缩，请稍候...")

        params = dict(
            inputs=[str(p) for p in self.files],
            output_dir=Path(output_text),
            level=level,
            output_format=output_format,
            max_edge=max_edge,
        )
        threading.Thread(target=self._worker, args=(params,), daemon=True).start()
        self.root.after(100, self._poll)

    def _worker(self, params):
        def progress(done, total, source):
            self.queue.put(("progress", done, total, str(source)))

        try:
            summary = compress.compress_files(progress=progress, **params)
            self.queue.put(("done", summary))
        except compress.ToolError as exc:
            self.queue.put(("error", str(exc)))
        except Exception as exc:  # noqa: BLE001
            self.queue.put(("error", "发生未知错误: %s" % exc))

    def _poll(self):
        while True:
            try:
                message = self.queue.get_nowait()
            except queue.Empty:
                break
            kind = message[0]
            if kind == "progress":
                _, done, total, source = message
                self.progress.configure(value=done)
                item = self.path_items.get(self._path_key(source))
                if item:
                    self.tree.set(item, "status", "处理中")
                self.status_var.set(
                    "正在处理 (%d/%d): %s" % (done + 1, total, Path(source).name))
            elif kind == "done":
                self._finish(message[1])
            elif kind == "error":
                self.busy = False
                self.start_btn.configure(state="normal")
                self.status_var.set("压缩失败。")
                messagebox.showerror("压缩失败", message[1])

        if self.busy:
            self.root.after(100, self._poll)

    def _finish(self, summary):
        self.busy = False
        self.start_btn.configure(state="normal")
        self.progress.configure(value=len(self.files))

        results = {
            self.path_items[self._path_key(r.source)]: r
            for r in summary.results
            if self._path_key(r.source) in self.path_items
        }
        skipped = {
            self.path_items[self._path_key(path)]: reason
            for path, reason in summary.skipped
            if self._path_key(path) in self.path_items
        }
        failures = {
            self.path_items[self._path_key(path)]: reason
            for path, reason in summary.failures
            if self._path_key(path) in self.path_items
        }

        for item, path in self.item_paths.items():
            try:
                original = _format_size(path.stat().st_size)
            except OSError:
                original = "0 B"
            if item in results:
                result = results[item]
                status = result.note or ("保留原图" if result.kept_original else "完成")
                self.tree.item(item, values=(
                    original, _format_size(result.output_size), status))
            elif item in skipped:
                self.tree.item(item, values=(original, "", "跳过"))
            elif item in failures:
                self.tree.item(item, values=(original, "", "失败"))

        message = "成功 %d 张，跳过 %d 张，失败 %d 张。" % (
            len(summary.results), len(summary.skipped), len(summary.failures))
        if summary.total_original:
            change = 100.0 * (1.0 - summary.total_output / summary.total_original)
            volume = ("节省 %.1f%%" % change if change >= 0
                      else "增加 %.1f%%" % abs(change))
            message += "\n总体积 %s -> %s（%s）" % (
                _format_size(summary.total_original),
                _format_size(summary.total_output), volume)

        details = []
        for path, reason in summary.skipped[:5]:
            details.append("跳过 %s: %s" % (Path(path).name, reason))
        for path, reason in summary.failures[:5]:
            details.append("失败 %s: %s" % (Path(path).name, reason))
        if details:
            message += "\n\n" + "\n".join(details)

        self.status_var.set("完成：成功 %d 张，跳过 %d 张，失败 %d 张。" % (
            len(summary.results), len(summary.skipped), len(summary.failures)))
        if summary.skipped or summary.failures:
            messagebox.showwarning("完成（有跳过或失败）", message)
        else:
            messagebox.showinfo("完成", message)


def main():
    root = tk.Tk()
    style = ttk.Style()
    if "vista" in style.theme_names():
        style.theme_use("vista")
    CompressApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
