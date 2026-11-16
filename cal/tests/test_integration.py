import tkinter as tk

from src.ui import CalculatorApp


def test_full_calculation_flow():
    root = tk.Tk()
    app = CalculatorApp(root)
    app.entry.insert(0, '2+3')
    app.calculate()
    assert app.entry.get() == '5'


def test_ui_triggers_calculation():
    root = tk.Tk()
    app = CalculatorApp(root)
    app.entry.insert(0, '2+3')
    app.equals_button.invoke()
    assert app.entry.get() == '5'
