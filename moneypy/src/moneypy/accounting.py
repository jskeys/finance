"""
Core domain models for a double-entry accounting ledger.

This module defines the immutable primitives used to record economic events:
accounts, transactions, and ledger entries. Transactions aggregate balanced
entries to enforce double-entry integrity, while entries record signed effects
on individual accounts.

These classes are designed to be storage-friendly, deterministic, and suitable
for use as the foundational layer of an expense-tracking or accounting system.
"""

import dataclasses
import datetime
import uuid

from typing import Optional, Tuple
from decimal import Decimal, ROUND_HALF_EVEN

SECONDS_PER_YEAR: float = 31536000
CURRENCY_EPSILON = Decimal("1.00")
ROUNDING_STRATEGY = ROUND_HALF_EVEN


@dataclasses.dataclass(frozen=True)
class Account:
    """
    An immutable identifier for a ledger account.

    An Account represents a logical bucket used to accumulate debits and credits
    (e.g., cash, reimbursement receivable, or a participant’s balance). Accounts
    do not store balances directly; balances are derived from associated ledger
    entries.

    Fields:
        uid: Unique identifier for the account.
        name: Human-readable name for the account.

    Notes:
        - Accounts are immutable and uniquely identified by `uid`.
        - Account balances are computed by aggregating related Entry objects.
        - Accounts are intentionally lightweight and free of accounting logic.
    """

    uid: uuid.UUID
    name: str


@dataclasses.dataclass(frozen=True)
class Entry:
    """
    An immutable ledger entry representing a single posting within a transaction.

    An Entry records the effect of a transaction on a specific account. Entries are
    atomic and must be aggregated by a Transaction to form a balanced double-entry
    posting.

    Fields:
        uid: Unique identifier for this entry.
        transaction_uid: Identifier of the transaction this entry belongs to.
        account_uid: Identifier of the affected account.
        amount: Signed monetary amount applied to the account.

            Convention:
                amount > 0  → credit
                amount < 0  → debit

    Notes:
        - Entries are immutable once created.
        - Entries do not enforce balance on their own; balance is enforced at the
          Transaction level.
        - Monetary values should use Decimal and be quantized to the appropriate
          currency precision.
    """

    uid: uuid.UUID
    transaction_uid: uuid.UUID
    account_uid: uuid.UUID
    amount: Decimal

    def __post_init__(self):
        """Quantize the amount using `CURRENCY_EPSILON`."""
        object.__setattr__(
            self, "amount", self.amount.quantize(CURRENCY_EPSILON, rounding=ROUNDING_STRATEGY)
        )


@dataclasses.dataclass(frozen=True)
class Transaction:
    """
    An immutable accounting transaction composed of balanced ledger entries.

    A Transaction represents a single economic event (e.g., an expense, transfer,
    or settlement) recorded using double-entry bookkeeping. It aggregates two or
    more Entry objects whose signed amounts must sum to zero, ensuring the
    transaction is fully balanced.

    Invariants (enforced at construction time):
        - A transaction must contain at least two entries.
        - The sum of all entry amounts must be zero (within rounding tolerance).

    Fields:
        uid: Unique identifier for the transaction.
        entries: Tuple of Entry objects associated with this transaction.
            Each entry must reference this transaction via `transaction_uid`.
        description: Human-readable description of the economic event.
        timestamp: Optional datetime indicating when the transaction occurred.

    Amount conventions:
        - Entry.amount > 0  → credit
        - Entry.amount < 0  → debit

    Notes:
        - Transactions are immutable once created.
        - Balance is enforced at the Transaction level, not the Entry level.
        - Transactions serve as the atomic unit of consistency in the ledger.

    """

    uid: uuid.UUID
    entries: Tuple[Entry, ...]
    description: str
    timestamp: Optional[datetime.datetime]

    def __post_init__(self):
        """Check minimum entry count and in-balance conditions."""
        if len(self.entries) < 2:
            raise ValueError("Transaction must contain at least 2 entries.")

        total = sum((e.amount for e in self.entries), Decimal("0"))
        if total.quantize(Decimal(CURRENCY_EPSILON)) != Decimal(0.0):
            raise ValueError(
                f"Transaction `{self.description}` is out of balance by $ {total:.2f}."
            )

        if any(e.transaction_uid != self.uid for e in self.entries):
            raise ValueError("Entry transaction_uid mismatch.")

    @property
    def gross_cost(self) -> Decimal:
        """Get the gross cost or magnitude of the economic event."""
        return sum(entry.amount for entry in self.entries if entry.amount > 0)
