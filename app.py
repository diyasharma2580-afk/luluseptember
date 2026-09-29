"""
LuLu UAE Sales Dashboard  (app.py)
==================================
A Streamlit dashboard built on SYNTHETIC (made-up) LuLu-style sales data.

How the filters work
--------------------
1. GLOBAL filters (date range + emirates) sit in the box at the top.
   They change EVERY chart on the page.
2. LOCAL filters sit behind the "Filters" button on each chart.
   They change ONLY that one chart, on top of the global filters.

Why each chart is wrapped in @st.fragment
-----------------------------------------
Normally, touching ANY widget makes Streamlit re-run the whole script.
A "fragment" is a piece of the page that can re-run on its own.
So when you change a chart's local filter, only that chart is redrawn.

Run it on your own computer:
    pip install -r requirements.txt
    streamlit run app.py
"""

from datetime import timedelta
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

# =============================================================================
# 1. PAGE SETUP  (must be the first Streamlit command in the file)
# =============================================================================
st.set_page_config(page_title="LuLu UAE Sales Dashboard", page_icon="🛒", layout="wide")

# Pink & purple theme + bold, underlined headings
st.markdown(
    """
    <style>
    .stApp { background: linear-gradient(180deg, #FDF2F8 0%, #F5F0FF 100%); }
    h1, h2, h3, h4 {
        font-weight: 800 !important;
        text-decoration: underline !important;
        text-decoration-color: #EC4899;
        text-decoration-thickness: 3px;
        text-underline-offset: 6px;
        color: #581C87 !important;
    }
    [data-testid="stCaptionContainer"] { color: #7E22CE; }
    [data-testid="stMetric"] { background: #FFFFFF; border-color: #E9D5FF !important; }
    [data-testid="stVerticalBlockBorderWrapper"] { border-color: #E9D5FF; background: rgba(255,255,255,0.6); }
    [data-testid="stMetricValue"] { color: #6B21A8; }
    .stButton > button, [data-testid="stPopover"] button, .stDownloadButton > button {
        border-color: #C084FC; color: #6B21A8;
    }
    .stButton > button:hover, [data-testid="stPopover"] button:hover, .stDownloadButton > button:hover {
        border-color: #EC4899; color: #BE185D; background: #FDF2F8;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# =============================================================================
# 2. SETTINGS USED ACROSS THE APP
# =============================================================================
# The CSV sits in the same folder as this file. Building the path from
# __file__ means it is found both on your laptop and on Streamlit Cloud.
DATA_FILE = Path(__file__).parent / "lulu_sales_data.csv"

CATEGORIES = ["Fresh", "Grocery", "Fashion", "Home Decor", "Electronics", "Furniture"]
EMIRATES = ["Dubai", "Abu Dhabi", "Sharjah", "Ajman", "Ras Al Khaimah", "Fujairah", "Umm Al Quwain"]
AGE_GROUPS = ["18-24", "25-34", "35-44", "45-54", "55+"]
FESTIVE_SEASONS = ["White Friday", "DSF", "Ramadan", "Back to School"]

# Each category always gets the SAME colour in every chart, so viewers
# learn the colours once and can read every chart faster.
CATEGORY_COLORS = {
    "Fresh": "#F48FB1",        # light pink
    "Grocery": "#D81B60",      # deep pink
    "Fashion": "#EC4899",      # hot pink
    "Home Decor": "#C084FC",   # lavender
    "Electronics": "#7E22CE",  # vivid purple
    "Furniture": "#4A148C",    # dark violet
}
OTHER_COLORS = ["#7E22CE", "#EC4899", "#C084FC", "#F9A8D4"]   # for charts not split by category
PINK_PURPLE_SCALE = ["#FCE4F3", "#F9A8D4", "#EC4899", "#A855F7", "#581C87"]   # light pink -> dark purple
DIVERGING_SCALE = ["#BE185D", "#F9A8D4", "#FDF2F8", "#D8B4FE", "#6B21A8"]     # negative pink -> positive purple
CHART_HEIGHT = 380                                          # same height for every chart

# The measures a user can choose, and the column each one comes from.
METRIC_COLUMNS = {
    "Net sales (AED)": "Net_Sales_AED",
    "Profit (AED)": "Profit_AED",
    "Units sold": "Units_Sold",
    "Transactions": "Transaction_ID",
}


# =============================================================================
# 3. LOAD THE DATA
# =============================================================================
# @st.cache_data = "read the file once, then remember it".
# Without it, the CSV would be re-read every time anyone clicks anything.
#
# ➡️ LIVE VERSION (later): change this to @st.cache_data(ttl=5)
#    so Streamlit re-reads the file every 5 seconds and picks up new rows.
@st.cache_data
def load_data():
    return pd.read_csv(DATA_FILE, parse_dates=["Timestamp", "Date"])


# =============================================================================
# 4. HELPER FUNCTIONS  (small reusable pieces used by the charts)
# =============================================================================
def aed(value):
    """Turn a number into a short money label, e.g. 1234567 -> 'AED 1.23M'."""
    if abs(value) >= 1_000_000:
        return f"AED {value / 1_000_000:.2f}M"
    if abs(value) >= 1_000:
        return f"AED {value / 1_000:.1f}K"
    return f"AED {value:,.0f}"


def filter_rows(data, start, end, emirates):
    """Keep only rows between two dates AND inside the chosen emirates."""
    in_dates = data["Date"].between(pd.Timestamp(start), pd.Timestamp(end))
    in_emirates = data["Emirate"].isin(emirates)
    return data[in_dates & in_emirates]


def chosen_emirates():
    """Emirates picked in the global filter. Picking nothing means 'all emirates'."""
    return st.session_state["global_emirates"] or EMIRATES


def get_global_data():
    """Every chart starts here: the full data with the GLOBAL filters applied.

    The global widgets save their values in st.session_state (Streamlit's
    memory), so any chart can read them, even when only that chart re-runs.
    """
    start, end = st.session_state["global_dates"]
    return filter_rows(load_data(), start, end, chosen_emirates())


def emirates_in(data):
    """Emirates that appear in the data, in our standard order."""
    present = set(data["Emirate"])
    return [e for e in EMIRATES if e in present]


def summarise(data, group_by, metric):
    """Group the data (e.g. by Category) and calculate one measure per group.

    Most measures are simple totals. Two need special maths:
      * Transactions      -> count the rows
      * Profit margin (%) -> total profit / total net sales x 100
      * Average rating    -> the average (mean) of the ratings
    """
    groups = data.groupby(group_by)
    if metric == "Transactions":
        result = groups["Transaction_ID"].count()
    elif metric == "Profit margin (%)":
        result = groups["Profit_AED"].sum() / groups["Net_Sales_AED"].sum() * 100
    elif metric == "Average rating (1-5)":
        result = groups["Customer_Rating"].mean()
    else:
        result = groups[METRIC_COLUMNS[metric]].sum()
    return result.rename(metric).reset_index()


def card_header(title, wide=False):
    """Draw a chart title with a 'Filters' button on its right.

    Returns the pop-over (the little menu that opens when you click the
    button). Anything created inside  `with card_header(...):`  goes in it.
    """
    title_col, button_col = st.columns([6, 1] if wide else [3, 1], vertical_alignment="center")
    title_col.markdown(f"#### {title}")
    return button_col.popover("Filters", icon=":material/tune:", width="stretch")


def local_select(label, options, key):
    """A dropdown that never gets 'stuck' on an option that has disappeared.

    Example: you pick 'Ajman' in a chart, then remove Ajman in the global
    filter. The old choice is no longer valid, so we reset it to the first
    option ('All ...') before drawing the dropdown.
    """
    if st.session_state.get(key) not in options:
        st.session_state[key] = options[0]
    return st.selectbox(label, options, key=key)


def show_active_filters(*choices):
    """The filters hide inside a pop-over, so print the current choices under the title."""
    st.caption("Showing: " + ", ".join(choices))


def no_data_message():
    st.info("No transactions match these filters. Widen them using the Filters button.")


def style(fig):
    """Give every Plotly chart the same size, margins and legend position."""
    fig.update_layout(
        height=CHART_HEIGHT,
        margin=dict(l=0, r=0, t=10, b=0),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0, title_text=""),
        colorway=OTHER_COLORS,
        font=dict(color="#4A148C"),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    return fig


# =============================================================================
# 5. THE CHARTS
# Each function below draws one card: title + Filters button + chart.
# @st.fragment lets each card re-run on its own when its local filters change.
#
# ➡️ LIVE VERSION (later): change @st.fragment to @st.fragment(run_every="5s")
#    and the card will refresh itself every 5 seconds.
# =============================================================================

# ----------------------------------------------------------------- KPI strip
def calc_kpis(data):
    """The five headline numbers for a slice of data."""
    net = data["Net_Sales_AED"].sum()
    count = len(data)
    return {
        "net": net,
        "transactions": count,
        "units": data["Units_Sold"].sum(),
        "avg_value": net / count if count else 0,
        "margin": data["Profit_AED"].sum() / net * 100 if net else 0,
    }


def pct_change(now, before):
    """'+12.3%' style change label, or None when there is nothing to compare with."""
    if before is None or before == 0:
        return None
    return f"{(now - before) / abs(before) * 100:+.1f}%"


@st.fragment
def kpi_row():
    data = get_global_data()

    # Compare with the period just before, of the same length.
    # (With the full year selected there is no earlier data, so no arrows.)
    start, end = st.session_state["global_dates"]
    period_days = (end - start).days + 1
    prev_end = start - timedelta(days=1)
    prev_start = prev_end - timedelta(days=period_days - 1)
    previous = filter_rows(load_data(), prev_start, prev_end, chosen_emirates())

    now = calc_kpis(data)
    before = calc_kpis(previous) if not previous.empty else {k: None for k in now}

    # Month-by-month values for the small sparkline inside each KPI box
    by_month = data.groupby(data["Date"].dt.to_period("M"))
    monthly_net = by_month["Net_Sales_AED"].sum()
    monthly_count = by_month["Transaction_ID"].count()
    sparklines = {
        "net": monthly_net.round(0).tolist(),
        "transactions": monthly_count.tolist(),
        "units": by_month["Units_Sold"].sum().tolist(),
        "avg_value": (monthly_net / monthly_count).round(1).tolist(),
        "margin": (by_month["Profit_AED"].sum() / monthly_net * 100).round(1).tolist(),
    }

    margin_delta = None if before["margin"] is None else f"{now['margin'] - before['margin']:+.1f} pts"
    compare_help = "Arrow = change vs the previous period of the same length (shown when that period is in the data)."

    boxes = [
        ("Net sales", aed(now["net"]), pct_change(now["net"], before["net"]), "net"),
        ("Transactions", f"{now['transactions']:,}", pct_change(now["transactions"], before["transactions"]), "transactions"),
        ("Units sold", f"{now['units']:,}", pct_change(now["units"], before["units"]), "units"),
        ("Avg. transaction value", aed(now["avg_value"]), pct_change(now["avg_value"], before["avg_value"]), "avg_value"),
        ("Profit margin", f"{now['margin']:.1f}%", margin_delta, "margin"),
    ]
    for column, (label, value, delta, spark_key) in zip(st.columns(5), boxes):
        column.metric(label, value, delta, border=True, help=compare_help,
                      chart_data=sparklines[spark_key], chart_type="area")


# --------------------------------------------------------- Sales by category
@st.fragment
def sales_by_category_card():
    data = get_global_data()
    with st.container(border=True):
        with card_header("Sales by category"):
            emirate = local_select("Emirate", ["All emirates"] + emirates_in(data), key="cat_emirate")
            metric = st.radio("Measure", list(METRIC_COLUMNS), key="cat_metric")

        if emirate != "All emirates":
            data = data[data["Emirate"] == emirate]
        show_active_filters(emirate, metric)
        if data.empty:
            return no_data_message()

        summary = summarise(data, "Category", metric)
        fig = px.bar(summary, x=metric, y="Category", orientation="h", text_auto=".3s",
                     color="Category", color_discrete_map=CATEGORY_COLORS)
        fig.update_layout(showlegend=False, yaxis_title=None)
        fig.update_yaxes(categoryorder="total ascending")   # biggest bar at the top
        st.plotly_chart(style(fig), key="chart_category")


# ------------------------------------------------- Emirate x Category heatmap
@st.fragment
def emirate_heatmap_card():
    data = get_global_data()
    with st.container(border=True):
        with card_header("Emirate × category heatmap"):
            metric = st.radio("Measure", ["Net sales (AED)", "Profit (AED)", "Profit margin (%)", "Transactions"],
                              key="heat_metric")
            channel = st.selectbox("Sales channel", ["All channels", "In-store", "Online", "Click & Collect"],
                                   key="heat_channel")

        if channel != "All channels":
            data = data[data["Sales_Channel"] == channel]
        show_active_filters(metric, channel)
        if data.empty:
            return no_data_message()

        # Turn the long table into a grid: one row per emirate, one column per category
        grid = (summarise(data, ["Emirate", "Category"], metric)
                .pivot(index="Emirate", columns="Category", values=metric)
                .reindex(index=emirates_in(data), columns=CATEGORIES))

        is_margin = metric == "Profit margin (%)"
        if not is_margin:
            grid = grid.fillna(0)   # no sales = 0 (a margin with no sales is left blank)

        fig = px.imshow(
            grid, aspect="auto",
            text_auto=".1f" if is_margin else ".3s",
            # Margin can be negative, so use a pink-to-purple scale centred on 0
            color_continuous_scale=DIVERGING_SCALE if is_margin else PINK_PURPLE_SCALE,
            color_continuous_midpoint=0 if is_margin else None,
            labels=dict(x="", y="", color=""),
        )
        st.plotly_chart(style(fig), key="chart_heatmap")


# ------------------------------------------------------------
