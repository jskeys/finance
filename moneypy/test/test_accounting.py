import uuid
from decimal import Decimal

import pytest

from moneypy.accounting import Entry, Transaction
from moneypy.core import ZERO


def test_entry_accepts_float():

    Entry(uid=uuid.uuid4(), transaction_uid=uuid.uuid4(), account_uid=uuid.uuid4(), amount=0.0)


def test_entry_accepts_int():

    Entry(uid=uuid.uuid4(), transaction_uid=uuid.uuid4(), account_uid=uuid.uuid4(), amount=0)


def test_entry_accepts_decimal():

    Entry(uid=uuid.uuid4(), transaction_uid=uuid.uuid4(), account_uid=uuid.uuid4(), amount=ZERO)


def test_transaction_handles_rounding():
    tx_uid = uuid.uuid4()

    with pytest.raises(ValueError):
        Transaction(
            uid=tx_uid,
            entries=(
                Entry(
                    uid=uuid.uuid4(), transaction_uid=tx_uid, account_uid=uuid.uuid4(), amount=1 / 3
                ),
                Entry(
                    uid=uuid.uuid4(), transaction_uid=tx_uid, account_uid=uuid.uuid4(), amount=1 / 3
                ),
                Entry(
                    uid=uuid.uuid4(), transaction_uid=tx_uid, account_uid=uuid.uuid4(), amount=1 / 3
                ),
                Entry(
                    uid=uuid.uuid4(), transaction_uid=tx_uid, account_uid=uuid.uuid4(), amount=-1
                ),
            ),
            description="Test out-of-balance entries.",
        )
