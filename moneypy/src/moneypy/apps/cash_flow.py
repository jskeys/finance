import dataclasses
import uuid
from datetime import datetime, timedelta
from decimal import Decimal

import dateutil
import pandas as pd

from ..accounting import Account, Entry, Transaction

accounts = {
    "CASH": Account(uuid.uuid4(), "CASH"),
    "WITHOLDING": Account(uuid.uuid4(), "WITHOLDING"),
    "SALARY": Account(uuid.uuid4(), "SALARY"),
}


@dataclasses.dataclass(frozen=True)
class RecurringTransaction:
    rrule: dateutil.rrule.rrule
    transaction_prototype: Transaction

    def get_transactions(self, start: datetime, finish: datetime):
        for recurrence in self.rrule.between(start, finish):
            transaction_uid = uuid.uuid4()
            print(self.transaction_prototype)
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
    recurring_transaction = RecurringTransaction(
        dateutil.rrule.rrule(dateutil.rrule.DAILY, datetime(2026, 1, 2), interval=14),
        Transaction(
            0,
            entries=(
                Entry(0, 0, accounts["CASH"].uid, Decimal(1_000)),
                Entry(0, 0, accounts["SALARY"].uid, Decimal(-1_000)),
            ),
            description="Salary",
            timestamp=None,
        ),
    )

    df = pd.DataFrame.from_dict(
        (
            dataclasses.asdict(entry)
            for transaction in recurring_transaction.get_transactions(
                datetime.today(), datetime.today() + timedelta(days=180)
            )
            for entry in transaction.entries
        )
    )

    print(df)
