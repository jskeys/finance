"""Common financial formulas."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_EVEN
import numpy as np
import numpy.typing as npt


CURRENCY_EPSILON = Decimal("1.00")
ROUNDING_STRATEGY = ROUND_HALF_EVEN


def calc_annuity(
    rate_per_period: npt.ArrayLike,
    periods: float = 360.0,
) -> npt.NDArray[np.floating]:
    """
    Calculate the annuity factor for a fixed-rate loan.

    This returns the multiplier such that:

        payment = principal * annuity

    Parameters are broadcast according to NumPy rules.
    """
    rate = np.asarray(rate_per_period, dtype=float)

    # Handle zero-interest case explicitly
    return np.where(
        rate == 0,
        1 / periods,
        rate / (1 - np.power(1 + rate, -periods)),
    )
