import abc
import dataclasses
import logging
import typing
from decimal import Decimal

from .core import VectorTuple, ZERO, to_decimal, ONE_YEAR
from .securities import IncentiveStockOption, ISODisposition, RestrictedStockUnit

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

    brackets: typing.Sequence[Bracket]

    def __post_init__(self):
        """Sort tax brackets once."""
        object.__setattr__(self, "brackets", sorted(self.brackets))

    def apply(self, income: Decimal) -> typing.Sequence[Decimal]:
        """Calculate the tax."""
        bracket_tax: typing.Sequence[Decimal] = []

        lowers = [bracket.threshold for bracket in self.brackets]
        uppers = lowers[1:] + [Decimal("Infinity")]

        for bracket, upper in zip(self.brackets, uppers):
            bracket_income = max(ZERO, min(upper, income) - bracket.threshold)
            bracket_tax.append(bracket_income * bracket.rate)

        return bracket_tax


@dataclasses.dataclass(frozen=True)
class TaxSummary:
    income: Decimal
    tax: Decimal


class TaxSystem(abc.ABC):
    def calculate_tax(
        self,
        year: int,
        income: Income,
        isos: typing.Optional[typing.Sequence[IncentiveStockOption]] = None,
        rsus: typing.Optional[typing.Sequence[RestrictedStockUnit]] = None,
        tax_credits: Decimal = ZERO,
    ):
        _logger.info("Calculating %s for %d", type(self).__name__, year)
        if isos is not None:
            income += self._process_isos(isos, year)

        if rsus is not None:
            income += self._process_rsus(rsus, year)

        taxable_income = income - self._calc_deduction(income)

        income_tax = Income(
            sum(self.ordinary_income_schedule.apply(taxable_income.ordinary)),
            sum(self.ltcg_income_schedule.apply(sum(taxable_income)))
            - sum(self.ltcg_income_schedule.apply(taxable_income.ordinary)),
        )

        income_tax = sum(income_tax)

        _logger.info(f"Total tax: {income_tax:,.2f}")
        _logger.info(f"Tax rate: {100 * income_tax / sum(income):.2f} %")

        return TaxSummary(sum(income), income_tax)

    @property
    @abc.abstractmethod
    def ordinary_income_schedule(self) -> Schedule:
        pass

    @property
    @abc.abstractmethod
    def ltcg_income_schedule(self) -> Schedule:
        pass

    @abc.abstractmethod
    def _process_isos(self, isos: typing.Sequence[IncentiveStockOption], year: int) -> Income:
        pass

    @abc.abstractmethod
    def _calc_deduction(self, income: Income) -> Income:
        pass

    @staticmethod
    def _process_rsus(rsus: typing.Sequence[RestrictedStockUnit], year: int) -> Income:
        income = Income()

        _logger.info(f"Processing RSUs for tax year {year}.")
        for rsu in rsus:
            _logger.info(f"Processing RSU {rsu.uid}")
            if rsu.vest_date.year == year:
                _logger.info("+$%s RSU BASIS to OI", f"{rsu.rsu_basis:,.2f}")
                income += Income(ordinary=rsu.rsu_basis)

            if rsu.sale_date and rsu.sale_date.year == year:
                if rsu.sale_date > rsu.grant_date + ONE_YEAR:
                    income += Income(ltcg=rsu.capital_gain)
                    _logger.info("+$%s CAPITAL GAIN to LCTG", f"{rsu.capital_gain:,.2f}")
                else:
                    income += Income(ordinary=rsu.capital_gain)
                    _logger.info("+$%s CAPITAL GAIN to OI", f"{rsu.capital_gain:,.2f}")

        return income


@dataclasses.dataclass(frozen=True)
class RegularTaxSystem(TaxSystem):
    @property
    def ordinary_income_schedule(self) -> Schedule:
        return Schedule(
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

    @property
    def ltcg_income_schedule(self) -> Schedule:
        return Schedule(
            [
                Bracket(0, 0.0),
                Bracket(98900, 0.15),
                Bracket(613700, 0.20),
            ]
        )

    def _calc_deduction(self, income: Income) -> Income:
        """Apply the standard deduction against ordinary income then ltcg_income."""
        STANDARD_DEDUCTION = Decimal(32200)

        # Determine how to apply the standard deduction. It reduces ordinary
        # income and then long-term capital gains. We can use a list of brackets
        # like a tax schedule for this calculation. Pretty clever.
        deduction_schedule = Schedule(
            [
                Bracket(ZERO),
                Bracket(income.ordinary),
            ]
        ).apply(STANDARD_DEDUCTION)

        return Income(*deduction_schedule)

    @staticmethod
    def _process_isos(isos: typing.Sequence[IncentiveStockOption], year: int) -> Income:
        income = Income()

        _logger.info(f"Processing ISOs for tax year {year}.")
        for iso in isos:
            if iso.sale_date is None or iso.sale_date.year != year:
                continue

            _logger.info(f"Processing ISO {iso.uid}")
            if iso.disposition == ISODisposition.DISQUALIFYING:
                income += Income(iso.net_income)
                _logger.info(f"+${iso.net_income:,.2f} NET_INCOME to OI.")
            if iso.disposition == ISODisposition.QUALIFYING:
                income += Income(ltcg=iso.net_income)
                _logger.info(f"+${iso.net_income:,.2f} NET_INCOME to LTCG.")

        _logger.info("ISO Income: %s", income)
        return income


@dataclasses.dataclass(frozen=True)
class AlternativeMinimumTaxSystem(TaxSystem):
    @property
    def ordinary_income_schedule(self) -> Schedule:
        return Schedule(
            [
                Bracket(0, 0.26),
                Bracket(244500, 0.28),
            ]
        )

    @property
    def ltcg_income_schedule(self) -> Schedule:
        return Schedule(
            [
                Bracket(0, 0.0),
                Bracket(98900, 0.15),
                Bracket(613700, 0.20),
            ]
        )

    def _calc_deduction(self, income: Income) -> Income:
        """Apply the standard deduction against ordinary income then ltcg_income."""
        MAX_EXEMPTION = Decimal("140_200")
        PHASEOUT_RATE = Decimal("0.5")
        PHASEOUT_THRESHOLD = Decimal("1_000_000")

        amount_above_threshold = max(ZERO, sum(income) - PHASEOUT_THRESHOLD)
        reduction = min(amount_above_threshold * PHASEOUT_RATE, MAX_EXEMPTION)
        exemption = max(0, MAX_EXEMPTION - reduction)

        exemptions = Income(
            *Schedule(
                [
                    Bracket(ZERO),
                    Bracket(income.ordinary),
                ]
            ).apply(exemption)
        )

        _logger.info("AMT Exemption: %s", exemptions)

        return exemptions

    @staticmethod
    def _process_isos(isos: typing.Sequence[IncentiveStockOption], year: int) -> Income:
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
            # CASE A:
            # If the ISO has yet to be exercised, there are no tax considerations.
            if iso.exercise_date is None:
                continue

            # CASE B:
            # If there is no sale in the same year, then increase ordinary income by bargain element
            if iso.sale_date is None or iso.sale_date.year != year:
                if iso.exercise_date.year == year:
                    income += Income(iso.bargain_element)
                    _logger.info(f"+${iso.bargain_element:,.2f} BARGAIN ELEMENT to OI.")
                continue

            if iso.sale_date.year == year and iso.exercise_date.year == year:
                _logger.info(f"+${iso.net_income:,.2f} NET INCOME to OI.")
                income += Income(iso.net_income)
                continue

            if iso.sale_date.year == year:
                if iso.disposition == ISODisposition.DISQUALIFYING:
                    income += Income(ordinary=iso.amt_gain)
                    _logger.info(f"+${iso.amt_gain:,.2f} AMT GAIN to OI.")
                if iso.disposition == ISODisposition.QUALIFYING:
                    income += Income(ltcg=iso.amt_gain)
                    _logger.info(f"+${iso.amt_gain:,.2f} AMT GAIN to LTCG.")

        return income
