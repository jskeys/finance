"""Common financial formulas."""

import numpy as np
import numpy.typing as npt


def calc_annuity(rate_per_period: npt.NDArray, periods: int = 360) -> npt.NDArray:
    return rate_per_period / (1 - np.power(1 + rate_per_period, -1 * periods))


def calc_annuity_schedule(rate_per_period: float, periods: int = 360) -> npt.NDArray:
    """Return the principal, interest, and balance per period."""

    annuity = calc_annuity(rate_per_period, periods)

    schedule = np.zeros((5, periods))
    schedule[0, 0] = 1

    for i in range(periods - 1):
        balance = schedule[0, i]
        interest = balance * rate_per_period
        principal = annuity - interest

        schedule[0, i + 1] = balance - principal
        schedule[1, i + 1] = interest
        schedule[2, i + 1] = principal
        schedule[3, i + 1] = interest + schedule[3, i]
        schedule[4, i + 1] = principal + schedule[4, i]

    return schedule
