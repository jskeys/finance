import argparse
import itertools
import logging
import typing
from decimal import Decimal

import dacite
import pandas as pd
import yaml
from tabulate import tabulate

from moneypy.securities import IncentiveStockOption, RestrictedStockUnit
from moneypy.tax import AlternativeMinimumTaxSystem, Income, RegularTaxSystem


def main():

    parser = argparse.ArgumentParser()
    parser.add_argument("equity_path")
    parser.add_argument("--log-level", "-l", type=int, default=logging.INFO)

    args = parser.parse_args()

    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s:%(lineno)4d - %(message)s"))

    logger = logging.getLogger()
    logger.setLevel(args.log_level)
    logger.addHandler(handler)

    with open(args.equity_path) as iso_file:
        equity_dict = yaml.safe_load(iso_file)
        logger.info(f"Loaded equity summary from `{args.equity_path}`.")

    isos: typing.Dict[str, IncentiveStockOption] = {}
    rsus: typing.Dict[str, RestrictedStockUnit] = {}

    fair_market_value = 10.94

    for equity in equity_dict:
        equity_class = equity.pop("class")
        if equity_class == "ISO":
            equity["fair_market_value"] = fair_market_value
            isos[equity["uid"]] = dacite.from_dict(
                IncentiveStockOption,
                equity,
                config=dacite.Config(type_hooks={Decimal: Decimal}),
            )
        if equity_class == "RSU":
            equity["vest_fair_market_value"] = 50
            rsus[equity["uid"]] = dacite.from_dict(
                RestrictedStockUnit,
                equity,
                config=dacite.Config(type_hooks={Decimal: Decimal}),
            )

    DATE_COLS = ["grant_date", "exercise_date", "sale_date"]

    iso_df = pd.DataFrame(isos.values())
    iso_df[DATE_COLS] = iso_df[DATE_COLS].apply(pd.to_datetime, errors="coerce")
    iso_df["bargain_element"] = iso_df.apply(lambda row: isos[row["uid"]].bargain_element, axis=1)
    iso_df["exercise_cost"] = iso_df.apply(lambda row: isos[row["uid"]].exercise_cost, axis=1)
    iso_df["proceeds"] = iso_df.apply(lambda row: isos[row["uid"]].proceeds, axis=1)
    iso_df["amt_gain"] = iso_df.apply(lambda row: isos[row["uid"]].amt_gain, axis=1)
    iso_df["net_income"] = iso_df.apply(lambda row: isos[row["uid"]].net_income, axis=1)
    iso_df["disposition"] = iso_df.apply(lambda row: isos[row["uid"]].disposition, axis=1)
    print(iso_df)
    print()

    RSU_DATE_COLS = ["grant_date", "vest_date", "sale_date"]
    rsu_df = pd.DataFrame(rsus.values())
    rsu_df[RSU_DATE_COLS] = rsu_df[RSU_DATE_COLS].apply(pd.to_datetime, errors="coerce")
    rsu_df["rsu_basis"] = rsu_df.apply(lambda row: rsus[row["uid"]].rsu_basis, axis=1)
    rsu_df["capital_gain"] = rsu_df.apply(lambda row: rsus[row["uid"]].capital_gain, axis=1)
    print(tabulate(rsu_df, headers=rsu_df.columns, floatfmt=",.2f"))

    rts = RegularTaxSystem()
    amt = AlternativeMinimumTaxSystem()

    dfs = []

    for year, system in itertools.product((2026, 2027), (rts, amt)):
        dfs.append(
            pd.DataFrame.from_dict(
                {
                    (year, type(system).__name__): system.calculate_tax(
                        year,
                        Income(Decimal(240_000)),
                        isos.values(),
                        rsus.values(),
                    ),
                },
                orient="index",
            )
        )

    df = pd.concat(dfs)
    print(tabulate(df, headers=df.columns, floatfmt=",.2f"))


if __name__ == "__main__":
    main()
