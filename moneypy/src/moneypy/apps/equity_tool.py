import argparse
import logging
import typing
from decimal import Decimal

import dacite
import pandas as pd
import yaml
from tabulate import tabulate

from moneypy.securities import IncentiveStockOption, ISODisposition, RestrictedStockUnit
from moneypy.tax import AlternativeMinimumTaxSystem, RegularTaxSystem


def main():

    parser = argparse.ArgumentParser()
    parser.add_argument("equity_path")
    parser.add_argument("ordinary_income", type=Decimal)
    parser.add_argument("iso_fair_market_value", type=Decimal)
    parser.add_argument("rsu_fair_market_value", type=Decimal)

    args = parser.parse_args()

    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s:%(lineno)d - %(message)s"))

    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)

    with open(args.equity_path) as iso_file:
        equity_dict = yaml.safe_load(iso_file)
        logger.info(f"Loaded equity summary from `{args.equity_path}`.")

    isos: typing.Dict[str, IncentiveStockOption] = {}
    rsus: typing.Dict[str, RestrictedStockUnit] = {}

    for equity in equity_dict:
        equity_class = equity.pop("class")
        if equity_class == "ISO":
            equity["fair_market_value"] = args.iso_fair_market_value
            isos[equity["uid"]] = dacite.from_dict(
                IncentiveStockOption,
                equity,
                config=dacite.Config(type_hooks={Decimal: Decimal}),
            )
        if equity_class == "RSU":
            equity["vest_fair_market_value"] = args.rsu_fair_market_value
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
    rsu_df["compensation_income"] = rsu_df.apply(
        lambda row: rsus[row["uid"]].compensation_income, axis=1
    )
    print(tabulate(rsu_df, headers=rsu_df.columns, floatfmt=",.2f"))

    rts = RegularTaxSystem()
    amt = AlternativeMinimumTaxSystem()

    summaries = {}

    for year in (2026, 2027):
        print()
        print(year)
        print(rts.calculate_tax(args.ordinary_income, isos.values(), year))

    # for year in (2026, 2027):
    #     # Calculate capital gains
    #     mask = [True] * len(iso_df)
    #     mask &= iso_df["sale_date"].apply(lambda x: x.year) == year
    #     mask &= iso_df["disposition"] == ISODisposition.QUALIFYING
    #     capital_gains = iso_df[mask]["net_income"].sum()

    #     # Calculate income
    #     mask = [True] * len(iso_df)
    #     mask &= iso_df["sale_date"].apply(lambda x: x.year) == year
    #     mask &= iso_df["disposition"] == ISODisposition.DISQUALIFYING
    #     income = iso_df[mask]["net_income"].sum()

    #     # Calculate Exercie cost
    #     mask = [True] * len(iso_df)
    #     mask &= iso_df["exercise_date"].apply(lambda x: x.year) == year
    #     exercise_cost = iso_df[mask]["exercise_cost"].sum()

    #     # The bargain element is added toe alternative minimum tax income if the position is not
    #     # sold that year.
    #     mask &= iso_df["sale_date"].apply(lambda x: x.year) != year
    #     bargain_elements = iso_df[mask]["bargain_element"].sum()

    #     # If the year an option is sold is different than the exercise year, then the tax bill may
    #     # be reduced. The `amt_gain` is added to amt income for non-qualifying dispositions and to
    #     # long-term capital-gains for qualifying dispositions. Note that this value is the
    #     # sale-price to fmv spread rather than the sale-price to exercise spread, so the amt tax
    #     # bill should be lower, which should increase the amount of the credit available for use.
    #     mask = [True] * len(iso_df)
    #     mask &= iso_df["exercise_date"].apply(lambda x: x.year) != year
    #     mask &= iso_df["sale_date"].apply(lambda x: x.year) == year
    #     mask &= iso_df["disposition"] == ISODisposition.QUALIFYING
    #     amt_lt_capital_gains = iso_df[mask]["amt_gain"].sum()

    #     mask = [True] * len(iso_df)
    #     mask &= iso_df["exercise_date"].apply(lambda x: x.year) != year
    #     mask &= iso_df["sale_date"].apply(lambda x: x.year) == year
    #     mask &= iso_df["disposition"] == ISODisposition.DISQUALIFYING
    #     amt_income = iso_df[mask]["amt_gain"].sum()

    #     # Calculate RSU contribution
    #     mask = [True] * len(rsu_df)
    #     mask &= rsu_df["vest_date"].apply(lambda x: x.year) == year
    #     income += rsu_df[mask]["compensation_income"].sum()

    #     income += Decimal(250000)

    #     amt_income += income + bargain_elements

    #     regular_tax = rts.calculate_tax(income, capital_gains)
    #     amt_tax = amt.calculate_tax(amt_income, capital_gains)
    #     tax = max(regular_tax, amt_tax)

    #     summary = {
    #         "iso_exercise_cost": exercise_cost,
    #         "bargain_elements": bargain_elements,
    #         "ordinary_income": income,
    #         "amt_income": amt_income,
    #         "capital_gains": capital_gains,
    #         "regular_tax": regular_tax,
    #         "amt_tax": amt_tax,
    #         "tax": tax,
    #         "tax_rate": tax / (income + capital_gains),
    #         "amt_credit": amt_tax - regular_tax if amt_tax > regular_tax else 0,
    #     }

    #     summaries[year] = summary

    # summary_df = pd.DataFrame.from_dict(summaries, orient="index")
    # print(tabulate(summary_df, headers=summary_df.columns, floatfmt=",.2f"))


if __name__ == "__main__":
    main()
