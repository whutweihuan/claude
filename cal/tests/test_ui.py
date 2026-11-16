from src.ui import CalculatorApp


def test_calculator_window():
    app = CalculatorApp()
    assert app.window.winfo_exists() == 1


def test_theme_switch():
    app = CalculatorApp()
    app.toggle_theme()
    assert app.style.theme_use() in ['clam', 'alt']
