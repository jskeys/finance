import dataclasses
import enum
import logging
import typing
from datetime import datetime
from decimal import Decimal

import dacite
import yaml
from dateutil import parser

from .core import ONE_YEAR, ZERO, to_decimal

_logger = logging.getLogger(__name__)


class ISODisposition(enum.Enum):
    NONE = "NONE"
    QUALIFYING = "QUALIFYING"
    DISQUALIFYING = "DISQUALIFYING"


@dataclasses.dataclass(frozen=True)
class IncentiveStockOption:
    uid: str
    num_shares: int
    grant_date: datetime
    strike_price: Decimal
    exercise_date: typing.Optional[datetime] = None
    fair_market_value: typing.Optional[Decimal] = None
    sale_date: typing.Optional[datetime] = None
    sale_price: typing.Optional[Decimal] = None

    def __post_init__(self):
        """Validate instantiation and quantize Decimal fields."""
        if self.exercise_date is not None and self.fair_market_value is None:
            raise ValueError("Must set `fair_market_value` and `exercise_date` together.")

        if self.sale_date is not None and self.sale_price is None:
            raise ValueError("Must set `sale_price` and `sale_date` together")

        if self.sale_date is not None and self.exercise_date is None:
            raise ValueError("Cannot set `sale_date` without setting `exercise_date`")

        for attr in ("fair_market_value", "strike_price", "sale_price"):
            if getattr(self, attr) is not None:
                value = to_decimal(getattr(self, attr))
                object.__setattr__(self, attr, value)

    @property
    def exercise_gain(self) -> Decimal:
        """Spread at exercise (AMT bargain element)."""
        if self.fair_market_value is not None:
            return max(ZERO, self.fair_market_value - self.strike_price) * self.num_shares

        return Decimal("NaN")

    @property
    def exercise_cost(self) -> Decimal:
        """
        Spread at exercise (AMT bargain element).
        """
        return self.strike_price * self.num_shares

    @property
    def realized_gain(self) -> Decimal:
        """
        Total economic gain (or loss) from exercise to sale.
        """
        if self.sale_price is not None:
            return (self.sale_price - self.strike_price) * self.num_shares

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
        date: datetime,
        fair_market_value: Decimal,
        num_shares: typing.Optional[int] = None,
    ) -> typing.Tuple[
        typing.Optional["IncentiveStockOption"],
        typing.Optional["IncentiveStockOption"],
    ]:
        """Exercise `num_shares` shares.

        If `None`, all shares are exercised. If

        """
        if self.exercise_date is not None:
            raise ValueError(f"Option {self.uid} is already exercised.")

        # All shares are exercised. There is nothing left to return.
        if (num_shares is None) or (num_shares == self.num_shares):
            return (
                dataclasses.replace(
                    self,
                    exercise_date=date,
                    fair_market_value=fair_market_value,
                ),
                None,
            )

        if num_shares > self.num_shares:
            raise ValueError(
                "Tried to exercise {num_shares} but ISO {iso.uid} only has {self.num_shares}"
                + " exercisable shares."
            )

        if num_shares < 0:
            raise ValueError("Must exercise more than zero shares.")

        # Allow this to make life easier on clients.
        if num_shares == 0:
            _logger.debug(f"Requested to exercise 0 shares from ISO {self.uid}.")
            return (
                None,
                dataclasses.replace(self),
            )

        # Split the option into an exercised and non-exercised instances. Keep the `uid`, `grant_date`,
        # `num_shares`, and `strike_price` constant.
        return (
            # What was exercised
            dataclasses.replace(
                self,
                num_shares=num_shares,
                exercise_date=date,
                fair_market_value=fair_market_value,
            ),
            # What is left
            dataclasses.replace(
                self,
                num_shares=self.num_shares - num_shares,
            ),
        )

    def sell(
        self,
        date: datetime,
        price: Decimal,
        num_shares: typing.Optional[int] = None,
    ) -> typing.Tuple[
        typing.Optional["IncentiveStockOption"],
        typing.Optional["IncentiveStockOption"],
    ]:
        """Sell `num_shares` shares.

        Pass `num_shares=None` (default) to sell all shares.


        """
        if self.sale_date is not None:
            raise ValueError(f"Option {self.uid} is already sold.")

        if (num_shares is None) or (num_shares == self.num_shares):
            return (
                dataclasses.replace(
                    self,
                    sale_date=date,
                    sale_price=price,
                ),
                None,
            )

        if num_shares > self.num_shares:
            raise ValueError(
                "Tried to sell {num_shares} but ISO {iso.uid} only has {self.num_shares} sellable"
                + " shares."
            )

        if num_shares < 0:
            raise ValueError("Must sell zero or more shares.")

        if num_shares == 0:
            _logger.debug(f"Requested to sell 0 shares from ISO {self.uid}.")
            return (None, dataclasses.replace(self))

        # Split the option into an sold and non-sold instances. Keep the `uid`, `grant_date`,
        # `num_shares`, and `strike_price` constant.
        return (
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
        )


@dataclasses.dataclass(frozen=True)
class RestrictedStockUnit:
    uid: str
    num_shares: int
    grant_date: datetime
    vest_date: datetime
    vest_fair_market_value: typing.Optional[Decimal] = None
    sale_price: typing.Optional[Decimal] = None
    sale_date: typing.Optional[datetime] = None

    def __post_init__(self):
        """Quantize currency values using `CURRENCY_EPSILON`."""
        for attr in ("vest_fair_market_value", "sale_price"):
            if getattr(self, attr) is not None:
                value = to_decimal(getattr(self, attr))
                object.__setattr__(self, attr, value)

        if (self.sale_price is None) ^ (self.sale_date is None):
            raise ValueError(
                "Only one of `sale_price` and `sale_date` was set for RSU" + f"`{self.uid}`."
            )

    @property
    def rsu_basis(self) -> Decimal:
        """
        Total economic gain (or loss) from exercise to sale.
        """
        if self.vest_fair_market_value is not None:
            return self.vest_fair_market_value * self.num_shares

        return Decimal("NaN")

    @property
    def proceeds(self) -> Decimal:
        """
        Total economic gain (or loss) from exercise to sale.
        """
        if self.sale_date is not None and self.sale_price is not None:
            return self.sale_price * self.num_shares

        return Decimal("NaN")

    @property
    def capital_gain(self) -> Decimal:
        """
        Total economic gain (or loss) from exercise to sale.
        """
        if (
            self.sale_date is not None
            and self.sale_price is not None
            and self.vest_fair_market_value is not None
        ):
            return (self.sale_price - self.vest_fair_market_value) * self.num_shares

        return Decimal("NaN")


def import_isos_from_yaml(file: typing.IO[str]) -> typing.List[IncentiveStockOption]:

    equity_dict = yaml.safe_load(file)
    isos: typing.List[IncentiveStockOption] = []

    for equity in equity_dict:
        if equity.pop("class") == "ISO":
            _logger.info(f"Reading ISO `{equity['uid']}`.")
            isos.append(
                dacite.from_dict(
                    IncentiveStockOption,
                    equity,
                    config=dacite.Config(
                        cast=[Decimal],
                        type_hooks={datetime: lambda x: parser.parse(str(x))},
                    ),
                )
            )

    return isos


def import_rsus_from_yaml(file: typing.IO[bytes]) -> typing.List[RestrictedStockUnit]:

    equity_dict = yaml.safe_load(file)
    rsus: typing.List[RestrictedStockUnit] = []

    for equity in equity_dict:
        if equity.pop("class") == "RSU":
            _logger.info(f"Reading RSU `{equity['uid']}`.")
            rsus.append(
                dacite.from_dict(
                    RestrictedStockUnit,
                    equity,
                    config=dacite.Config(
                        cast=[Decimal],
                        type_hooks={datetime: lambda x: parser.parse(str(x))},
                    ),
                )
            )

    return rsus
