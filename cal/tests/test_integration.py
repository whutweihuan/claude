import tkinter as tk

from src.ui import CalculatorApp


def test_full_calculation_flow():
    root = tk.Tk()
    app = CalculatorApp(root)
    app.entry.insert(0, '2+3')
    app.calculate()
    assert app.entry.get() == '5'
