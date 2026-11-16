from src.calculator import add, subtract, multiply, divide


def test_addition():
    assert add(2, 3) == 5


def test_subtraction():
    assert subtract(5, 3) == 2


def test_multiplication():
    assert multiply(4, 3) == 12


def test_division():
    assert divide(6, 3) == 2
