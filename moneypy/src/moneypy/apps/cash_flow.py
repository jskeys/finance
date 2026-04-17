import dataclasses
import typing
import uuid
from datetime import datetime, timedelta
from decimal import Decimal

import dateutil
import pandas as pd

from ..accounting import Account, Entry, Transaction

accounts = {
    "cash": Account(uuid.uuid4(), "CASH"),
    "salary": Account(uuid.uuid4(), "SALARY"),
    "entertainment": Account(uuid.uuid4(), "ENTERTAINMENT"),
    "car_insurance": Account(uuid.uuid4(), "INSURANCE"),
    "mortgage": Account(uuid.uuid4(), "MORTGAGE"),
    "taxes": Account(uuid.uuid4(), "TAXES"),
    "benefits": Account(uuid.uuid4(), "BENEFITS"),
    "retirement": Account(uuid.uuid4(), "RETIREMENT"),
    "other": Account(uuid.uuid4(), "OTHER"),
}


@dataclasses.dataclass(frozen=True)
class RecurringTransaction:
    rrule: dateutil.rrule.rrule
    transaction_prototype: Transaction

    def get_transactions(self, start: datetime, finish: datetime):
        for recurrence in self.rrule.between(start, finish):
            transaction_uid = uuid.uuid4()
            yield dataclasses.replace(
                self.transaction_prototype,
                uid=transaction_uid,
                entries=tuple(
                    dataclasses.replace(entry, uid=uuid.uuid4(), transaction_uid=transaction_uid)
                    for entry in self.transaction_prototype.entries
                ),
                timestamp=recurrence,
            )


if __name__ == "__main__":
    recurring_transactions = [
        RecurringTransaction(
            dateutil.rrule.rrule(dateutil.rrule.MONTHLY, datetime(2026, 1, 1), interval=1),
            Transaction(
                0,
                entries=(
                    Entry(0, 0, accounts["cash"].uid, Decimal(-194.30)),
                    Entry(0, 0, accounts["car_insurance"].uid, Decimal(194.30)),
                ),
                description="Car Insurance",
                timestamp=None,
            ),
        ),
        RecurringTransaction(
            dateutil.rrule.rrule(dateutil.rrule.MONTHLY, datetime(2026, 1, 1), interval=1),
            Transaction(
                0,
                entries=(
                    Entry(0, 0, accounts["cash"].uid, Decimal(-3_855.51)),
                    Entry(0, 0, accounts["mortgage"].uid, Decimal(3_855.51)),
                ),
                description="MORTGAGE - 9013 LANTANA",
                timestamp=None,
            ),
        ),
        RecurringTransaction(
            dateutil.rrule.rrule(dateutil.rrule.MONTHLY, datetime(2026, 1, 1), interval=1),
            Transaction(
                0,
                entries=(
                    Entry(0, 0, accounts["cash"].uid, Decimal(-2_233.48)),
                    Entry(0, 0, accounts["mortgage"].uid, Decimal(2_233.48)),
                ),
                description="MORTGAGE - 2514 E 4TH",
                timestamp=None,
            ),
        ),
        RecurringTransaction(
            dateutil.rrule.rrule(dateutil.rrule.DAILY, datetime(2026, 1, 2), interval=14),
            Transaction(
                0,
                entries=(
                    Entry(0, 0, accounts["salary"].uid, Decimal(-8_830.67)),
                    Entry(0, 0, accounts["cash"].uid, Decimal(5_398.23)),
                    Entry(0, 0, accounts["taxes"].uid, Decimal(2_185.93)),
                    Entry(0, 0, accounts["benefits"].uid, Decimal(352.60)),
                    Entry(0, 0, accounts["retirement"].uid, Decimal(883.76)),
                    Entry(0, 0, accounts["other"].uid, Decimal(10.15)),
                ),
                description="SALARY",
                timestamp=None,
            ),
        ),
    ]

    transactions: typing.List[Transaction] = []
    for rt in recurring_transactions:
        transactions.extend(rt.get_transactions(datetime(2026, 1, 1), datetime(2026, 12, 21)))

    entries = []
    for tx in transactions:
        entries.extend(tx.entries)

    for transaction in transactions:
        print(transaction)

    entry_df = pd.DataFrame(dataclasses.asdict(entry) for entry in entries)
    entry_df = entry_df.set_index("uid")

    accounts_df = pd.DataFrame(dataclasses.asdict(account) for account in accounts.values())
    accounts_df = accounts_df.set_index("uid")
