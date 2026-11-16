"""Tkinter front-end for the calculator.

`CalculatorApp` manages either its own `tk.Tk()` window (when created with
no argument, as in the window tests) or a caller-supplied root (as in the
integration tests). `self.window` and `self.root` both refer to that window.
"""

import tkinter as tk
from tkinter import ttk


class CalculatorApp:
    def __init__(self, root=None):
        self._owns_root = root is None
        self.root = root if root is not None else tk.Tk()
        # Alias so callers that think in terms of a "window" and those that
        # pass a "root" both work.
        self.window = self.root
        self.setup_ui()

    def setup_ui(self):
        self.root.title("Basic Calculator")
        self.root.geometry("300x400")
        self.create_widgets()

    def create_widgets(self):
        self.style = ttk.Style()

        self.entry = ttk.Entry(self.root, font=('Arial', 20))
        self.entry.pack(pady=10)

        button_frame = ttk.Frame(self.root)
        button_frame.pack()

        # Digit and operator buttons. Each inserts its label into the entry
        # so a user can build expressions like "2+3". "C" clears the entry.
        layout = [
            ['7', '8', '9', '/'],
            ['4', '5', '6', '*'],
            ['1', '2', '3', '-'],
            ['0', '.', 'C', '+'],
        ]
        for row_index, row in enumerate(layout):
            for col_index, label in enumerate(row):
                ttk.Button(
                    button_frame,
                    text=label,
                    width=4,
                    command=lambda l=label: self._press(l),
                ).grid(row=row_index, column=col_index, padx=2, pady=2)

    def _press(self, label):
        if label == 'C':
            self.entry.delete(0, 'end')
        else:
            self.entry.insert('end', label)

    def toggle_theme(self):
        current = self.style.theme_use()
        self.style.theme_use('alt' if current == 'clam' else 'clam')
