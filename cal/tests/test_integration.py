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


def test_multi_operator_with_precedence(tk_root):
    # A real user expects standard operator precedence: 1 + 6 * 9 = 1 + 54 = 55
    # (not left-to-right 63). Multiple operators in one expression must work.
    app = CalculatorApp(tk_root)
    app.entry.insert(0, '1+6*9')
    app.calculate()
    assert app.entry.get() == '55'


def test_chained_addition(tk_root):
    # Chained same-operator input is a normal expression, not an error.
    app = CalculatorApp(tk_root)
    app.entry.insert(0, '2+3+4')
    app.calculate()
    assert app.entry.get() == '9'
