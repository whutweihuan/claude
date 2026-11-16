from src.ui import CalculatorApp


def test_divide_by_zero(tk_root):
    app = CalculatorApp(tk_root)
    app.entry.insert(0, '5/0')
    app.calculate()
    assert app.entry.get() == "Error: Cannot divide by zero"


def test_multi_operator_gives_clear_error(tk_root):
    app = CalculatorApp(tk_root)
    app.entry.insert(0, '2+3+4')
    app.calculate()
    text = app.entry.get()
    assert text.startswith('Error:')
    assert 'Invalid expression' in text
