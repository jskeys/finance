import dataclasses
import io
import typing
from datetime import datetime
from decimal import Decimal

import pandas as pd
import plotly.graph_objects as go
import streamlit as streamlit
from dateutil.relativedelta import relativedelta
from plotly.subplots import make_subplots

from moneypy.apps.equity_tool import (
    ExerciseStrategy,
    ISOScenario,
    run_scenarios,
    visualize_scenario,
)
from moneypy.core import to_decimal
from moneypy.securities import (
    RestrictedStockUnit,
    import_isos_from_yaml,
    import_rsus_from_yaml,
)
from moneypy.tax import AlternativeMinimumTaxSystem, Income, RegularTaxSystem

rts = RegularTaxSystem()
amt = AlternativeMinimumTaxSystem()


def _coerce_date(x) -> typing.Optional[datetime]:
    if x is not None:
        return pd.to_datetime(x, errors="coerce")
    return None


def _coerce_decimal(x) -> typing.Optional[Decimal]:
    try:
        return to_decimal(x)
    except Exception:
        return None


@streamlit.cache_data
def _run_scenarios(income, scenarios, isos, rsus):
    return run_scenarios(income=income, scenarios=scenarios, isos=isos, rsus=rsus)


@streamlit.cache_data
def _load_equities(equity_file):
    text_stream = io.StringIO(equity_file.getvalue().decode("utf-8"))
    isos = [
        dataclasses.replace(
            iso,
            exercise_date=None,
            sale_date=None,
            fair_market_value=None,
        )
        for iso in import_isos_from_yaml(text_stream)
    ]

    text_stream = io.StringIO(equity_file.getvalue().decode("utf-8"))
    rsus = [
        dataclasses.replace(
            rsu,
            vest_fair_market_value=Decimal(50),
        )
        for rsu in import_rsus_from_yaml(text_stream)
    ]
    return isos, rsus


def main():
    streamlit.set_page_config(layout="wide", page_title="Equity Simulator")

    with streamlit.sidebar:
        equity_file = streamlit.file_uploader(label="Equity YAML", type=["yaml"])

        if equity_file is None:
            streamlit.info("Please upload an equity YAML file to continue.")
            return

        isos, rsus = _load_equities(equity_file)

        streamlit.header("Income Info")
        wages = streamlit.number_input(
            "Wages",
            min_value=0.0,
            max_value=1_000_000.0,
            value=100_000.0,
            step=1_000.0,
            format="%.2f",
        )

        streamlit.header("ISO Global Settings")
        fair_market_value = streamlit.number_input(
            "Fair Market Value",
            min_value=0.0,
            max_value=100.0,
            value=10.0,
            step=0.01,
            format="%.2f",
        )
        price_at_exercise = streamlit.number_input(
            "Price at Exercise",
            min_value=0.0,
            max_value=100.0,
            value=20.0,
            step=0.01,
            format="%.2f",
        )
        price_at_sale = streamlit.number_input(
            "Price at Sale",
            min_value=0.0,
            max_value=100.0,
            value=50.0,
            step=0.01,
            format="%.2f",
        )
        delta = streamlit.number_input(
            "Step",
            min_value=1000,
            max_value=10000,
            value=5000,
            step=1,
            format="%d",
        )

    base_scenario = ISOScenario(
        num_to_exercise=0,
        num_to_sell=0,
        fair_market_value=to_decimal(fair_market_value),
        price_at_exercise=to_decimal(price_at_exercise),
        price_at_sale=to_decimal(price_at_sale),
        exercise_strategy=ExerciseStrategy.INCREASING_STRIKE,
        exercise_date=datetime.today(),
        sale_date=datetime.today() + relativedelta(years=1),
        tax_system=rts,
    )

    iso_df = pd.DataFrame(dataclasses.asdict(iso) for iso in isos)
    iso_df = iso_df.drop(["exercise_date", "fair_market_value", "sale_date", "sale_price"], axis=1)

    iso_col, rsu_col = streamlit.columns([1, 1])
    table_height = 400

    # Convert uploaded file to text stream for YAML parsing
    with iso_col:
        streamlit.header("ISOs")
        streamlit.dataframe(
            iso_df,
            column_config={
                "uid": streamlit.column_config.TextColumn(
                    "UID",
                ),
                "grant_date": streamlit.column_config.DateColumn(
                    "Grant Date",
                ),
                "strike_price": streamlit.column_config.NumberColumn(
                    "Strike Price",
                    format="dollar",
                ),
                "num_shares": streamlit.column_config.NumberColumn(
                    "Shares",
                    format="localized",
                ),
            },
            height=table_height,
        )

    with rsu_col:
        streamlit.header("RSUs")
        rsus_df = streamlit.data_editor(
            # Set column names explicitly. This handles the case where the equities file doesn't
            # have any RSUs
            pd.DataFrame(
                rsus, columns=[field.name for field in dataclasses.fields(RestrictedStockUnit)]
            ),
            column_config={
                "num_shares": streamlit.column_config.NumberColumn(
                    "Shares",
                    format="localized",
                ),
                "sale_date": streamlit.column_config.DateColumn(
                    "Sale Date",
                ),
                "vest_fair_market_value": streamlit.column_config.NumberColumn(
                    "FMV at Vest",
                    format="dollar",
                ),
                "sale_price": streamlit.column_config.NumberColumn(
                    "Price at Sale",
                    format="dollar",
                ),
            },
            height=table_height,
        )

    rsus_df["sale_date"] = rsus_df["sale_date"].apply(_coerce_date)
    rsus_df["sale_price"] = rsus_df["sale_price"].apply(_coerce_decimal)

    try:
        rsus = [RestrictedStockUnit(**row) for row in rsus_df.to_dict(orient="records")]
    except Exception as e:
        streamlit.info(e)
        return -1

    share_count = sum([iso.num_shares for iso in isos])

    scenarios = [base_scenario] + [
        dataclasses.replace(base_scenario, num_to_sell=num_to_sell, num_to_exercise=num_to_exercise)
        for num_to_exercise in range(0, share_count + delta, delta)
        for num_to_sell in range(0, num_to_exercise + delta, delta)
    ]

    scenarios += [dataclasses.replace(scenario, tax_system=amt) for scenario in scenarios]
    income = Income(Decimal(wages))

    df = _run_scenarios(income, scenarios, isos, rsus)

    keys = list(dataclasses.asdict(base_scenario).keys()) + ["year"]
    keys.remove("tax_system")

    max_tax_df = df.loc[df.groupby(keys)["tax"].idxmax()].reset_index(drop=True)

    summary_cols = [
        "cash_flow",
        "iso_exercise_cost",
        "iso_proceeds",
        "iso_realized_gain",
        "tax",
        "rsu_proceeds",
    ]
    keys.remove("year")
    summary_df = (
        max_tax_df.groupby(keys).agg({**{col: "sum" for col in summary_cols}}).reset_index()
    )

    x_col = "num_to_exercise"
    y_col = "num_to_sell"
    x_label = "ISO Exercise Count"
    y_label = "ISO Sell Count"
    fig_height = 400
    fig_width = 400
    title = {"x": 0.5, "xanchor": "center"}

    unique_years = list(max_tax_df["year"].unique())
    columns = streamlit.columns(len(unique_years) + 1)

    # for parameter in summary_cols:
    for parameter in ["cash_flow", "tax"]:
        pretty_parameter = parameter.replace("_", "").title()
        with columns[0]:
            fig = go.Figure()
            fig.add_traces(
                visualize_scenario(summary_df[x_col], summary_df[y_col], summary_df[parameter])
            )
            fig.update_layout(
                title={"text": f"{pretty_parameter}<br>Summary", **title},
                height=fig_height,
                width=fig_width,
                xaxis_title_text=x_label,
                yaxis_title_text=y_label,
            )
            streamlit.plotly_chart(fig, width=fig_width)

        for i, (year, year_df) in enumerate(max_tax_df.groupby("year")):
            with columns[i + 1]:
                fig = go.Figure()
                fig.add_traces(
                    visualize_scenario(year_df[x_col], year_df[y_col], year_df[parameter])
                )
                fig.update_layout(
                    title={"text": f"{pretty_parameter}<br>{year}", **title},
                    height=fig_height,
                    width=fig_width,
                    xaxis_title_text=x_label,
                    yaxis_title_text=y_label,
                )
                streamlit.plotly_chart(fig, width=fig_width)

    streamlit.header("Strategy Summaries")
    streamlit.dataframe(summary_df)


if __name__ == "__main__":
    main()
