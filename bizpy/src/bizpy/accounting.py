#!/usr/bin/env python3

import datetime
import numpy as np
import uuid

from enum import IntEnum
from prettytable import PrettyTable
from typing import List, Optional

SECONDS_PER_YEAR: float = 31536000


class Account(IntEnum):
    # Asset Accounts
    CASH = 100
    INVENTORY = 101
    ACCOUNTS_RECEIVABLE = 102
    OTHER_ASSETS = 103
    PPE = 104
    # Expense Accounts
    GA = 200
    SM = 201
    RD = 202
    # Liability Accounts
    ACCOUNTS_PAYABLE = 301
    RETAINED_EARNINGS = 302
    ACCRUED_EXPENSES = 303
    SHORT_TERM_DEBT = 304
    LONG_TERM_DEBT = 300
    # Equity Accounts
    SHAREHOLDERS_EQUITY = 400
    # Revenue Accounts
    REVENUE = 500


class Transaction:
    def __init__(
        self,
        date: datetime.date,
        account: Account,
        amount: float,
        *,
        group_uuid: Optional[int] = None,
    ):
        self._date = date
        self._account = account
        self._amount = amount
        self._uuid = uuid.uuid4()
        self._group_uuid = group_uuid
        self._processed = False

    def as_dict(self):
        return {
            "date": self._date,
            "account": self._account,
            "amount": self._amount,
            "uuid": self._uuid,
            "group_uuid": self._group_uuid,
            "processed": self._processed,
        }

    def get_date(self):
        return self._date

    def get_amount(self):
        return self._amount

    def get_account(self):
        return self._account

    def get_processed(self):
        return self._processed

    def mark_processed(self):
        self._processed = True

    def __le__(self, other):
        return self._date <= other._date

    def __lt__(self, other):
        return self._date < other._date


class TransactionGroup:
    def __init__(self) -> None:
        self._group_uuid: int = uuid.uuid4().int
        self._transactions: List[Transaction] = []

    def _append_transaction(self, date: datetime.date, account: Account, amount: float) -> None:
        self._transactions.append(Transaction(date, account, amount, group_uuid=self._group_uuid))

    def get_transactions(self) -> List[Transaction]:
        return self._transactions


class CommonStockIssue(TransactionGroup):
    def __init__(self, shares, share_price, date: datetime.date):
        super().__init__()
        self._append_transaction(date, Account.SHAREHOLDERS_EQUITY, shares * share_price)
        self._append_transaction(date, Account.CASH, shares * share_price)


class Payroll(TransactionGroup):
    def __init__(self, date: datetime.date, payroll_expense: float, payroll_checks: float):
        super().__init__()
        self._append_transaction(date, Account.CASH, -1 * payroll_checks)
        self._append_transaction(date, Account.ACCRUED_EXPENSES, payroll_expense - payroll_checks)
        self._append_transaction(date, Account.RETAINED_EARNINGS, payroll_expense)


class Loan(TransactionGroup):
    def __init__(self, amount: float, date: datetime.date):
        super().__init__()
        self._append_transaction(date, Account.SHORT_TERM_DEBT, 100000)
        self._append_transaction(date, Account.LONG_TERM_DEBT, 900000)
        self._append_transaction(date, Account.CASH, 1e6)


class CapitalPurchase(TransactionGroup):
    def __init__(self, date: datetime.date, amount: float):
        super().__init__()
        self._append_transaction(date, Account.CASH, -1 * amount)
        self._append_transaction(date, Account.PPE, amount)


class ProductSale(TransactionGroup):
    def __init__(self, date: datetime.date, revenue: float, cogs: float):
        super().__init__()
        self._append_transaction(date, Account.CASH, revenue)
        self._append_transaction(date, Account.INVENTORY, -1 * cogs)
        self._append_transaction(date, Account.RETAINED_EARNINGS, revenue - cogs)


class Business:
    def __init__(self) -> None:
        self._shares = 0

        self._accounts = {account.value: 0.0 for account in Account}

        self._transactions: List[Transaction] = []
        self._events: List[TransactionGroup] = []

        # Operations
        self._unit_price = 100
        self._unit_cogs = 40

    def add_transaction_group(self, event: TransactionGroup) -> None:
        self._transactions.extend(event.get_transactions())
        self._transactions.sort()

    def process_transactions(self, date: Optional[datetime.date] = None):
        date = date if date is not None else datetime.date.today()

        for transaction in self._transactions:
            if not transaction.get_processed() and transaction.get_date() <= date:
                self._accounts[transaction.get_account()] += transaction.get_amount()
                transaction.mark_processed()

    def get_account_balances(self):
        return self._accounts


def present_value(row):
    periods = (row["date"] - datetime.date.today()).total_seconds() / SECONDS_PER_YEAR
    return row["amount"] / (np.power(1 + row["discount_rate"], periods))


def main():
    today = datetime.date.today()

    # Reinvestment simulation.
    business = Business()
    business.add_transaction_group(CommonStockIssue(100, 1, today))
    business.add_transaction_group(ProductSale(today, 20, 0))
    business.process_transactions()

    account_balances = business.get_account_balances()

    pretty_table = PrettyTable()
    pretty_table.add_column("Account", [Account(key).name for key in account_balances.keys()])
    pretty_table.add_column("Balance", [f"{value:.2f}" for value in account_balances.values()])
    pretty_table.align["Account"] = "l"
    pretty_table.align["Balance"] = "r"

    print(pretty_table)


if __name__ == "__main__":
    main()
