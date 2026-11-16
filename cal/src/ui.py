"""Tkinter front-end for the calculator.

`CalculatorApp` manages either its own `tk.Tk()` window (when created with
no argument, as in the window tests) or a caller-supplied root (as in the
integration tests). `self.window` and `self.root` both refer to that window.
"""

import ast

import tkinter as tk
from tkinter import ttk

from src import calculator


class CalculatorApp:
    # Maps AST binary-operator node types to calculator functions. Using the
    # AST (not eval) keeps user input safe while supporting multiple operators
    # with standard precedence (e.g. 1 + 6 * 9 = 55).
    _AST_OPS = {
        ast.Add: 'add',
        ast.Sub: 'subtract',
        ast.Mult: 'multiply',
        ast.Div: 'divide',
    }

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
        # Buttons are kept in self.buttons (keyed by label) so callers and
        # tests can drive the real widgets (e.g. buttons['2'].invoke()).
        self.buttons = {}
        for row_index, row in enumerate(layout):
            for col_index, label in enumerate(row):
                button = ttk.Button(
                    button_frame,
                    text=label,
                    width=4,
                    command=lambda l=label: self._press(l),
                )
                button.grid(row=row_index, column=col_index, padx=2, pady=2)
                self.buttons[label] = button

        # Full-width equals button triggers the calculation, alongside the
        # Enter key, so a real user can actually run an expression.
        self.equals_button = ttk.Button(
            button_frame,
            text='=',
            width=4,
            command=self.calculate,
        )
        self.equals_button.grid(row=len(layout), column=0, columnspan=len(layout[0]), padx=2, pady=2)
        self.root.bind('<Return>', lambda event: self.calculate())

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
        # Parse the expression into an AST and evaluate it. This supports any
        # number of operators with standard precedence (1 + 6 * 9 = 55) while
        # staying safe: we only ever walk numbers and the four arithmetic
        # operators, never executing arbitrary Python.
        expr = expr.strip()
        if not expr:
            raise ValueError("Invalid expression: empty input")
        try:
            tree = ast.parse(expr, mode='eval')
        except SyntaxError:
            raise ValueError("Invalid expression: malformed input")
        return self._eval_node(tree.body)

    def _eval_node(self, node):
        # A number literal. ast.Num is what 3.8 produces; ast.Constant covers
        # newer builds. Reject non-numeric constants (e.g. names, strings).
        if isinstance(node, (ast.Constant, ast.Num)):
            value = node.value if isinstance(node, ast.Constant) else node.n
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError("Invalid expression: unsupported literal")
            return float(value)
        if isinstance(node, ast.BinOp):
            left = self._eval_node(node.left)
            right = self._eval_node(node.right)
            op_name = self._AST_OPS.get(type(node.op))
            if op_name is None:
                raise ValueError("Invalid expression: unsupported operator")
            return getattr(calculator, op_name)(left, right)
        if isinstance(node, ast.UnaryOp):
            # Allow a leading sign, e.g. -5 or +3.
            operand = self._eval_node(node.operand)
            if isinstance(node.op, ast.USub):
                return -operand
            if isinstance(node.op, ast.UAdd):
                return operand
            raise ValueError("Invalid expression: unsupported unary operator")
        raise ValueError("Invalid expression: unsupported input")

    def toggle_theme(self):
        current = self.style.theme_use()
        self.style.theme_use('alt' if current == 'clam' else 'clam')
