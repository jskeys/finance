"""A simple application for calculating shared expense account balances."""

import logging
import pandas as pd
import uuid
import yaml

from decimal import Decimal
from typing import Tuple
from .accounting import Account, Entry, Transaction, CURRENCY_EPSILON, ROUNDING_STRATEGY

_logger = logging.getLogger(__name__)


class EqualSplitter:
    """
    Strategy for evenly splitting a monetary amount across multiple accounts.

    The EqualSplitter produces balanced ledger entries by distributing a total
    cost equally among creditor and debtor accounts. Rounding is handled by
    allocating any remainder to the final account in each group, ensuring the
    resulting entries are exactly in balance.
    """

    def split(
        self,
        cost: Decimal,
        transaction_uid: uuid.UUID,
        creditors: Tuple[Account, ...],
        debtors: Tuple[Account, ...],
    ) -> Tuple[Entry, ...]:
        """
        Generate balanced ledger entries for an equal split transaction.

        The total cost is divided evenly among all creditors (as credits) and
        all debtors (as debits). All monetary amounts are quantized according to
        the configured currency precision and rounding strategy. The returned
        entries sum to zero by construction.

        Args:
            cost:
                Total monetary amount to be split.
            transaction_uid:
                Identifier of the transaction these entries belong to.
            creditors:
                Accounts receiving credit (positive amounts).
            debtors:
                Accounts receiving debit (negative amounts).

        Returns:
            Tuple of Entry objects representing a balanced double-entry posting.
        """
        cost = cost.quantize(CURRENCY_EPSILON, ROUNDING_STRATEGY)

        credits = [Decimal(cost / len(creditors)).quantize(CURRENCY_EPSILON, ROUNDING_STRATEGY)] * (
            len(creditors) - 1
        )
        credits.append(cost - sum(credits))
        credit_entries = [
            Entry(
                uid=uuid.uuid4(),
                transaction_uid=transaction_uid,
                account_uid=creditor.uid,
                amount=credit,
            )
            for creditor, credit in zip(creditors, credits)
        ]

        debits = [Decimal(cost / len(debtors)).quantize(CURRENCY_EPSILON, ROUNDING_STRATEGY)] * (
            len(debtors) - 1
        )
        debits.append(cost - sum(debits))
        debit_entries = [
            Entry(
                uid=uuid.uuid4(),
                transaction_uid=transaction_uid,
                account_uid=debtor.uid,
                amount=-debit,
            )
            for debtor, debit in zip(debtors, debits)
        ]

        return tuple(credit_entries + debit_entries)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("trip")

    args = parser.parse_args()

    with open(args.trip) as trip_file:
        trip = yaml.load(trip_file, Loader=yaml.SafeLoader)

    accounts = {name: Account(uuid.uuid4(), name) for name in trip["accounts"]}
    all_names = list(accounts.keys())

    equal_splitter = EqualSplitter()
    transactions = {}

    for e in trip["expenses"]:
        uid = uuid.uuid4()

        transactions[uid] = Transaction(
            uid=uid,
            entries=equal_splitter.split(
                cost=Decimal(e["amount"]),
                transaction_uid=uid,
                creditors=[accounts[name] for name in e["payers"]],
                debtors=tuple(accounts.values()),
            ),
            description=e["description"],
            timestamp=None,
        )

    entries = [entry for expense in transactions.values() for entry in expense.entries]
    df = pd.DataFrame(entries)
    df["description"] = df["transaction_uid"].apply(lambda x: transactions[x].description)

    print()
    for account in accounts.values():
        print(account.name)
        print(account.uid)
        idx = df["account_uid"] == account.uid
        print(df.loc[idx, ["description", "amount"]])
        print(df.loc[idx, "amount"].sum())
        print()
