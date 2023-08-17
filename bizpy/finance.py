#!/usr/bin/env python3

import abc
import datetime
import pandas

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import List, NamedTuple, Optional

SECONDS_PER_YEAR = 31536000

@dataclass
class Account(abc.ABC):
    value: float = 0

    @abc.abstractmethod
    def debit(self, amount: float):
        pass

    @abc.abstractmethod
    def credit(self, amount: float):
        pass

class AssetAccount(Account):
    def debit(self, amount: float):
        self.value += amount

    def credit(self, amount: float):
        self.value -= amount

@dataclass
class LiabilityAccount(Account):
    def debit(self, amount: float):
        self.value -= amount

    def credit(self, amount: float):
        self.value += amount


@dataclass
class Transaction:
    date: date
    amount: float
    debit_account: Account
    credit_account: Account

    def pv(self, discount_rate, current_date: Optional[date] = None):
        if current_date is None:
            current_datetime = date.today()

        years = (self.date - current_date.total_seconds()) / SECONDS_PER_YEAR

        return self.amount / (1 + discount_rate) ** years

@dataclass
class Ledger:
    # Asset Accounts
    inventory: AssetAccount = field(default_factory=AssetAccount)
    cash: AssetAccount = field(default_factory=AssetAccount)

    # Liability Accounts
    shareholders_equity: LiabilityAccount = field(default_factory=LiabilityAccount)
    accounts_payable: LiabilityAccount = field(default_factory=LiabilityAccount)

class Business:
    def __init__(self):
        self._ledger: Ledger = Ledger()
        self._shares = 0

        # Transactions that have been processed.
        self._journal = []

    def raise_equity(self, shares, amount: float, date: datetime.date):
        self._shares += shares
        self._journal.append(
            Transaction(
                date,
                amount, 
                self._ledger.cash,
                self._ledger.shareholders_equity,
            )
        )

    def purchase_inventory(self, amount: float, purchase_date: datetime, terms: timedelta):
        self._journal.append(
            Transaction(
                purchase_date,
                amount,
                self._ledger.inventory,
                self._ledger.accounts_payable,
            )
        )

        self._journal.append(
            Transaction(
                purchase_date + terms,
                amount,
                self._ledger.accounts_payable,
                self._ledger.cash,
            )
        )

    def process(self, date: Optional[datetime.date] = None):
        for transaction in self._journal:
            transaction.debit_account.debit(transaction.amount)
            transaction.credit_account.credit(transaction.amount)

        self._journal = []