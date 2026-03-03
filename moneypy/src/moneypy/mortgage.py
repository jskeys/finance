"""Common financial formulas."""

from __future__ import annotations

import numpy as np
import numpy.typing as npt

from .core import calc_annuity

MONTHS_PER_YEAR: int = 12


def calc_home_value(
    down_payment: npt.ArrayLike,
    monthly_payment: npt.ArrayLike,
    interest_rate: npt.ArrayLike,
    *,
    tax_rate: float = 0.0,
    insurance_rate: float = 0.0,
    num_months: int = 360,
) -> npt.NDArray[np.floating]:
    """Calculate the maximum home value affordable.

    Parameters are broadcast according to NumPy rules.
    """
    down_payment = np.asarray(down_payment, dtype=float)
    monthly_payment = np.asarray(monthly_payment, dtype=float)
    interest_rate = np.asarray(interest_rate, dtype=float)

    annuity = calc_annuity(interest_rate / MONTHS_PER_YEAR, num_months)
    carrying_rate = (tax_rate + insurance_rate) / MONTHS_PER_YEAR

    return (monthly_payment + down_payment * annuity) / (carrying_rate + annuity)


def calc_down_payment(
    home_value: npt.ArrayLike,
    monthly_payment: npt.ArrayLike,
    interest_rate: npt.ArrayLike,
    *,
    tax_rate: float = 0.0,
    insurance_rate: float = 0.0,
    num_months: int = 360,
) -> npt.NDArray[np.floating]:
    """Calculate the required down payment for a given home value."""
    interest_rate = np.asarray(interest_rate, dtype=float)
    home_value = np.asarray(home_value, dtype=float)
    monthly_payment = np.asarray(monthly_payment, dtype=float)

    annuity = calc_annuity(interest_rate / MONTHS_PER_YEAR, num_months)
    carrying_cost = home_value * (tax_rate + insurance_rate) / MONTHS_PER_YEAR

    return home_value - (monthly_payment - carrying_cost) / annuity


def calc_monthly_payment(
    home_value: npt.ArrayLike,
    down_payment: npt.ArrayLike,
    interest_rate: npt.ArrayLike,
    *,
    tax_rate: float = 0.0,
    insurance_rate: float = 0.0,
    num_months: int = 360,
) -> npt.NDArray[np.floating]:
    """Calculate the required monthly payment for a given home value and down payment."""
    home_value = np.asarray(home_value, dtype=float)
    down_payment = np.asarray(down_payment, dtype=float)
    interest_rate = np.asarray(interest_rate, dtype=float)

    annuity = calc_annuity(interest_rate / MONTHS_PER_YEAR, num_months)
    carrying_cost = home_value * (tax_rate + insurance_rate) / MONTHS_PER_YEAR

    return (home_value - down_payment) * annuity + carrying_cost
