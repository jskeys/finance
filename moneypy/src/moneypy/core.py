"""Common financial formulas."""

from __future__ import annotations

import dataclasses
import operator
import typing
from decimal import ROUND_HALF_EVEN, Decimal

import numpy as np
import numpy.typing as npt
from dateutil.relativedelta import relativedelta

CURRENCY_EPSILON = Decimal("1.00")
ONE_YEAR = relativedelta(years=1)
ROUNDING_STRATEGY = ROUND_HALF_EVEN
ZERO = Decimal(0)

DecimalLike = typing.Union[int, float, str, Decimal]


def calc_annuity(
    rate_per_period: npt.ArrayLike,
    periods: float = 360.0,
) -> npt.NDArray[np.floating]:
    """
    Calculate the annuity factor for a fixed-rate loan.

    This returns the multiplier such that:

        payment = principal * annuity

    Parameters are broadcast according to NumPy rules.
    """
    rate = np.asarray(rate_per_period, dtype=float)

    # Handle zero-interest case explicitly
    return np.where(
        rate == 0,
        1 / periods,
        rate / (1 - np.power(1 + rate, -periods)),
    )


def to_decimal(value: DecimalLike):
    if not isinstance(value, Decimal):
        value = Decimal(str(value))

    return value.quantize(CURRENCY_EPSILON, rounding=ROUNDING_STRATEGY)


@dataclasses.dataclass(frozen=True)
class VectorTuple:
    """Mixin providing element-wise arithmetic for dataclasses."""

    def _apply(self, other, op):
        cls = type(self)

        if isinstance(other, cls):
            values = (
                op(getattr(self, f.name), getattr(other, f.name)) for f in dataclasses.fields(self)
            )
        else:
            values = (op(getattr(self, f.name), other) for f in dataclasses.fields(self))

        return cls(*values)

    def __add__(self, other):
        return self._apply(other, operator.add)

    def __sub__(self, other):
        return self._apply(other, operator.sub)

    def __mul__(self, other):
        return self._apply(other, operator.mul)

    def __truediv__(self, other):
        return self._apply(other, operator.truediv)

    def __iter__(self):
        for field in dataclasses.fields(self):
            yield (getattr(self, field.name))
