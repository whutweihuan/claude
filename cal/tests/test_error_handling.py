from src.ui import CalculatorApp


def test_divide_by_zero(tk_root):
    app = CalculatorApp(tk_root)
    app.entry.insert(0, '5/0')
    app.calculate()
    assert app.entry.get() == "Error: Cannot divide by zero"


def test_invalid_expression_gives_clear_error(tk_root):
    # Non-numeric input must give a clear, stable error (not a raw float() crash).
    app = CalculatorApp(tk_root)
    app.entry.insert(0, 'abc')
    app.calculate()
    text = app.entry.get()
    assert text.startswith('Error:')
    assert 'Invalid expression' in text
