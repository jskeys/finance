"""Common financial formulas."""

import numpy as np
import numpy.typing as npt


def calc_annuity(rate_per_period: npt.NDArray, periods: int = 360) -> npt.NDArray:
    return rate_per_period / (1 - np.power(1 + rate_per_period, -1 * periods))
