"""Common financial formulas."""

from __future__ import annotations

import numpy as np
import numpy.typing as npt


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
