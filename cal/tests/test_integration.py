from src.ui import CalculatorApp


def test_full_calculation_flow(tk_root):
    app = CalculatorApp(tk_root)
    app.entry.insert(0, '2+3')
    app.calculate()
    assert app.entry.get() == '5'


def test_ui_triggers_calculation(tk_root):
    app = CalculatorApp(tk_root)
    app.entry.insert(0, '2+3')
    app.equals_button.invoke()
    assert app.entry.get() == '5'
