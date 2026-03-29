import argparse
import dataclasses
import itertools
import logging
import typing
from datetime import date
from decimal import Decimal
from enum import IntEnum, auto

import pandas as pd
import plotly.graph_objects as go
from dateutil.relativedelta import relativedelta

from moneypy.securities import IncentiveStockOption, import_isos_from_yaml
from moneypy.tax import AlternativeMinimumTaxSystem, Income, RegularTaxSystem


class ExerciseStrategy(IntEnum):
    INCREASING_STRIKE = 0
    DECREASING_STRIKE = auto()


def allocate(points, target):
    out = []
    for p in points:
        out.append(min(p, target))
        target -= out[-1]
    return out


def run_scenarios(
    income: Income,
    isos: typing.Sequence[IncentiveStockOption],
    fair_market_value: Decimal,
    price_at_exercise: Decimal,
    price_at_sale: Decimal,
    exercise_strategies: typing.Sequence[ExerciseStrategy] = (
        ExerciseStrategy.INCREASING_STRIKE,
        ExerciseStrategy.DECREASING_STRIKE,
    ),
    delta: int = 1000,
    sale_date: typing.Optional[date] = None,
):

    rts = RegularTaxSystem()
    amt = AlternativeMinimumTaxSystem()

    # Discount salary-related tax at the end because we're ignoring salary, but it still factors in
    # calculations.
    baseline_tax = rts.calculate_tax(2026, income).tax

    scenarios = []

    if sale_date is None:
        sale_date = date.today() + relativedelta(years=1)

    for exercise_strategy in exercise_strategies:
        isos = sorted(
            isos,
            key=lambda k: k.exercise_price,
            reverse=exercise_strategy == ExerciseStrategy.DECREASING_STRIKE,
        )
        iso_share_counts = [iso.num_shares for iso in isos]
        num_iso_shares = sum(iso_share_counts)
        for num_exercised in range(0, num_iso_shares + delta, delta):
            for num_sold in range(0, num_exercised + delta, delta):
                exercise_schedule = allocate(iso_share_counts, num_exercised)
                sale_schedule = allocate(iso_share_counts, num_sold)
                processed_isos = []
                for iso, exercise_shares, sale_shares in zip(
                    isos, exercise_schedule, sale_schedule
                ):
                    # Exercise up to `exercise_shares`. Returns the exercised shares and the
                    # un-exercised shares. Tuck the unexercised shares away for later.
                    (exercised, unexercised) = iso.exercise(
                        date.today(), fair_market_value, exercise_shares
                    )
                    # Capture the unexercised shares, although they won't have any bearing on the
                    # scenario outcome
                    if unexercised:
                        processed_isos += [unexercised]

                    # Sell some of the exercised shares now and sell the rest in one year.
                    if exercised:
                        (sold, unsold) = exercised.sell(
                            date.today(), price_at_exercise, sale_shares
                        )
                        if sold:
                            processed_isos += [sold]
                        if unsold:
                            processed_isos += [unsold.sell(sale_date, price_at_sale)[0]]

                years = set(
                    [
                        iso.exercise_date.year
                        for iso in processed_isos
                        if iso.exercise_date is not None
                    ]
                    + [iso.sale_date.year for iso in processed_isos if iso.sale_date is not None]
                )

                for year, system in itertools.product(years, (rts, amt)):
                    scenarios.append(
                        {
                            "exercise_strategy": exercise_strategy,
                            "num_exercised": num_exercised,
                            "num_sold": num_sold,
                            **dataclasses.asdict(
                                system.calculate_tax(year, income, processed_isos)
                            ),
                            "shares_exercised_this_year": sum(
                                [
                                    iso.num_shares
                                    for iso in processed_isos
                                    if iso.exercise_date is not None
                                    and iso.exercise_date.year == year
                                ]
                            ),
                            "shares_sold_this_year": sum(
                                [
                                    iso.num_shares
                                    for iso in processed_isos
                                    if iso.sale_date is not None and iso.sale_date.year == year
                                ]
                            ),
                            "iso_exercise_cost": sum(
                                [
                                    iso.exercise_cost
                                    for iso in processed_isos
                                    if iso.exercise_date is not None
                                    and iso.exercise_date.year == year
                                ]
                            ),
                            "iso_exercise_cost": sum(
                                [
                                    iso.exercise_cost
                                    for iso in processed_isos
                                    if iso.exercise_date is not None
                                    and iso.exercise_date.year == year
                                ]
                            ),
                            "iso_proceeds": sum(
                                [
                                    iso.proceeds
                                    for iso in processed_isos
                                    if iso.sale_date is not None and iso.sale_date.year == year
                                ]
                            ),
                            "iso_net_gain": sum(
                                [
                                    iso.net_income
                                    for iso in processed_isos
                                    if iso.sale_date is not None and iso.sale_date.year == year
                                ]
                            ),
                        }
                    )

    multi_index = ["year", "system", "exercise_strategy"]

    df = pd.DataFrame(scenarios).set_index(multi_index).sort_index()
    # Add a column that provides the actual tax that year.
    df["max_tax"] = df.groupby(["year", "exercise_strategy", "num_exercised", "num_sold"])[
        "tax"
    ].transform("max")
    df["cash_flow"] = df["iso_proceeds"] - df["iso_exercise_cost"] - df["max_tax"] + baseline_tax

    # Summarize strategy across all years.
    multi_year_groupby = ["system", "exercise_strategy", "num_exercised", "num_sold"]

    df["total_proceeds"] = df.groupby(multi_year_groupby)["iso_proceeds"].transform("sum")
    df["total_cash_flow"] = df.groupby(multi_year_groupby)["cash_flow"].transform("sum")
    df["total_tax"] = df.groupby(multi_year_groupby)["max_tax"].transform("sum")

    return df


def visualize_scenarios(df: pd.DataFrame) -> typing.List[go.Figure]:

    year = 2026
    system = "regular_tax"
    exercise_strategy = ExerciseStrategy.INCREASING_STRIKE

    x = df.loc[year, system, exercise_strategy]["num_exercised"]
    y = df.loc[year, system, exercise_strategy]["num_sold"]

    figures = []
    for title, z in {
        "Proceeds": df.loc[year, system, exercise_strategy]["iso_proceeds"],
        "Total Proceeds": df.loc[year, system, exercise_strategy]["total_proceeds"],
        "Tax": df.loc[year, system, exercise_strategy]["max_tax"],
        "Total Tax": df.loc[year, system, exercise_strategy]["total_tax"],
        "Cash Flow": df.loc[year, system, exercise_strategy]["cash_flow"],
        "Total Cash Flow": df.loc[(year, system, exercise_strategy), "total_cash_flow"],
    }.items():
        zmin = min(z)
        zmax = max(z)

        if zmin > 0:
            colorscale = [[0.0, "yellow"], [1.0, "green"]]
        else:
            colorscale = [
                [0.0, "red"],
                [abs(zmin) / (abs(zmin) + abs(zmax)), "yellow"],
                [1.0, "green"],
            ]

        fig = go.Figure()
        fig.update_layout(
            title_text=title,
            title_x=0.5,
            height=500,
            width=500,
            xaxis_title="Exercised Shares",
            yaxis_title="Shares Sold at Exercise",
        )
        fig.add_trace(
            go.Heatmap(
                x=x,
                y=y,
                z=z,
                colorscale=colorscale,
                zmin=zmin,
                zmax=zmax,
            )
        )
        fig.add_trace(
            go.Contour(
                x=x,
                y=y,
                z=z,
                contours={"coloring": "none", "showlabels": True},
                showscale=False,
                connectgaps=False,
            )
        )
        figures.append(fig)
    return figures


def main():

    parser = argparse.ArgumentParser()
    parser.add_argument("equity_path")
    parser.add_argument("--income", "-w", type=Decimal)
    parser.add_argument("--iso_fmv", "-i", type=Decimal)
    parser.add_argument("--iso_price_at_exercise", "-e", type=Decimal)
    parser.add_argument("--iso_price_at_sale", "-s", type=Decimal)
    parser.add_argument("--rsu_fmv", "-r", type=Decimal)
    parser.add_argument("--log-level", "-l", type=int, default=logging.WARN)

    args = parser.parse_args()

    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s:%(lineno)4d - %(message)s"))

    logger = logging.getLogger()
    logger.setLevel(args.log_level)
    logger.addHandler(handler)

    isos = import_isos_from_yaml(args.equity_path, args.iso_fmv)
    isos = [dataclasses.replace(iso, exercise_date=None, sale_date=None) for iso in isos]

    logger.info("Running scenarios.")
    df = run_scenarios(
        Income(args.income),
        isos,
        args.iso_fmv,
        args.iso_price_at_exercise,
        args.iso_price_at_sale,
    )
    print(df)


if __name__ == "__main__":
    main()
