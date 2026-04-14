import dataclasses
from typing import Callable, Optional

import numpy as np
import plotly.colors as pc
import plotly.graph_objects as go
import streamlit as streamlit

from moneypy.mortgage import (
    MortgageParameters,
    calc_down_payment,
    calc_home_value,
    calc_monthly_payment,
)


@dataclasses.dataclass(frozen=True)
class ParameterSpec:
    arg_name: str
    display_name: str
    default_value: float
    sweep_default_min: Optional[float] = None
    sweep_default_max: Optional[float] = None
    sweep_default_steps: Optional[int] = None
    format_str: str = "%.2f"
    converter: Callable = dataclasses.field(default=lambda x: x)


parameters = {
    MortgageParameters.HOME_VALUE: ParameterSpec(
        arg_name="home_value",
        display_name="Home Value ($k)",
        default_value=200.0,
        sweep_default_min=100.0,
        sweep_default_max=1_000.0,
        sweep_default_steps=101,
    ),
    MortgageParameters.MONTHLY_PAYMENT: ParameterSpec(
        arg_name="monthly_payment",
        display_name="Monthly Payment ($k)",
        default_value=2.0,
        sweep_default_min=1.0,
        sweep_default_max=10.0,
        sweep_default_steps=101,
    ),
    MortgageParameters.DOWN_PAYMENT: ParameterSpec(
        arg_name="down_payment",
        display_name="Down Payment ($k)",
        default_value=40.0,
        sweep_default_min=0.0,
        sweep_default_max=500.0,
        sweep_default_steps=101,
    ),
    MortgageParameters.INTEREST_RATE: ParameterSpec(
        arg_name="interest_rate",
        display_name="Interest Rate (%)",
        default_value=6.875,
        format_str="%.3f",
        sweep_default_min=3,
        sweep_default_max=10,
        sweep_default_steps=101,
        converter=lambda x: x / 100,
    ),
    MortgageParameters.TAX_RATE: ParameterSpec(
        arg_name="tax_rate",
        display_name="Tax Rate (%)",
        format_str="%.3f",
        default_value=2.0,
        converter=lambda x: x / 100,
    ),
    MortgageParameters.INSURANCE_RATE: ParameterSpec(
        arg_name="insurance_rate",
        display_name="Insurance Rate (%)",
        format_str="%.3f",
        default_value=0.5,
        converter=lambda x: x / 100,
    ),
    MortgageParameters.TERM_MONTHS: ParameterSpec(
        arg_name="num_months",
        display_name="Term (Months)",
        format_str="%d",
        default_value=360,
    ),
}

functions = {
    MortgageParameters.DOWN_PAYMENT: calc_down_payment,
    MortgageParameters.HOME_VALUE: calc_home_value,
    MortgageParameters.MONTHLY_PAYMENT: calc_monthly_payment,
}

ALL_PARAMETERS = frozenset(MortgageParameters)

Z_PARAMETERS = set(functions.keys())
XY_PARAMETERS = Z_PARAMETERS | set([MortgageParameters.INTEREST_RATE])


def main():
    streamlit.set_page_config(layout="wide", page_title="Mortgage Explorer")

    with streamlit.sidebar:
        streamlit.header("Parameters")
        z_parameter = streamlit.selectbox(
            "Calculated Value",
            Z_PARAMETERS,
            index=0,
            format_func=lambda x, p=parameters: p[x].display_name,
        )

        swept_parameters = set(XY_PARAMETERS)
        swept_parameters.remove(z_parameter)

        streamlit.write("Swept Parameters")
        x_parameter = streamlit.selectbox(
            "X-Axis",
            swept_parameters,
            index=0,
            format_func=lambda x, p=parameters: p[x].display_name,
        )
        swept_parameters.remove(x_parameter)

        y_parameter = streamlit.selectbox(
            "Y-Axis",
            swept_parameters,
            index=0,
            format_func=lambda x, p=parameters: p[x].display_name,
        )
        swept_parameters.remove(y_parameter)

        scalar_swept_parameter = list(swept_parameters)[0]

        streamlit.write("Scalar Parameters")
        scalar_parameters = ALL_PARAMETERS - set([z_parameter, x_parameter, y_parameter])
        scalars = {}
        for parameter in scalar_parameters:
            config = parameters[parameter]
            scalars[parameter] = config.converter(
                streamlit.number_input(
                    config.display_name, value=config.default_value, format=config.format_str
                )
            )

    streamlit.header("Sweep Settings")
    min_col, max_col, num_col = streamlit.columns(3)

    x_config = parameters[x_parameter]
    y_config = parameters[y_parameter]

    x_name = x_config.display_name
    y_name = y_config.display_name

    with min_col:
        x_min = streamlit.number_input(f"{x_name} Min", value=x_config.sweep_default_min)
        y_min = streamlit.number_input(f"{y_name} Min", value=y_config.sweep_default_min)

    with max_col:
        x_max = streamlit.number_input(f"{x_name} Max", value=x_config.sweep_default_max)
        y_max = streamlit.number_input(f"{y_name} Max", value=y_config.sweep_default_max)

    with num_col:
        x_steps = streamlit.number_input(
            f"{x_name} Steps",
            value=x_config.sweep_default_steps,
            min_value=2,
            max_value=501,
            step=1,
        )
        y_steps = streamlit.number_input(
            f"{y_name} Steps",
            value=y_config.sweep_default_steps,
            min_value=2,
            max_value=501,
            step=1,
        )

    if x_steps is None or y_steps is None:
        streamlit.info("Swept parameter steps must be an integer.")
        return 0

    streamlit.divider()
    streamlit.header("Results")

    x = np.linspace(x_min, x_max, int(x_steps))
    y = np.linspace(y_min, y_max, int(y_steps))

    x_sweep = x_config.converter(x)
    y_sweep = y_config.converter(y)

    args = {
        parameters[x_parameter].arg_name: x_sweep,
        parameters[y_parameter].arg_name: y_sweep,
        **{parameters[s].arg_name: scalars[s] for s in scalar_parameters},
    }

    z, axis_parameters = functions[z_parameter](**args)

    z = z.transpose(
        axis_parameters.index(y_parameter),
        axis_parameters.index(x_parameter),
        axis_parameters.index(scalar_swept_parameter),
    )

    fig = go.Figure()
    fig.add_traces(
        [
            go.Heatmap(
                x=x,
                y=y,
                z=z[:, :, 0],
                colorscale=pc.sequential.Viridis,
            ),
            go.Contour(
                x=x,
                y=y,
                z=z[:, :, 0],
                contours={"coloring": "none", "showlabels": True},
                showlegend=False,
                showscale=False,
                connectgaps=False,
            ),
        ]
    )
    fig.update_layout(
        title={"text": parameters[z_parameter].display_name, "x": 0.5},
        xaxis={"title": parameters[x_parameter].display_name, "tickprefix": "$", "ticksuffix": "k"},
        yaxis={"title": parameters[y_parameter].display_name, "tickprefix": "$", "ticksuffix": "k"},
    )
    streamlit.plotly_chart(fig, width="content", height=600)


if __name__ == "__main__":
    main()
