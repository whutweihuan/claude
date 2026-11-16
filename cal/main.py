"""Entry point for the calculator.

Run with:

    python main.py

This opens the calculator window and lets a real user type / click
expressions interactively. The window stays open until it is closed.
"""

from src.ui import CalculatorApp


def main():
    app = CalculatorApp()
    app.window.mainloop()


if __name__ == '__main__':
    main()
