"""shareFile 的 Tkinter 主窗口与启动入口。"""

import json
import os
import socket
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from share_core import format_size
from share_server import ShareServer

DEFAULT_PORT = 8000
WINDOW_MIN_WIDTH = 560
WINDOW_MIN_HEIGHT = 760
MAX_TRANSFER_ROWS = 100


def enable_dpi_awareness():
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.shcore.SetProcessDpiAwareness(1)
        return
    except Exception:
        pass
    try:
        import ctypes

        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


def load_config(path, default_dir):
    default = {
        "shared_dir": str(Path(default_dir).resolve()),
        "port": DEFAULT_PORT,
    }
    path = Path(path)
    try:
        with open(str(path), "r", encoding="utf-8") as handle:
            raw = json.load(handle)
    except (OSError, ValueError):
        return default

    if not isinstance(raw, dict):
        return default

    shared = raw.get("shared_dir")
    if not isinstance(shared, str) or not shared.strip():
        return default

    shared_path = Path(shared)
    if not shared_path.is_absolute():
        shared_path = (path.parent / shared_path).resolve()
    else:
        shared_path = shared_path.resolve()

    try:
        port = int(raw.get("port", DEFAULT_PORT))
    except (TypeError, ValueError):
        port = DEFAULT_PORT
    if not 1 <= port <= 65535:
        port = DEFAULT_PORT

    return {"shared_dir": str(shared_path), "port": port}


def save_config(path, shared_dir, port):
    path = Path(path)
    payload = {
        "shared_dir": str(Path(shared_dir).resolve()),
        "port": int(port),
    }
    tmp = path.with_name(path.name + ".tmp")
    with open(str(tmp), "w", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, indent=2))
    os.replace(str(tmp), str(path))


def _is_private(ip):
    try:
        parts = [int(part) for part in ip.split(".")]
    except ValueError:
        return False
    if len(parts) != 4:
        return False
    if parts[0] == 10:
        return True
    if parts[0] == 172 and 16 <= parts[1] <= 31:
        return True
    if parts[0] == 192 and parts[1] == 168:
        return True
    return False


def choose_addresses(candidates):
    seen = set()
    private = []
    public = []

    for candidate in candidates:
        if not isinstance(candidate, str):
            continue
        ip = candidate.strip()
        if not ip or ip.startswith("127.") or ip.startswith("169.254."):
            continue
        if ip.count(".") != 3 or ip in seen:
            continue
        seen.add(ip)
        if _is_private(ip):
            private.append(ip)
        else:
            public.append(ip)

    result = private + public
    return result or ["127.0.0.1"]


def get_lan_addresses():
    candidates = []
    sock = None
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(("8.8.8.8", 80))
        candidates.append(sock.getsockname()[0])
    except OSError:
        pass
    finally:
        if sock is not None:
            try:
                sock.close()
            except OSError:
                pass

    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            candidates.append(info[4][0])
    except OSError:
        pass

    return choose_addresses(candidates)


def is_writable(path):
    return os.access(str(path), os.W_OK)


class ShareApp(tk.Tk):
    def __init__(self, config_path, shared_dir=None, port=None):
        tk.Tk.__init__(self)
        self.config_path = Path(config_path)
        default_dir = self.config_path.parent / "shared"
        cfg = load_config(self.config_path, default_dir)

        self.shared_dir = Path(shared_dir) if shared_dir is not None else Path(cfg["shared_dir"])
        self.listen_port = int(port if port is not None else cfg["port"])
        self._ensure_shared_dir()

        self.events = None
        self.server = None
        self._rows = {}
        self._row_order = []
        self._closing = False

        self.title("局域网文件共享")
        self.path_var = tk.StringVar()
        self.address_var = tk.StringVar()
        self.pin_var = tk.StringVar()
        self.status_var = tk.StringVar(value="正在启动…")
        self._build_ui()
        self._start_server()
        self._refresh_path_label()
        self._refresh_addresses()
        self._refresh_pin()
        self._update_status()
        self._fit_window()
        self.after(200, self.poll_events)
        self.protocol("WM_DELETE_WINDOW", self.close)

    # ---- 启动与配置 ----

    def _ensure_shared_dir(self):
        try:
            self.shared_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass

    def _start_server(self):
        import queue

        self.events = queue.Queue(maxsize=1000)
        try:
            server = ShareServer(
                self.shared_dir,
                port=self.listen_port,
                events=self.events,
                read_only=not is_writable(self.shared_dir),
            )
            server.start()
        except OSError as exc:
            self.server = None
            self.status_var.set("启动失败：%s" % exc)
            self.status_label.configure(foreground="#aa0000")
            return

        self.server = server
        self.status_var.set("运行中 · 端口 %d" % server.port)

    def _refresh_path_label(self):
        text = str(self.shared_dir)
        if len(text) > 40:
            text = text[:18] + "…" + text[-18:]
        self.path_var.set(text)

    def _refresh_addresses(self):
        if self.server is None:
            self.address_var.set("未启动")
            self.address_combo["values"] = []
            return
        addresses = get_lan_addresses()
        values = [
            "http://%s:%d/" % (ip, self.server.port) for ip in addresses
        ]
        self.address_combo["values"] = values
        current = self.address_var.get()
        if current not in values:
            self.address_var.set(values[0])
        self.draw_qr(self.address_var.get())

    def _refresh_pin(self):
        if self.server is None:
            self.pin_var.set("----")
        else:
            self.pin_var.set(self.server.pin)
        self.pin_label.configure(text=self.pin_var.get())

    def _update_status(self):
        if self.server is None:
            return
        if not self.server.state.can_write():
            self.status_var.set("运行中 · 端口 %d · 只读" % self.server.port)
        else:
            self.status_var.set("运行中 · 端口 %d" % self.server.port)

    # ---- 界面 ----

    def _build_ui(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=0)
        self.rowconfigure(2, weight=1)

        top = ttk.Frame(self, padding=(12, 10, 12, 4))
        top.grid(row=0, column=0, sticky="ew")
        top.columnconfigure(1, weight=1)

        ttk.Label(top, text="共享文件夹").grid(row=0, column=0, sticky="w")
        self.path_label = ttk.Label(top, textvariable=self.path_var)
        self.path_label.grid(row=0, column=1, sticky="ew", padx=(8, 8))
        ttk.Button(top, text="选择…", command=self.choose_folder).grid(row=0, column=2)
        ttk.Button(top, text="打开", command=self.open_folder).grid(row=0, column=3, padx=(6, 0))

        ttk.Label(top, text="访问地址").grid(row=1, column=0, sticky="w", pady=(8, 0))
        self.address_combo = ttk.Combobox(
            top, textvariable=self.address_var, state="readonly"
        )
        self.address_combo.grid(row=1, column=1, sticky="ew", padx=(8, 8), pady=(8, 0))
        self.address_combo.bind("<<ComboboxSelected>>", self._on_address_selected)
        ttk.Button(top, text="复制", command=self.copy_address).grid(
            row=1, column=2, pady=(8, 0)
        )

        middle = ttk.Frame(self, padding=(12, 6, 12, 6))
        middle.grid(row=1, column=0, sticky="nsew")
        middle.columnconfigure(0, weight=1)
        middle.columnconfigure(1, weight=0)

        self.qr_canvas = tk.Canvas(
            middle, width=220, height=220, background="white",
            highlightthickness=1, highlightbackground="#cccccc",
        )
        self.qr_canvas.grid(row=0, column=0, rowspan=2, sticky="n")

        pin_box = ttk.Frame(middle)
        pin_box.grid(row=0, column=1, sticky="n", padx=(18, 0))
        ttk.Label(pin_box, text="网页口令").pack(anchor="w")
        self.pin_label = ttk.Label(
            pin_box, text="----", font=("Consolas", 28, "bold")
        )
        self.pin_label.pack(anchor="w", pady=(4, 8))
        ttk.Button(pin_box, text="换一个口令", command=self.regenerate_pin).pack(anchor="w")
        ttk.Label(
            pin_box,
            text="手机与电脑需在同一 Wi-Fi\n扫码后输入口令即可上传下载",
            justify="left",
            foreground="#666666",
            wraplength=220,
        ).pack(anchor="w", pady=(16, 0))

        transfers = ttk.Frame(self, padding=(12, 0, 12, 6))
        transfers.grid(row=2, column=0, sticky="nsew")
        transfers.columnconfigure(0, weight=1)
        ttk.Label(transfers, text="传输记录").grid(row=0, column=0, sticky="w")
        self.transfer_tree = ttk.Treeview(
            transfers,
            columns=("direction", "name", "size", "progress", "speed"),
            show="headings",
            height=10,
        )
        headings = {
            "direction": "方向",
            "name": "文件",
            "size": "大小",
            "progress": "进度",
            "speed": "速度",
        }
        widths = {
            "direction": 54,
            "name": 230,
            "size": 70,
            "progress": 70,
            "speed": 80,
        }
        for column, title in headings.items():
            self.transfer_tree.heading(column, text=title)
            self.transfer_tree.column(
                column, width=widths[column], anchor="w", stretch=(column == "name")
            )
        self.transfer_tree.grid(row=1, column=0, sticky="nsew", pady=(4, 0))
        transfers.rowconfigure(1, weight=1)

        self.status_label = ttk.Label(
            self, textvariable=self.status_var, padding=(12, 4, 12, 8),
            foreground="#1a6b2f",
        )
        self.status_label.grid(row=3, column=0, sticky="ew")

    def _fit_window(self):
        self.update_idletasks()
        width = max(WINDOW_MIN_WIDTH, self.winfo_reqwidth())
        height = max(WINDOW_MIN_HEIGHT, self.winfo_reqheight())
        self.geometry("%dx%d" % (width, height))
        self.minsize(width, height)

    # ---- 二维码 ----

    def draw_qr(self, url):
        self.qr_canvas.delete("all")
        matrix = None

        try:
            import segno
        except ImportError:
            segno = None

        if segno is not None:
            try:
                matrix = [list(row) for row in segno.make(url, error="m").matrix]
            except Exception:
                matrix = None

        if matrix is None:
            try:
                import share_qr

                matrix = share_qr.encode(url)
            except Exception:
                self.qr_canvas.create_text(
                    110, 110,
                    text="二维码生成失败\n%s" % url,
                    justify="center",
                    fill="#aa0000",
                    width=190,
                )
                return

        size = len(matrix)
        scale = max(1, 220 // (size + 8))
        offset = (220 - (size + 8) * scale) // 2 + 4 * scale

        for row_index, row in enumerate(matrix):
            col = 0
            while col < size:
                if not row[col]:
                    col += 1
                    continue
                start = col
                while col < size and row[col]:
                    col += 1
                self.qr_canvas.create_rectangle(
                    offset + start * scale,
                    offset + row_index * scale,
                    offset + col * scale,
                    offset + (row_index + 1) * scale,
                    fill="black",
                    outline="black",
                )

    # ---- 事件与按钮 ----

    def _on_address_selected(self, event=None):
        self.draw_qr(self.address_var.get())

    def choose_folder(self):
        chosen = filedialog.askdirectory(
            parent=self, initialdir=str(self.shared_dir), title="选择共享文件夹"
        )
        if not chosen:
            return
        self.shared_dir = Path(chosen)
        self._ensure_shared_dir()
        if self.server is not None:
            self.server.set_shared_dir(self.shared_dir)
            self.server.state.set_read_only(not is_writable(self.shared_dir))
        try:
            save_config(self.config_path, self.shared_dir, self.listen_port)
        except OSError as exc:
            self.status_var.set("保存配置失败：%s" % exc)
        self._refresh_path_label()
        self._update_status()

    def open_folder(self):
        path = str(self.shared_dir)
        try:
            if sys.platform == "win32":
                os.startfile(path)
            elif sys.platform == "darwin":
                import subprocess

                subprocess.Popen(["open", path])
            else:
                import subprocess

                subprocess.Popen(["xdg-open", path])
        except OSError as exc:
            messagebox.showerror("无法打开文件夹", str(exc), parent=self)

    def copy_address(self):
        address = self.address_var.get()
        if address and address != "未启动":
            self.clipboard_clear()
            self.clipboard_append(address)

    def regenerate_pin(self):
        if self.server is None:
            return
        self.server.regenerate_pin()
        self._refresh_pin()

    def poll_events(self):
        if self._closing:
            return
        if self.events is not None:
            while True:
                try:
                    event = self.events.get_nowait()
                except Exception:
                    break
                self._apply_event(event)
        if not self._closing:
            self.after(200, self.poll_events)

    def _apply_event(self, event):
        kind = event.get("kind", "")
        name = event.get("name", "")
        phase = event.get("phase", "")
        key = (kind, name)
        total = int(event.get("size") or event.get("total") or 0)
        done = int(event.get("done") or 0)
        direction = "上传" if kind == "upload" else "下载"

        if phase == "start":
            if key not in self._rows:
                item = self.transfer_tree.insert(
                    "", "end",
                    values=(direction, name, format_size(total), "0%", ""),
                )
                self._rows[key] = item
                self._row_order.append(item)
                while len(self._row_order) > MAX_TRANSFER_ROWS:
                    oldest = self._row_order.pop(0)
                    self.transfer_tree.delete(oldest)
                    for row_key, row_item in list(self._rows.items()):
                        if row_item == oldest:
                            del self._rows[row_key]
            return

        item = self._rows.get(key)
        if item is None:
            return

        if phase == "progress":
            percent = int(done * 100 / total) if total else 0
            speed = event.get("speed") or 0
            self.transfer_tree.set(item, "progress", "%d%%" % min(percent, 100))
            self.transfer_tree.set(
                item, "size", format_size(total) if total else ""
            )
            self.transfer_tree.set(item, "speed", "%s/s" % format_size(int(speed)))
        elif phase == "done":
            saved_name = event.get("saved_name")
            if saved_name:
                self.transfer_tree.set(item, "name", saved_name)
            self.transfer_tree.set(item, "progress", "100%")
            self.transfer_tree.set(item, "speed", "")
        elif phase == "error":
            self.transfer_tree.set(item, "progress", "失败")
            self.transfer_tree.set(item, "speed", "")

    def close(self):
        if self._closing:
            return
        self._closing = True
        if self.server is not None:
            try:
                self.server.stop()
            except Exception:
                pass
            self.server = None
        self.destroy()


def main():
    enable_dpi_awareness()
    script_dir = Path(__file__).resolve().parent
    config_path = script_dir / "config.json"
    try:
        app = ShareApp(config_path=config_path)
    except Exception as exc:
        try:
            messagebox.showerror("局域网文件共享", "启动失败：%s" % exc)
        except Exception:
            pass
        return

    app.mainloop()


if __name__ == "__main__":
    main()
