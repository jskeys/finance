import argparse
import dataclasses
import logging
import typing
from datetime import datetime
from decimal import Decimal
from enum import IntEnum, auto

import pandas as pd
import plotly.graph_objects as go
import tabulate
from dateutil.relativedelta import relativedelta

from moneypy.securities import (
    IncentiveStockOption,
    RestrictedStockUnit,
    import_isos_from_yaml,
    import_rsus_from_yaml,
)
from moneypy.tax import AlternativeMinimumTaxSystem, Income, RegularTaxSystem, TaxSystem


class ExerciseStrategy(IntEnum):
    INCREASING_STRIKE = 0
    DECREASING_STRIKE = auto()


@dataclasses.dataclass(frozen=True)
class ISOScenario:
    num_to_exercise: int
    num_to_sell: int
    fair_market_value: Decimal
    price_at_exercise: Decimal
    price_at_sale: Decimal
    exercise_strategy: ExerciseStrategy
    exercise_date: datetime
    sale_date: datetime
    tax_system: TaxSystem


def allocate(points, target):
    out = []
    for p in points:
        out.append(min(p, target))
        target -= out[-1]
    return out


def run_scenarios(
    income: Income,
    scenarios: typing.Sequence[ISOScenario],
    isos: typing.Sequence[IncentiveStockOption] = [],
    rsus: typing.Sequence[RestrictedStockUnit] = [],
):

    # Discount salary-related tax at the end because we're ignoring salary, but it still factors in
    # calculations.
    baseline_tax = RegularTaxSystem().calculate_tax(2026, income).tax

    scenario_results = []

    for scenario in scenarios:
        isos = sorted(
            isos.copy(),
            key=lambda k: k.strike_price,
            reverse=scenario.exercise_strategy == ExerciseStrategy.DECREASING_STRIKE,
        )
        iso_share_counts = [iso.num_shares for iso in isos]

        exercise_schedule = allocate(iso_share_counts, scenario.num_to_exercise)
        sale_schedule = allocate(iso_share_counts, scenario.num_to_sell)
        processed_isos = []

        for iso, exercise_shares, sale_shares in zip(isos, exercise_schedule, sale_schedule):
            # Exercise up to `exercise_shares`. Returns the exercised shares and the
            # un-exercised shares. Tuck the unexercised shares away for later.
            (exercised, unexercised) = iso.exercise(
                scenario.exercise_date, scenario.fair_market_value, exercise_shares
            )
            # Capture the unexercised shares, although they won't have any bearing on the
            # scenario outcome
            if unexercised:
                processed_isos += [unexercised]

            # Sell some of the exercised shares now and sell the rest in one year.
            if exercised:
                (sold, unsold) = exercised.sell(
                    scenario.exercise_date, scenario.price_at_exercise, sale_shares
                )
                if sold:
                    processed_isos += [sold]
                if unsold:
                    processed_isos += [unsold.sell(scenario.sale_date, scenario.price_at_sale)[0]]

        years = set(
            [iso.exercise_date.year for iso in processed_isos if iso.exercise_date is not None]
            + [iso.sale_date.year for iso in processed_isos if iso.sale_date is not None]
            + [rsu.sale_date.year for rsu in rsus if rsu.sale_date is not None]
            + [rsu.vest_date.year for rsu in rsus if rsu.vest_date is not None]
        )

        for year in years:
            # Get rid of keys that don't add value.A
            scenario_dict = dataclasses.asdict(scenario)
            scenario_dict.pop("tax_system")
            scenario_results.append(
                {
                    **scenario_dict,
                    **dataclasses.asdict(
                        scenario.tax_system.calculate_tax(
                            year=year,
                            income=income,
                            isos=processed_isos,
                            rsus=rsus,
                        )
                    ),
                    "shares_exercised_this_year": sum(
                        [
                            iso.num_shares
                            for iso in processed_isos
                            if iso.exercise_date is not None and iso.exercise_date.year == year
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
                            if iso.exercise_date is not None and iso.exercise_date.year == year
                        ]
                    ),
                    "iso_proceeds": sum(
                        [
                            iso.proceeds
                            for iso in processed_isos
                            if iso.sale_date is not None and iso.sale_date.year == year
                        ]
                    ),
                    "iso_realized_gain": sum(
                        [
                            iso.realized_gain
                            for iso in processed_isos
                            if iso.sale_date is not None and iso.sale_date.year == year
                        ]
                    ),
                    "rsu_proceeds": sum(
                        [
                            rsu.proceeds
                            for rsu in rsus
                            if rsu.sale_date is not None and rsu.sale_date.year == year
                        ]
                    ),
                }
            )

    df = pd.DataFrame.from_dict(scenario_results)
    df["cash_flow"] = df["iso_proceeds"] + df["rsu_proceeds"] - df["iso_exercise_cost"] - df["tax"]

    return df


def visualize_scenario(x: pd.Series, y: pd.Series, z: pd.Series) -> typing.Sequence[go.Trace]:

    zmin = min(z)
    zmax = max(z)

    if zmin > 0 or zmin == zmax:
        colorscale = [[0.0, "yellow"], [1.0, "green"]]
    else:
        colorscale = [
            [0.0, "red"],
            [abs(zmin) / (abs(zmin) + abs(zmax)), "yellow"],
            [1.0, "green"],
        ]

    traces = [
        go.Heatmap(
            x=x,
            y=y,
            z=z,
            colorscale=colorscale,
            showscale=False,
            zmin=zmin,
            zmax=zmax,
        ),
        go.Contour(
            x=x,
            y=y,
            z=z,
            contours={"coloring": "none", "showlabels": True},
            showlegend=False,
            showscale=False,
            connectgaps=False,
        ),
    ]

    return traces


def main():

    parser = argparse.ArgumentParser()
    parser.add_argument("equity_path")
    parser.add_argument("--income", "-w", type=Decimal)
    parser.add_argument("--num_to_exercise", "-ne", type=int)
    parser.add_argument("--num_to_sell", "-ns", type=int)
    parser.add_argument("--iso_fmv", "-f", type=Decimal)
    parser.add_argument("--iso_price_at_exercise", "-pe", type=Decimal)
    parser.add_argument("--iso_price_at_sale", "-ps", type=Decimal)
    parser.add_argument("--rsu_fmv", "-r", type=Decimal)
    parser.add_argument("--log-level", "-l", type=int, default=logging.WARN)

    args = parser.parse_args()

    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s:%(lineno)4d - %(message)s"))

    logger = logging.getLogger()
    logger.setLevel(args.log_level)
    logger.addHandler(handler)

    with open(args.equity_path) as equity_file:
        isos = import_isos_from_yaml(equity_file)
        isos = [dataclasses.replace(iso, exercise_date=None, sale_date=None) for iso in isos]

    with open(args.equity_path) as equity_file:
        rsus = import_rsus_from_yaml(equity_file)
        rsus = [dataclasses.replace(rsu) for rsu in rsus]

    logger.info("Running scenarios.")
    df = run_scenarios(
        isos=isos,
        rsus=rsus,
        income=Income(args.income),
        scenarios=[
            ISOScenario(
                exercise_date=datetime.today(),
                sale_date=datetime.today() + relativedelta(years=1),
                exercise_strategy=ExerciseStrategy.INCREASING_STRIKE,
                fair_market_value=args.iso_fmv,
                num_to_exercise=args.num_to_exercise,
                num_to_sell=args.num_to_sell,
                price_at_exercise=args.iso_price_at_exercise,
                price_at_sale=args.iso_price_at_sale,
                tax_system=tax_system,
            )
            for tax_system in (AlternativeMinimumTaxSystem(), RegularTaxSystem())
        ],
    )
    print(tabulate.tabulate(df, headers=df.columns))


if __name__ == "__main__":
    main()
