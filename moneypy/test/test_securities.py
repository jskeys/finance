import uuid
from datetime import datetime

import moneypy.securities as securities


def test_minimal_rsu():
    rsu = securities.RestrictedStockUnit(
        uid=uuid.uuid4(),
        num_shares=10000,
        grant_date=datetime(2020, 1, 1),
        vest_date=datetime(2021, 1, 1),
    )
