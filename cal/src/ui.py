"""Tkinter front-end for the calculator.

`CalculatorApp` manages either its own `tk.Tk()` window (when created with
no argument, as in the window tests) or a caller-supplied root (as in the
integration tests). `self.window` and `self.root` both refer to that window.
"""

import tkinter as tk
from tkinter import ttk

from src import calculator


class CalculatorApp:
    _OPS = {'+': 'add', '-': 'subtract', '*': 'multiply', '/': 'divide'}

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

        # History line: shows the last calculation as "expression=result".
        self.history = ttk.Entry(self.root, font=('Arial', 12))
        self.history.pack(pady=5)

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

    def calculate(self):
        # Capture the expression BEFORE rewriting the entry, so the history
        # records the original input rather than the result.
        expression = self.entry.get()
        try:
            result = self._evaluate(expression)
            formatted = self._format(result)
            self._set_entry(formatted)
            self.update_history(expression, formatted)
        except ValueError as e:
            self._set_entry(f"Error: {str(e)}")

    def update_history(self, expression, result):
        self.history.delete(0, 'end')
        self.history.insert(0, f"{expression}={result}")

    def _set_entry(self, text):
        self.entry.delete(0, 'end')
        self.entry.insert(0, text)

    def _format(self, value):
        # Show whole numbers without a trailing ".0" (e.g. 5.0 -> "5").
        if isinstance(value, float) and value.is_integer():
            return str(int(value))
        return str(value)

    def _evaluate(self, expr):
        expr = expr.strip()
        op_index = -1
        op_char = None
        for i, ch in enumerate(expr):
            if ch in self._OPS and i > 0:
                op_index, op_char = i, ch
        if op_index == -1:
            return float(expr)
        a = float(expr[:op_index])
        b = float(expr[op_index + 1:])
        return getattr(calculator, self._OPS[op_char])(a, b)

    def toggle_theme(self):
        current = self.style.theme_use()
        self.style.theme_use('alt' if current == 'clam' else 'clam')
