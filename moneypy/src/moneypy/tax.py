import dataclasses
import logging
import typing
from decimal import Decimal

from .core import VectorTuple, ZERO, to_decimal
from .securities import IncentiveStockOption, ISODisposition

_logger = logging.getLogger(__spec__.name)


@dataclasses.dataclass(frozen=True)
class Income(VectorTuple):
    ordinary: Decimal = ZERO
    ltcg: Decimal = ZERO

    def __repr__(self):
        return ", ".join(
            [
                f"{field.name}: ${getattr(self, field.name):,.2f}"
                for field in dataclasses.fields(self)
            ]
        )


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
    ORDINARY_INCOME_SCHEDULE = Schedule(
        [
            Bracket(Decimal(0), Decimal(0.10)),
            Bracket(Decimal(24_800), Decimal(0.12)),
            Bracket(Decimal(100_800), Decimal(0.22)),
            Bracket(Decimal(211_400), Decimal(0.24)),
            Bracket(Decimal(403_550), Decimal(0.32)),
            Bracket(Decimal(512_450), Decimal(0.35)),
            Bracket(Decimal(768_700), Decimal(0.37)),
        ]
    )
    LTCG_INCOME_SCHEDULE = Schedule(
        [
            Bracket(0, 0.0),
            Bracket(98900, 0.15),
            Bracket(613700, 0.20),
        ]
    )

    def calculate_tax(self, w2_income: Decimal, isos: typing.List[IncentiveStockOption], year: int):
        income = Income(ordinary=w2_income)

        income += self._process_isos(isos, year)
        _logger.info(f"Gross Income: {income}.")
        _logger.info(f"Total Income: $ {sum(income, ZERO):,.2f}.")

        income -= self._calc_deduction(income)
        _logger.info(f"Deducted Income: {income}.")
        _logger.info(f"Deducted Total Income: $ {sum(income, ZERO):,.2f}.")

        ordinary_income_tax = sum(self.ORDINARY_INCOME_SCHEDULE.apply(income.ordinary))
        ltcg_income_tax = sum(self.LTCG_INCOME_SCHEDULE.apply(income.ordinary + income.ltcg)) - sum(
            self.LTCG_INCOME_SCHEDULE.apply(income.ordinary)
        )

        income_tax = ordinary_income_tax + ltcg_income_tax

        _logger.info(f"Total tax: {income_tax:,.2f}")
        _logger.info(f"Tax rate: {100 * income_tax / sum(income):.2f} %")

        return income_tax

    def _calc_deduction(self, income: Income) -> Income:
        """Apply the standard deduction against ordinary income then ltcg_income."""

        # Determine how to apply the standard deduction. It reduces ordinary
        # income and then long-term capital gains. We can use a list of brackets
        # like a tax schedule for this calculation. Pretty clever.
        deduction_schedule = Schedule(
            [
                Bracket(ZERO),
                Bracket(income.ordinary),
            ]
        ).apply(self.STANDARD_DEDUCTION)

        return Income(*deduction_schedule)

    @staticmethod
    def _process_isos(
        isos: typing.List[IncentiveStockOption], year: int
    ) -> typing.Tuple[Decimal, Decimal]:
        income = Income()

        _logger.info(f"Processing ISOs for tax year {year}.")
        for iso in isos:
            _logger.debug(f"Processing ISO {iso.uid}")
            if iso.sale_date is None or iso.sale_date.year != year:
                continue

            if iso.disposition == ISODisposition.DISQUALIFYING:
                income += Income(iso.net_income)
                _logger.info(f"Added ${iso.net_income:,.2f} to ordinary income.")
            if iso.disposition == ISODisposition.QUALIFYING:
                income += Income(ltcg=iso.net_income)
                _logger.info(f"Added ${iso.net_income:,.2f} to long-term capital gains.")

        return income


@dataclasses.dataclass()
class AlternativeMinimumTaxSystem:
    MAX_EXEMPTION = Decimal("140_200")
    PHASEOUT_RATE = Decimal("0.5")
    PHASEOUT_THRESHOLD = Decimal("1_000_000")
    ORDINARY_INCOME_SCHEDULE = Schedule(
        [
            Bracket(0, 0.26),
            Bracket(244500, 0.28),
        ]
    )
    LTCG_INCOME_SCHEDULE = Schedule(
        [
            Bracket(0, 0.0),
            Bracket(98900, 0.15),
            Bracket(613700, 0.20),
        ]
    )

    def calculate_tax(self, w2_income: Decimal, isos: typing.List[IncentiveStockOption], year: int):
        income = Income(ordinary=w2_income)

        income += self._process_isos(isos, year)
        _logger.info(f"Gross Income: {income}.")
        _logger.info(f"Total Income: $ {sum(income, ZERO):,.2f}.")

        income -= self._calc_deduction(income)
        _logger.info(f"Deducted Income: {income}.")
        _logger.info(f"Deducted Total Income: $ {sum(income, ZERO):,.2f}.")

        ordinary_income_tax = sum(self.ORDINARY_INCOME_SCHEDULE.apply(income.ordinary))
        ltcg_income_tax = sum(self.LTCG_INCOME_SCHEDULE.apply(income.ordinary + income.ltcg)) - sum(
            self.LTCG_INCOME_SCHEDULE.apply(income.ordinary)
        )

        income_tax = ordinary_income_tax + ltcg_income_tax

        _logger.info(f"Total tax: {income_tax:,.2f}")
        _logger.info(f"Tax rate: {100 * income_tax / sum(income):.2f} %")

        return income_tax

    def _calc_deduction(self, income: Income) -> Income:
        """Apply the standard deduction against ordinary income then ltcg_income."""

        amount_above_threshold = max(ZERO, income.ordinary - self.PHASEOUT_THRESHOLD)
        reduction = min(amount_above_threshold * self.PHASEOUT_RATE, self.MAX_EXEMPTION)

        _logger.info(f"AMT Exemption: {self.MAX_EXEMPTION - reduction}")

        return Income(self.MAX_EXEMPTION - reduction)

    @staticmethod
    def _process_isos(
        isos: typing.List[IncentiveStockOption], year: int
    ) -> typing.Tuple[Decimal, Decimal]:
        income = Income()

        _logger.info(f"Processing ISOs for tax year {year}.")
        for iso in isos:
            _logger.debug(f"Processing ISO {iso.uid}")

            # Exercise Date   | 0 | 1 | 0 | 1 |
            # Sale Date       | 0 | 0 | 1 | 1 |
            # ---------------------------------
            # Event           | a | b | c | d |
            #
            # 0 = not this year or `None`
            # 1 = this year
            #
            # a. do nothing
            # b. bargain element
            # c. disposition using amt_gain
            # d. ordinary income
            #
            # If the ISO has yet to be exercised, there are no tax considerations.
            if iso.exercise_date is None:
                continue

            # If there is no sale, then increase ordinary income by bargain element (case b)
            if iso.sale_date is None or iso.sale_date.year != year:
                if iso.exercise_date.year == year:
                    income += Income(iso.bargain_element)
                    _logger.info(
                        f"Added ${iso.bargain_element:,.2f} bargain element to ordinary income."
                    )
                continue

            if (iso.sale_date.year == year) and (iso.exercise_date.year) == year:
                _logger.info(f"Added ${iso.net_income:,.2f} net income to ordinary income.")
                income += Income(iso.net_income)
                continue

            if iso.sale_date.year == year:
                if iso.disposition == ISODisposition.DISQUALIFYING:
                    income += Income(ordinary=iso.amt_gain)
                    _logger.info(f"Added ${iso.amt_gain:,.2f} amt gain to ordinary income.")
                if iso.disposition == ISODisposition.QUALIFYING:
                    income += Income(ltcg=iso.amt_gain)
                    _logger.info(
                        f"Added ${iso.net_income:,.2f} amt gain to long-term capital gains."
                    )

        return income
