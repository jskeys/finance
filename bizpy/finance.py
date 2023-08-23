#!/usr/bin/env python3

import abc
import datetime
import pandas as pd
import uuid

from collections import UserDict
from dataclasses import dataclass, field
from enum import IntEnum
from typing import List, NamedTuple, Optional, Tuple

SECONDS_PER_YEAR = 31536000


class AccountType(IntEnum):
    # Current Assets
    CASH = 100
    INVENTORY = 101
    ACCOUNTS_RECEIVABLE = 102

    # Current Liabilities
    SHAREHOLDERS_EQUITY = 300
    ACCOUNTS_PAYABLE = 301


class TransactionType(IntEnum):
    DEBIT = 0
    CREDIT = 1


@dataclass
class Transaction:
    id: int
    entry_id: int
    date: datetime.date
    type: TransactionType
    account: AccountType
    amount: float

    def __le__(self, other):
        return self.date <= other.date

    def __lt__(self, other):
        return self.date < other.date


@dataclass
class Account(abc.ABC):
    name: str

    def __post_init__(self):
        self._transactions: List[Transaction] = []

    def post(self, transaction: Transaction):
        self._transactions.append(transaction)

    def _sum_transactions(self, type: TransactionType, date: Optional[datetime.date] = None):
        date = datetime.date.today() if date is None else date

        return sum(
            [
                transaction.amount
                for transaction in self._transactions
                if (transaction.date <= date) and (transaction.type == type)
            ]
        )

    @abc.abstractmethod
    def get_balance(self, date: Optional[datetime.date]):
        pass


class AssetAccount(Account):
    def get_balance(self, date: Optional[datetime.date] = None):
        return self._sum_transactions(TransactionType.DEBIT, date) - self._sum_transactions(
            TransactionType.CREDIT, date
        )


class LiabilityAccount(Account):
    def get_balance(self, date: Optional[datetime.date] = None):
        return self._sum_transactions(TransactionType.CREDIT, date) - self._sum_transactions(
            TransactionType.DEBIT, date
        )


class Business:
    def __init__(self):
        self._shares = 0

        self._ledger = {
            AccountType.CASH: AssetAccount("cash"),
            AccountType.INVENTORY: AssetAccount("inventory"),
            AccountType.ACCOUNTS_PAYABLE: LiabilityAccount("payable"),
            AccountType.ACCOUNTS_RECEIVABLE: AssetAccount("receivable"),
            AccountType.SHAREHOLDERS_EQUITY: LiabilityAccount("shareholders_equity"),
        }

        self._transactions = []

        # Operations
        self._unit_price = 100
        self._unit_cogs = 40

    def raise_equity(self, shares, price_per_share: float, date: datetime.date):
        self._shares += shares
        entry_id = uuid.uuid4()
        self._transactions.append(
            Transaction(
                uuid.uuid4().int,
                entry_id.int,
                datetime.date.today(),
                TransactionType.DEBIT,
                AccountType.CASH,
                shares * price_per_share,
            )
        )
        self._transactions.append(
            Transaction(
                uuid.uuid4().int,
                entry_id.int,
                datetime.date.today(),
                TransactionType.CREDIT,
                AccountType.SHAREHOLDERS_EQUITY,
                shares * price_per_share,
            )
        )

    def buy_inventory(self, amount: float):
        entry_id = uuid.uuid4().int
        self._transactions.append(
            Transaction(
                uuid.uuid4().int,
                entry_id,
                datetime.date.today(),
                TransactionType.DEBIT,
                AccountType.INVENTORY,
                amount,
            )
        )
        self._transactions.append(
            Transaction(
                uuid.uuid4().int,
                entry_id,
                datetime.date.today(),
                TransactionType.CREDIT,
                AccountType.ACCOUNTS_PAYABLE,
                amount,
            )
        )

    def process_transactions(self):
        for transaction in self._transactions:
            self._ledger[transaction.account].post(transaction)


def main():
    business = Business()
    business.raise_equity(50000, 1, datetime.date.today())
    business.raise_equity(150000, 10, datetime.date.today())
    business.buy_inventory(10000)

    business.process_transactions()

    for account_id, account in business._ledger.items():
        print(account_id.name, account.get_balance())


if __name__ == "__main__":
    main()
