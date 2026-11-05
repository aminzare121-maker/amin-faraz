"""Exact finite decimal inputs. No floats or implicit unknown-to-zero conversion."""
from decimal import Decimal


def dec(value):
    if isinstance(value, bool) or not isinstance(value, (str, int, Decimal)):
        raise ValueError("EXACT_DECIMAL_REQUIRED")
    try:
        result = Decimal(value)
    except (ValueError, ArithmeticError):
        raise ValueError("INVALID_DECIMAL") from None
    if not result.is_finite():
        raise ValueError("FINITE_DECIMAL_REQUIRED")
    if len(result.as_tuple().digits) > 128 or abs(result.as_tuple().exponent) > 64:
        raise ValueError("DECIMAL_INPUT_BOUND_EXCEEDED")
    return result


def natural(value):
    if type(value) is not int or value < 0:
        raise ValueError("NONNEGATIVE_INTEGER_REQUIRED")
    return value
