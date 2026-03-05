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
STANDARD_DEDUCTION = Decimal(32200)
MAX_AMT_EXEMPTION = Decimal(140200)


class Disposition(enum.Enum):
    NONE = "NONE"
    QUALIFYING = "QUALIFYING"
    DISQUALIFYING = "DISQUALIFYING"


@dataclasses.dataclass(frozen=True)
class IncentiveStockOption:
    uid: str
    num_shares: int
    grant_date: date
    exercise_price: Decimal
    fmv: typing.Optional[Decimal] = None
    sale_price: typing.Optional[Decimal] = None
    exercise_date: typing.Optional[date] = None
    sale_date: typing.Optional[date] = None

    def __post_init__(self):
        """Quantize the amount using `CURRENCY_EPSILON`."""
        for attr in ("fmv", "exercise_price", "sale_price"):
            if getattr(self, attr) is not None:
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
        return max(ZERO, self.fmv - self.exercise_price) * self.num_shares

    @property
    def exercise_cost(self) -> Decimal:
        """
        Spread at exercise (AMT bargain element).
        """
        return self.exercise_price * self.num_shares

    @property
    def net_income(self) -> Decimal:
        """
        Total economic gain (or loss) from exercise to sale.
        """
        if self.sale_price is not None:
            return (self.sale_price - self.exercise_price) * self.num_shares

        return Decimal("NaN")

    @property
    def proceeds(self) -> Decimal:
        """
        Total economic gain (or loss) from exercise to sale.
        """
        if self.sale_price is not None:
            return self.sale_price * self.num_shares

        return Decimal("NaN")

    @property
    def amt_gain(self) -> Decimal:
        """
        Total economic gain (or loss) from exercise to sale.
        """
        if self.sale_price is not None and self.fmv is not None:
            return (self.sale_price - self.fmv) * self.num_shares

        return Decimal("NaN")

    @property
    def disposition(self) -> Disposition:
        """
        Determine ISO disposition type.

        Qualifying disposition requires BOTH:
          - Sale ≥ 1 year after exercise, AND
          - Sale ≥ 2 years after grant
        """
        if self.sale_date is None or self.exercise_date is None:
            return Disposition.NONE

        if (self.sale_date >= (self.exercise_date + ONE_YEAR)) and (
            self.sale_date >= (self.grant_date + 2 * ONE_YEAR)
        ):
            return Disposition.QUALIFYING

        return Disposition.DISQUALIFYING


@dataclasses.dataclass(frozen=True)
class RestrictedStockUnit:
    uid: str
    num_shares: int
    grant_date: date
    vest_date: typing.Optional[date] = None
    vest_fmv: typing.Optional[Decimal] = None
    sale_price: typing.Optional[Decimal] = None
    sale_date: typing.Optional[date] = None

    def __post_init__(self):
        """Quantize currency values using `CURRENCY_EPSILON`."""
        for attr in ("vest_fmv", "sale_price"):
            value = getattr(self, attr)
            if value is not None:
                object.__setattr__(
                    self,
                    attr,
                    value.quantize(CURRENCY_EPSILON, rounding=ROUNDING_STRATEGY),
                )

    @property
    def compensation_income(self) -> Decimal:
        """
        Total economic gain (or loss) from exercise to sale.
        """
        if self.vest_fmv is not None:
            return self.vest_fmv * self.num_shares

        return Decimal("NaN")


@dataclasses.dataclass(frozen=True, order=True)
class Bracket:
    threshold: float
    rate: float


@dataclasses.dataclass(frozen=True)
class Schedule:
    brackets: typing.List[Bracket]

    def __post_init__(self):
        """Sort tax brackets once."""
        object.__setattr__(self, "brackets", sorted(self.brackets))

    def apply(self, income: float):
        """Calculate the tax."""
        lower_bounds = [bracket.threshold for bracket in self.brackets]
        upper_bounds = lower_bounds[1:] + [np.inf]
        tax_rates = [bracket.rate for bracket in self.brackets]

        income_in_bracket = np.clip(income, lower_bounds, upper_bounds) - lower_bounds
        taxes = income_in_bracket * tax_rates

        return taxes


@dataclasses.dataclass()
class RegularTaxSystem:
    def __post_init__(self):
        self._income_tax_schedule = Schedule(
            [
                Bracket(0, 0.10),
                Bracket(24800, 0.12),
                Bracket(100800, 0.22),
                Bracket(211400, 0.24),
                Bracket(403550, 0.32),
                Bracket(512450, 0.35),
                Bracket(768700, 0.37),
            ]
        )

        self._lt_capital_gain = Schedule(
            [
                Bracket(0, 0.0),
                Bracket(98900, 0.15),
                Bracket(613700, 0.20),
            ]
        )

    def calculate_tax(self, ordinary_income: float, long_term_capital_gains: float):
        # Determine how to apply the standard deduction. It reduced ordinary
        # income and then long-term capital gains. We can use a list of brackets
        # like a tax schedule for this calculation.
        deduction_schedule = Schedule([Bracket(0, 1), Bracket(ordinary_income, 1)]).apply(
            float(STANDARD_DEDUCTION)
        )
        ordinary_income -= deduction_schedule[0]
        long_term_capital_gains -= deduction_schedule[1]

        return sum(self._income_tax_schedule.apply(ordinary_income)) + sum(
            self._lt_capital_gain.apply(long_term_capital_gains)
        )


@dataclasses.dataclass()
class AlternativeMinimumTaxSystem:
    def __post_init__(self):
        self._income_tax_schedule = Schedule(
            [
                Bracket(0, 0.26),
                Bracket(244500, 0.28),
            ]
        )
        self._lt_capital_gain = Schedule(
            [
                Bracket(0, 0.15),
                Bracket(98900, 0.15),
                Bracket(613700, 0.20),
            ]
        )

    def calculate_tax(self, ordinary_income: float, long_term_capital_gains: float):
        return sum(self._income_tax_schedule.apply(ordinary_income)) + sum(
            self._lt_capital_gain.apply(long_term_capital_gains)
        )


if __name__ == "__main__":
    amt = Schedule(
        [
            Bracket(0, 0.26),
            Bracket(244500, 0.28),
        ]
    )

    rts = Schedule(
        [
            Bracket(0, 0.10),
            Bracket(24800, 0.12),
            Bracket(100800, 0.22),
            Bracket(211400, 0.24),
            Bracket(403550, 0.32),
            Bracket(512450, 0.35),
            Bracket(768700, 0.37),
        ]
    )

    import dacite
    import yaml

    with open("isos.yaml") as iso_file:
        equity_dict = yaml.safe_load(iso_file)

    isos: typing.Dict[str, IncentiveStockOption] = {}
    rsus: typing.Dict[str, RestrictedStockUnit] = {}

    fmv = 10.94

    for equity in equity_dict:
        equity_class = equity.pop("class")
        if equity_class == "ISO":
            equity["fmv"] = fmv
            isos[equity["uid"]] = dacite.from_dict(
                IncentiveStockOption, equity, config=dacite.Config(type_hooks={Decimal: Decimal})
            )
        if equity_class == "RSU":
            equity["vest_fmv"] = 50
            rsus[equity["uid"]] = dacite.from_dict(
                RestrictedStockUnit, equity, config=dacite.Config(type_hooks={Decimal: Decimal})
            )

    import pandas as pd

    DATE_COLS = ["grant_date", "exercise_date", "sale_date"]

    iso_df = pd.DataFrame(isos.values())
    iso_df[DATE_COLS] = iso_df[DATE_COLS].apply(pd.to_datetime, errors="coerce")

    iso_df["bargain_element"] = iso_df.apply(lambda row: isos[row["uid"]].bargain_element, axis=1)
    iso_df["exercise_cost"] = iso_df.apply(lambda row: isos[row["uid"]].exercise_cost, axis=1)
    iso_df["proceeds"] = iso_df.apply(lambda row: isos[row["uid"]].proceeds, axis=1)
    iso_df["amt_gain"] = iso_df.apply(lambda row: isos[row["uid"]].amt_gain, axis=1)
    iso_df["net_income"] = iso_df.apply(lambda row: isos[row["uid"]].net_income, axis=1)
    iso_df["disposition"] = iso_df.apply(lambda row: isos[row["uid"]].disposition, axis=1)

    print(iso_df)
    print()

    RSU_DATE_COLS = ["grant_date", "vest_date", "sale_date"]
    rsu_df = pd.DataFrame(rsus.values())
    rsu_df[RSU_DATE_COLS] = rsu_df[RSU_DATE_COLS].apply(pd.to_datetime, errors="coerce")
    rsu_df["compensation_income"] = rsu_df.apply(
        lambda row: rsus[row["uid"]].compensation_income, axis=1
    )
    print(rsu_df)
    print()

    rts = RegularTaxSystem()
    amt = AlternativeMinimumTaxSystem()

    for year in (2026, 2027):
        # Calculate capital gains
        mask = [True] * len(iso_df)
        mask &= iso_df["sale_date"].apply(lambda x: x.year) == year
        mask &= iso_df["disposition"] == Disposition.QUALIFYING
        capital_gains = iso_df[mask]["net_income"].sum()

        # Calculate income
        mask = [True] * len(iso_df)
        mask &= iso_df["sale_date"].apply(lambda x: x.year) == year
        mask &= iso_df["disposition"] == Disposition.DISQUALIFYING
        income = iso_df[mask]["net_income"].sum()

        # Calculate Exercie cost
        mask = [True] * len(iso_df)
        mask &= iso_df["exercise_date"].apply(lambda x: x.year) == year
        exercise_cost = iso_df[mask]["exercise_cost"].sum()

        # Calculate the AMT contribution
        mask &= iso_df["sale_date"].apply(lambda x: x.year) == year
        bargain_elements = iso_df[mask]["bargain_element"].sum()

        mask = [True] * len(rsu_df)
        mask &= rsu_df["vest_date"].apply(lambda x: x.year) == year
        income += rsu_df[mask]["compensation_income"].sum()

        income += Decimal(250000)

        amt_income = income + bargain_elements

        print(year)
        print(f"Exercise Cost:\t\t${float(exercise_cost):,.2f}")
        print(f"Taxable Income:\t\t${float(income):,.2f}")
        print(f"Capital Gains:\t\t${float(capital_gains):,.2f}")
        print(f"Regular Tax:\t\t${rts.calculate_tax(float(income), float(capital_gains)):,.2f}")
        print(f"Bargain Elements:\t${float(bargain_elements):,.2f}")
        print(f"AMT Income:\t\t${float(amt_income):,.2f}")
        print(f"AMT Tax:\t\t${amt.calculate_tax(float(income - MAX_AMT_EXEMPTION), float(capital_gains)):,.2f}")
        print()
