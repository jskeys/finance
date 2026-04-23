import logging
from decimal import Decimal

from moneypy.core import to_currency
from moneypy.tax import FICATaxSystem, Income


def test_fica_tax_over_ss_limit():

    fica_tax_system = FICATaxSystem()
    fica_tax_summary = fica_tax_system.calculate_tax(2026, Income(ordinary=230_000))
    assert fica_tax_summary.tax == to_currency(184_500 * 0.062 + 230_000 * 0.0145)


def test_fica_tax_over_medicare_limit():

    fica_tax_system = FICATaxSystem()
    fica_tax_summary = fica_tax_system.calculate_tax(2026, Income(ordinary=300_000))
    assert fica_tax_summary.tax == to_currency(184_500 * 0.062 + 250_000 * 0.0145 + 50_000 * 0.0235)


def test_fica_tax_under_ss_limit():

    fica_tax_system = FICATaxSystem()
    fica_tax_summary = fica_tax_system.calculate_tax(2026, Income(ordinary=150_000))
    assert fica_tax_summary.tax == to_currency(150_000 * 0.062 + 150_000 * 0.0145)
