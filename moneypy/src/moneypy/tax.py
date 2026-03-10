import dataclasses
import logging
import typing
from decimal import Decimal

from .core import ZERO, to_decimal

_logger = logging.getLogger(__spec__.name)


@dataclasses.dataclass(frozen=True, order=True)
class Bracket:
    """A minium threshold and an associated rate."""

    threshold: Decimal
    rate: Decimal = Decimal("1")

    def __post_init__(self):
        """Convert float to Decimal and quantize."""
        for attr in ("threshold", "rate"):
            object.__setattr__(self, attr, to_decimal(getattr(self, attr)))


@dataclasses.dataclass(frozen=True)
class Schedule:
    """
    A progressive tax schedule composed of ordered marginal tax brackets.

    Each bracket specifies a tax rate that applies to income above its
    threshold. Only the portion of income within a bracket is taxed at
    that bracket's rate.

    Brackets are sorted by threshold during initialization.
    """

    brackets: typing.List[Bracket]

    def __post_init__(self):
        """Sort tax brackets once."""
        object.__setattr__(self, "brackets", sorted(self.brackets))

    def apply(self, income: Decimal) -> typing.List[Decimal]:
        """Calculate the tax."""
        bracket_tax: typing.List[Decimal] = []

        lowers = [bracket.threshold for bracket in self.brackets]
        uppers = lowers[1:] + [Decimal("Infinity")]

        for bracket, upper in zip(self.brackets, uppers):
            bracket_income = max(ZERO, min(upper, income) - bracket.threshold)
            bracket_tax.append(bracket_income * bracket.rate)

        return bracket_tax


@dataclasses.dataclass()
class RegularTaxSystem:
    STANDARD_DEDUCTION = Decimal(32200)

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

    def calculate_tax(self, ordinary_income: Decimal, long_term_capital_gains: Decimal):
        # Determine how to apply the standard deduction. It reduces ordinary
        # income and then long-term capital gains. We can use a list of brackets
        # like a tax schedule for this calculation. Pretty clever.
        deduction_schedule = Schedule(
            [
                Bracket(ZERO),
                Bracket(ordinary_income),
            ]
        ).apply(self.STANDARD_DEDUCTION)

        ordinary_income -= deduction_schedule[0]
        long_term_capital_gains -= deduction_schedule[1]

        return sum(self._income_tax_schedule.apply(ordinary_income)) + sum(
            self._lt_capital_gain.apply(long_term_capital_gains)
        )


@dataclasses.dataclass()
class AlternativeMinimumTaxSystem:
    MAX_EXEMPTION = Decimal("140_200")
    PHASEOUT_RATE = Decimal("0.5")
    PHASEOUT_THRESHOLD = Decimal("1_000_000")

    def __post_init__(self):
        self._income_tax_schedule = Schedule(
            [
                Bracket(0, 0.26),
                Bracket(244500, 0.28),
            ]
        )
        self._lt_capital_gain = Schedule(
            [
                Bracket(0, 0.0),
                Bracket(98900, 0.15),
                Bracket(613700, 0.20),
            ]
        )

    def calculate_exemption(self, ordinary_income: Decimal, long_term_capital_gains: Decimal):
        amount_above_threshold = max(ZERO, ordinary_income - self.PHASEOUT_THRESHOLD)
        reduction = min(amount_above_threshold * self.PHASEOUT_RATE, self.MAX_EXEMPTION)
        _logger.info(f"AMT Exemption: {self.MAX_EXEMPTION - reduction}")
        return self.MAX_EXEMPTION - reduction

    def calculate_tax(self, ordinary_income: Decimal, long_term_capital_gains: Decimal):
        ordinary_income -= self.calculate_exemption(ordinary_income, long_term_capital_gains)

        return sum(self._income_tax_schedule.apply(ordinary_income)) + sum(
            self._lt_capital_gain.apply(long_term_capital_gains)
        )
