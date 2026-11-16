from src.ui import CalculatorApp


def test_history_display(tk_root):
    app = CalculatorApp(tk_root)
    app.entry.insert(0, '2+2')
    app.calculate()
    assert app.history.get() == "2+2=4"
