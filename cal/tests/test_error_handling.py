import tkinter as tk

from src.ui import CalculatorApp


def test_divide_by_zero():
    root = tk.Tk()
    app = CalculatorApp(root)
    app.entry.insert(0, '5/0')
    app.calculate()
    assert app.entry.get() == "Error: Cannot divide by zero"
