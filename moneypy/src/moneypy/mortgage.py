"""Common financial formulas."""

import numpy.typing as npt

from .core import calc_annuity

MONTHS_PER_YEAR = 12


def calc_home_value(
    down_payment: npt.ArrayLike,
    monthly_payment: npt.ArrayLike,
    interest_rate: npt.ArrayLike,
    tax_rate: float = 0,
    insurance_rate: float = 0,
    num_months: int = 360,
) -> npt.NDArray:
    """Calculate home value subject to `down_payment`, `monthly_payment`, and `interest_rate`."""

    annuity = calc_annuity(interest_rate / MONTHS_PER_YEAR, num_months)

    return (monthly_payment + down_payment * annuity) / (
        (tax_rate + insurance_rate) / MONTHS_PER_YEAR + annuity
    )


def calc_down_payment(
    home_value: npt.ArrayLike,
    monthly_payment: npt.ArrayLike,
    interest_rate: npt.ArrayLike,
    tax_rate: float = 0,
    insurance_rate: float = 0,
    num_months: int = 360,
) -> npt.NDArray:
    """Calculate down payment subject to `home_value`, `monthly_payment`, and `interest_rate`."""
    return home_value - (
        (monthly_payment - home_value * (insurance_rate + tax_rate) / MONTHS_PER_YEAR)
        / calc_annuity(interest_rate / MONTHS_PER_YEAR, num_months)
    )


def calc_monthly_payment(
    home_value: npt.ArrayLike,
    down_payment: npt.ArrayLike,
    interest_rate: npt.ArrayLike,
    tax_rate: float = 0,
    insurance_rate: float = 0,
    num_months: int = 360,
) -> npt.NDArray:
    """Calculate down payment subject to `home_value`, `monthly_payment`, and `interest_rate`."""
    return (home_value - down_payment) * calc_annuity(
        interest_rate / MONTHS_PER_YEAR, num_months
    ) + home_value * (tax_rate + insurance_rate) / MONTHS_PER_YEAR
