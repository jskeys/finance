import dataclasses
import enum
import numpy as np
import typing

from datetime import date
from dateutil.relativedelta import relativedelta
from decimal import Decimal

from .core import CURRENCY_EPSILON, ROUNDING_STRATEGY

import dataclasses

ONE_YEAR = relativedelta(years=1)
ZERO = Decimal(0)


class Disposition(enum.IntEnum):
    QUALIFYING = 0
    DISQUALIFYING = enum.auto()


@dataclasses.dataclass(frozen=True)
class IncentiveStockOption:
    num_options: int
    fmv: Decimal
    exercise_price: Decimal
    sale_price: Decimal
    grant_date: date
    exercise_date: date
    sale_date: date
    uid: typing.Optional[str]

    def __post_init__(self):
        """Quantize the amount using `CURRENCY_EPSILON`."""
        for attr in ("fmv", "exercise_price", "sale_price"):
            object.__setattr__(
                self,
                attr,
                getattr(self, attr).quantize(CURRENCY_EPSILON, rounding=ROUNDING_STRATEGY),
            )

    @property
    def bargain_element(self) -> Decimal:
        """
        Spread at exercise (AMT bargain element).
        """
        return max(ZERO, self.fmv - self.exercise_price) * self.num_options

    @property
    def net_income(self) -> Decimal:
        """
        Total economic gain (or loss) from exercise to sale.
        """
        return (self.sale_price - self.exercise_price) * self.num_options

    @property
    def disposition(self) -> Disposition:
        """
        Determine ISO disposition type.

        Qualifying disposition requires BOTH:
          - Sale ≥ 1 year after exercise, AND
          - Sale ≥ 2 years after grant
        """
        if (self.sale_date >= (self.exercise_date + ONE_YEAR)) and (
            self.sale_date >= (self.grant_date + 2 * ONE_YEAR)
        ):
            return Disposition.QUALIFYING

        return Disposition.DISQUALIFYING


@dataclasses.dataclass(frozen=True, order=True)
class TaxBracket:
    threshold: float
    rate: float


@dataclasses.dataclass(frozen=True)
class TaxSchedule:
    tax_brackets: typing.List[TaxBracket]

    def __post_init__(self):
        """Sort tax brackets once."""
        object.__setattr__(self, "tax_brackets", sorted(self.tax_brackets))

    def calculate_tax(self, income: float):
        """Calculate the tax."""
        lower_bounds = [bracket.threshold for bracket in self.tax_brackets]
        upper_bounds = lower_bounds[1:] + [np.inf]
        tax_rates = [bracket.rate for bracket in self.tax_brackets]

        income_in_bracket = np.clip(income, lower_bounds, upper_bounds) - lower_bounds
        taxes = income_in_bracket * tax_rates

        return taxes.sum()


if __name__ == "__main__":
    amt_tax_schedule = TaxSchedule(
        [
            TaxBracket(0, 0.26),
            TaxBracket(244500, 0.28),
        ]
    )

    tax_schedule = TaxSchedule(
        [
            TaxBracket(0, 0.10),
            TaxBracket(24800, 0.12),
            TaxBracket(100800, 0.22),
            TaxBracket(211400, 0.24),
            TaxBracket(403550, 0.32),
            TaxBracket(512450, 0.35),
            TaxBracket(768700, 0.37),
        ]
    )

    normal_income = 250000.00
    option_sale = 402444.60
    bargain_elements = 207200

    print(tax_schedule.calculate_tax(normal_income + option_sale - 32200))
    print(amt_tax_schedule.calculate_tax(normal_income + option_sale + bargain_elements - 140200))

    iso = IncentiveStockOption(
        num_options=10000,
        fmv=Decimal(10.94),
        exercise_price=Decimal(0.52),
        sale_price=Decimal(50.0),
        grant_date=date(2020, 5, 27),
        exercise_date=date.today(),
        sale_date=date(2027, 4, 1)
    )

    print(iso)
    print(iso.bargain_element)
    print(iso.net_income)
    print(iso.disposition)
