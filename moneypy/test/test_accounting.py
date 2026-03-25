
import uuid
from decimal import Decimal
from moneypy.core import ZERO
from moneypy.accounting import Entry

def test_entry_accepts_float():

    Entry(
        uid = uuid.uuid4(),
        transaction_uid=uuid.uuid4(),
        account_uid=uuid.uuid4(),
        amount=0.0,
    )

def test_entry_accepts_int():

    Entry(
        uid = uuid.uuid4(),
        transaction_uid=uuid.uuid4(),
        account_uid=uuid.uuid4(),
        amount=0,
    )

def test_entry_accepts_decimal():

    Entry(
        uid = uuid.uuid4(),
        transaction_uid=uuid.uuid4(),
        account_uid=uuid.uuid4(),
        amount=Decimal(ZERO),
    )

