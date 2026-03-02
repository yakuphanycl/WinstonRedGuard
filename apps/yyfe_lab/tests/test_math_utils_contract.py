import pytest

from yyfe_lab.math_utils import divide, moving_average, percentage


def test_divide_negative_values():
    assert divide(-6, 3) == -2
    assert divide(6, -3) == -2
    assert divide(-6, -3) == 2


def test_percentage_non_terminating_decimal_rounding_is_stable():
    # We don't demand a specific rounding policy; we demand numeric closeness.
    assert percentage(1, 3) == pytest.approx(33.3333333333, rel=1e-9)


def test_percentage_negative_values():
    assert percentage(-1, 4) == -25.0
    assert percentage(1, -4) == -25.0


def test_moving_average_window_one_returns_float_values():
    assert moving_average([1, 2, 3], 1) == [1.0, 2.0, 3.0]


def test_moving_average_empty_values_returns_empty():
    assert moving_average([], 1) == []
    assert moving_average([], 10) == []


def test_moving_average_window_equals_length_single_value():
    assert moving_average([1, 2, 3], 3) == [2.0]


def test_moving_average_window_must_be_int():
    with pytest.raises(TypeError):
        moving_average([1, 2, 3], 2.0)

    with pytest.raises(TypeError):
        moving_average([1, 2, 3], "2")
