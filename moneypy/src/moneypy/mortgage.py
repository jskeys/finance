"""Tools for evaluating mortgage parameters."""

from __future__ import annotations

import typing
from enum import IntEnum, auto

import numpy as np
import numpy.typing as npt

from .core import calc_annuity

MONTHS_PER_YEAR: int = 12


class MortgageParameters(IntEnum):
    HOME_VALUE = 0
    MONTHLY_PAYMENT = auto()
    DOWN_PAYMENT = auto()
    INTEREST_RATE = auto()
    TAX_RATE = auto()
    INSURANCE_RATE = auto()
    TERM_MONTHS = auto()


def calc_home_value(
    down_payment: npt.ArrayLike,
    monthly_payment: npt.ArrayLike,
    interest_rate: npt.ArrayLike,
    *,
    tax_rate: float = 0.0,
    insurance_rate: float = 0.0,
    num_months: int = 360,
) -> typing.Tuple[npt.NDArray[np.floating], typing.Tuple[MortgageParameters, ...]]:
    """Calculate the maximum home value affordable.

    Parameters are broadcast according to NumPy rules.
    """

    (dp_mesh, mp_mesh, ir_mesh) = np.ix_(
        np.asarray(down_payment, dtype=float).reshape(-1),
        np.asarray(monthly_payment, dtype=float).reshape(-1),
        np.asarray(interest_rate, dtype=float).reshape(-1),
    )

    annuity = calc_annuity(ir_mesh / MONTHS_PER_YEAR, num_months)
    carrying_rate = (tax_rate + insurance_rate) / MONTHS_PER_YEAR

    return (
        (mp_mesh + dp_mesh * annuity) / (carrying_rate + annuity),
        (
            MortgageParameters.DOWN_PAYMENT,
            MortgageParameters.MONTHLY_PAYMENT,
            MortgageParameters.INTEREST_RATE,
        ),
    )


def calc_down_payment(
    home_value: npt.ArrayLike,
    monthly_payment: npt.ArrayLike,
    interest_rate: npt.ArrayLike,
    *,
    tax_rate: float = 0.0,
    insurance_rate: float = 0.0,
    num_months: int = 360,
) -> typing.Tuple[npt.NDArray[np.floating], typing.Tuple[MortgageParameters, ...]]:
    """Calculate the required down payment for a given home value."""

    (hv_mesh, mp_mesh, ir_mesh) = np.ix_(
        np.asarray(home_value, dtype=float).reshape(-1),
        np.asarray(monthly_payment, dtype=float).reshape(-1),
        np.asarray(interest_rate, dtype=float).reshape(-1),
    )

    annuity = calc_annuity(ir_mesh / MONTHS_PER_YEAR, num_months)
    carrying_cost = hv_mesh * (tax_rate + insurance_rate) / MONTHS_PER_YEAR

    return (
        hv_mesh - (mp_mesh - carrying_cost) / annuity,
        (
            MortgageParameters.HOME_VALUE,
            MortgageParameters.MONTHLY_PAYMENT,
            MortgageParameters.INTEREST_RATE,
        ),
    )


def calc_monthly_payment(
    home_value: npt.ArrayLike,
    down_payment: npt.ArrayLike,
    interest_rate: npt.ArrayLike,
    *,
    tax_rate: float = 0.0,
    insurance_rate: float = 0.0,
    num_months: int = 360,
) -> typing.Tuple[npt.NDArray[np.floating], typing.Tuple[MortgageParameters, ...]]:
    """Calculate the required monthly payment for a given home value and down payment."""

    (hv_mesh, dp_mesh, ir_mesh) = np.ix_(
        np.asarray(home_value, dtype=float).reshape(-1),
        np.asarray(down_payment, dtype=float).reshape(-1),
        np.asarray(interest_rate, dtype=float).reshape(-1),
    )

    annuity = calc_annuity(ir_mesh / MONTHS_PER_YEAR, num_months)
    carrying_cost = hv_mesh * (tax_rate + insurance_rate) / MONTHS_PER_YEAR

    return (
        (hv_mesh - dp_mesh) * annuity + carrying_cost,
        (
            MortgageParameters.HOME_VALUE,
            MortgageParameters.DOWN_PAYMENT,
            MortgageParameters.INTEREST_RATE,
        ),
    )
