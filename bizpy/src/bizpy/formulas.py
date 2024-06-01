"""Common financial formulas."""

import numpy as np
import numpy.typing as npt


def annuity(rate_per_period: npt.NDArray, periods: int = 360) -> npt.NDArray:
    return rate_per_period / (1 - np.power(1 + rate_per_period, -1 * periods))


def mortgage(
    down_payment: npt.NDArray,
    annual_interest_rate: npt.NDArray,
    annual_property_tax_rate: float,
    annual_insurance_rate: float,
    num_months: int = 360,
):
    return (1 - down_payment) * annuity(annual_interest_rate / 12, num_months) + (
        annual_property_tax_rate + annual_insurance_rate
    ) / 12
