"""Basic arithmetic operations for the calculator.

Pure functions: each takes two numbers and returns a number, with no
UI or I/O side effects. `divide` raises ValueError on a zero divisor so
callers can surface a stable, predictable error message.
"""


def add(a: float, b: float) -> float:
    return a + b


def subtract(a: float, b: float) -> float:
    return a - b


def multiply(a: float, b: float) -> float:
    return a * b


def divide(a: float, b: float) -> float:
    if b == 0:
        raise ValueError("Cannot divide by zero")
    return a / b
