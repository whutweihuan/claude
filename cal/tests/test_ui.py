from src.ui import CalculatorApp


def test_calculator_window(tk_root):
    # The app builds a live window from a Tk root.
    app = CalculatorApp(tk_root)
    assert app.window.winfo_exists() == 1


def test_theme_switch(tk_root):
    app = CalculatorApp(tk_root)
    app.toggle_theme()
    assert app.style.theme_use() in ['clam', 'alt']


def test_user_journey_through_buttons(tk_root):
    # Drive the UI exactly as a real user would: tap the digit/operator
    # buttons, then the equals button. This exercises the actual button ->
    # command wiring, not just the calculate() function directly.
    app = CalculatorApp(tk_root)
    for label in ('2', '+', '3'):
        app.buttons[label].invoke()
    app.equals_button.invoke()
    assert app.entry.get() == '5'
