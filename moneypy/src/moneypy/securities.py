import dataclasses
import enum
import typing
from datetime import date
from decimal import Decimal

from .core import ONE_YEAR, ZERO, to_decimal, DecimalLike


class ISODisposition(enum.Enum):
    NONE = "NONE"
    QUALIFYING = "QUALIFYING"
    DISQUALIFYING = "DISQUALIFYING"


@dataclasses.dataclass(frozen=True)
class IncentiveStockOption:
    uid: str
    num_shares: int
    grant_date: date
    exercise_price: Decimal
    exercise_date: typing.Optional[date] = None
    fair_market_value: typing.Optional[Decimal] = None
    sale_date: typing.Optional[date] = None
    sale_price: typing.Optional[Decimal] = None

    def __post_init__(self):
        """Validate instantiation and quantize Decimal fields."""
        if self.exercise_date is not None and self.fair_market_value is None:
            raise ValueError("Must set `fair_market_value` and `exercise_date` together.")

        if self.sale_date is not None and self.sale_price is None:
            raise ValueError("Must set `sale_price` and `sale_date` together")

        if self.sale_date is not None and self.exercise_date is None:
            raise ValueError("Cannot set `sale_date` without setting `exercise_date`")

        for attr in ("fair_market_value", "exercise_price", "sale_price"):
            if getattr(self, attr) is not None:
                value = to_decimal(getattr(self, attr))
                object.__setattr__(self, attr, value)

    @property
    def bargain_element(self) -> Decimal:
        """Spread at exercise (AMT bargain element)."""
        if self.fair_market_value is not None:
            return max(ZERO, self.fair_market_value - self.exercise_price) * self.num_shares

        return Decimal("NaN")

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
        """Get the sale proceeds."""
        if self.sale_price is not None:
            return self.sale_price * self.num_shares

        return Decimal("NaN")

    @property
    def amt_gain(self) -> Decimal:
        """
        Total economic gain (or loss) from exercise to sale.
        """
        if self.sale_price is not None and self.fair_market_value is not None:
            return (self.sale_price - self.fair_market_value) * self.num_shares

        return Decimal("NaN")

    @property
    def disposition(self) -> ISODisposition:
        """
        Determine ISO disposition type.

        Qualifying disposition requires BOTH:
          - Sale ≥ 1 year after exercise, AND
          - Sale ≥ 2 years after grant
        """
        if self.sale_date is None or self.exercise_date is None:
            return ISODisposition.NONE

        if (self.sale_date >= (self.exercise_date + ONE_YEAR)) and (
            self.sale_date >= (self.grant_date + 2 * ONE_YEAR)
        ):
            return ISODisposition.QUALIFYING

        return ISODisposition.DISQUALIFYING

    def exercise(
        self,
        date: date,
        fair_market_value: Decimal,
        num_shares: typing.Optional[int],
    ) -> typing.List["IncentiveStockOption"]:
        """Exercise `num_shares` shares.

        If `None`, all shares are exercised. If

        """
        if self.exercise_date is not None:
            raise ValueError(f"Option {self.uid} is already exercised.")

        if (num_shares is None) or (num_shares == self.num_shares):
            return [
                dataclasses.replace(
                    self,
                    exercise_date=date,
                    fair_market_value=fair_market_value,
                )
            ]

        # Split the option into an exercised and non-exercised part. Keep the `uid`, `grant_date`,
        # `num_shares`, and `exercise_price` constant.
        if num_shares <= 0:
            raise ValueError("Must exercise more than zero shares.")

        return [
            dataclasses.replace(
                self,
                num_shares=num_shares,
                exercise_date=date,
                fair_market_value=fair_market_value,
            ),
            dataclasses.replace(
                self,
                num_shares=self.num_shares - num_shares,
            ),
        ]

    def sell(
        self,
        date: date,
        price: Decimal,
        num_shares: typing.Optional[int],
    ) -> typing.List["IncentiveStockOption"]:
        """Exercise `num_shares` shares.

        If `None`, all shares are exercised. If

        """
        if self.sale_date is not None:
            raise ValueError(f"Option {self.uid} is already sold.")

        if (num_shares is None) or (num_shares == self.num_shares):
            return [
                dataclasses.replace(
                    self,
                    sale_date=date,
                    sale_price=price,
                )
            ]

        if num_shares <= 0:
            raise ValueError("Must sell more than zero shares.")

        # Split the option into an exercised and non-exercised part. Keep the `uid`, `grant_date`,
        # `num_shares`, and `exercise_price` constant.
        return [
            dataclasses.replace(
                self,
                num_shares=num_shares,
                sale_date=date,
                sale_price=price,
            ),
            dataclasses.replace(
                self,
                num_shares=self.num_shares - num_shares,
            ),
        ]


@dataclasses.dataclass(frozen=True)
class RestrictedStockUnit:
    uid: str
    num_shares: int
    grant_date: date
    vest_date: typing.Optional[date] = None
    vest_fair_market_value: typing.Optional[Decimal] = None
    sale_price: typing.Optional[Decimal] = None
    sale_date: typing.Optional[date] = None

    def __post_init__(self):
        """Quantize currency values using `CURRENCY_EPSILON`."""
        for attr in ("vest_fair_market_value", "sale_price"):
            if getattr(self, attr) is not None:
                value = to_decimal(getattr(self, attr))
                object.__setattr__(self, attr, value)

    @property
    def compensation_income(self) -> Decimal:
        """
        Total economic gain (or loss) from exercise to sale.
        """
        if self.vest_fair_market_value is not None:
            return self.vest_fair_market_value * self.num_shares

        return Decimal("NaN")


if __name__ == "__main__":
    iso = IncentiveStockOption("test", 1000, date.today(), Decimal(0.55))
    isos = iso.exercise(date.today(), Decimal(10.00), 250)
    print(isos[0].sell(date.today(), Decimal(20), 100))
