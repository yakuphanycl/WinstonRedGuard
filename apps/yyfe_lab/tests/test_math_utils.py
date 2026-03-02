import pytest

from yyfe_lab.math_utils import divide, moving_average, percentage


def test_divide_basic():
    assert divide(6, 3) == 2


def test_divide_by_zero_raises():
    with pytest.raises(ZeroDivisionError):
        divide(1, 0)


def test_percentage_basic():
    assert percentage(1, 4) == 25.0


def test_percentage_total_zero_raises():
    with pytest.raises(ZeroDivisionError):
        percentage(10, 0)


def test_moving_average_basic():
    assert moving_average([1, 2, 3, 4], 2) == [1.5, 2.5, 3.5]


def test_moving_average_window_zero_raises():
    with pytest.raises(ValueError):
        moving_average([1, 2, 3], 0)


def test_moving_average_window_negative_raises():
    with pytest.raises(ValueError):
        moving_average([1, 2, 3], -1)


def test_moving_average_window_greater_than_length_returns_empty():
    # Current implementation returns [] when window > len(values).
    assert moving_average([1, 2, 3], 10) == []
