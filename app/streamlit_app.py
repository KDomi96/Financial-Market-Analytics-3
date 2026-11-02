"""Streamlit interface for the pair analysis API.

It only sends requests and draws the responses: every number on the page comes
from the API, and uploaded files are forwarded unchanged.
"""

import os
from datetime import date

import altair as alt
import httpx
import pandas as pd
import streamlit as st

API_URL = os.environ.get("API_URL") or "http://localhost:8000"
TIMEOUT = 120

st.set_page_config(page_title="Pair analysis", layout="wide", initial_sidebar_state="expanded")
# A link such as ?pair=NVDA_AMZN&exploratory=1&run=1&forecast=1 opens a given view; the inputs stay editable.
PARAMS = st.query_params


def once(name):
    """True on the first script run when the URL asks for this action, so later reruns don't repeat it."""
    if PARAMS.get(name) != "1" or st.session_state.get(f"done_{name}"):
        return False
    st.session_state[f"done_{name}"] = True
    return True


def call(method, path, **kwargs):
    """Return (body, error message); the API's own message is shown when it rejects a request."""
    try:
        response = httpx.request(method, f"{API_URL}{path}", timeout=TIMEOUT, **kwargs)
    except httpx.HTTPError as exc:
        return None, f"Could not reach the API at {API_URL}: {exc}"
    if response.status_code >= 400:
        try:
            detail = response.json().get("detail", response.text)
        except ValueError:
            detail = response.text
        if isinstance(detail, list):  # FastAPI's own form-validation errors
            detail = "; ".join(f"{'/'.join(map(str, d.get('loc', [])))}: {d.get('msg')}" for d in detail)
        return None, f"{response.status_code}: {detail}"
    return (response.json() if "json" in response.headers.get("content-type", "") else response.content), None


@st.cache_data(ttl=60, show_spinner=False)
def pairs_and_health():
    return call("GET", "/pairs"), call("GET", "/health")


def number(value, digits=4):
    return f"{value:.{digits}f}"


def show_tests(result):
    tests = result["tests"]
    if tests["cointegrated"]:
        st.success(f"{result['pair_id']} is cointegrated at the {tests['alpha']:.0%} level on the fitting sessions: "
                   "both the Engle-Granger and Johansen rules pass.")
    else:
        st.error(f"{result['pair_id']} is not cointegrated at the {tests['alpha']:.0%} level on the fitting sessions.")
    fit = result["fit"]
    st.caption(f"Fitting sessions {fit['first_session']} to {fit['last_fit_session']} ({fit['fit_sessions']}); "
               f"{fit['later_sessions']} later sessions up to {fit['last_session']}.")

    johansen = tests["johansen"]
    left, middle, right = st.columns(3)
    verdict = {True: "pass", False: "fail"}
    left.metric(f"Engle-Granger p, direction-adjusted ({verdict[tests['eg_pass']]})",
                number(tests["eg_pair_pvalue"]))
    middle.metric(f"Johansen trace r=0 (95% critical {number(johansen['trace_critical_r0_95'], 2)})",
                  number(johansen["trace_stat_r0"], 2))
    right.metric(f"Johansen rank at 95% ({verdict[tests['johansen_pass']]})", johansen["trace_rank_95"])

    directions = pd.DataFrame(tests["directions"])
    directions.insert(0, "kept", (directions.dependent == tests["kept_dependent"]))
    st.markdown("**Engle-Granger, both directions** (log prices; the direction-adjusted p is "
                "min(1, 2 × the smaller p))")
    st.dataframe(directions.rename(columns={"eg_pvalue": "p", "eg_statistic": "statistic",
                                            "eg_critical_5": "5% critical", "usedlag": "ADF lags"}),
                 hide_index=True)
    with st.expander("Unit-root checks on each log price"):
        st.dataframe(pd.DataFrame(result["integration"]), hide_index=True)
    for warning in result["warnings"]:
        st.warning(warning)
    if result["phase3"]:
        note = result["phase3"]
        st.info(f"Phase 3 rank {note['rank']} of 15, label **{note['evidence_label']}** "
                f"(Holm-adjusted p {number(note['holm_pair_pvalue'])}). {note['note']}")


def zscore_chart(series, signals, fit_end, window_start):
    frame = pd.DataFrame(series).assign(date=lambda d: pd.to_datetime(d["date"]))
    x = alt.X("date:T", title=None, axis=alt.Axis(format="%b %Y"))
    spread = alt.Chart(frame).mark_line(strokeWidth=1).encode(x=x, y=alt.Y("spread:Q", title="Spread (log)"))
    # Z is only meaningful from the normalization window on, and the signals need room to be seen.
    recent = frame[frame.date >= pd.Timestamp(window_start)]
    z = alt.Chart(recent).mark_line(strokeWidth=1).encode(x=x, y=alt.Y("zscore:Q", title="Z-score"))
    bands = alt.Chart(pd.DataFrame({"y": [-2, 0, 2]})).mark_rule(strokeDash=[4, 4], color="#8aa0c0").encode(y="y:Q")
    cut = alt.Chart(pd.DataFrame({"date": [pd.Timestamp(fit_end)]})).mark_rule(color="#f2c94c").encode(x="date:T")
    events = pd.DataFrame(signals).query("action != 'hold'")
    layers = [z, bands, cut]
    if not events.empty:
        events = events.assign(date=lambda d: pd.to_datetime(d["date"]))
        layers.append(alt.Chart(events).mark_point(size=70, filled=True).encode(
            x="date:T", y="zscore:Q",
            color=alt.Color("action:N", scale=alt.Scale(domain=["enter_long", "enter_short", "exit"],
                                                        range=["#3fb950", "#ff6b6b", "#e6edf7"])),
            shape="action:N", tooltip=["date:T", "action:N", alt.Tooltip("zscore:Q", format=".3f")]))
    st.altair_chart((spread + cut).properties(height=220), width="stretch")
    st.altair_chart(alt.layer(*layers).properties(height=260), width="stretch")


def show_spread(result):
    st.subheader("Spread and Z-score")
    if result["view"] == "exploratory":
        st.warning("Exploratory view: this pair failed the test, so these values are not evidence of "
                   "mean reversion.")
    reg, norm = result["regression"], result["normalization"]
    st.caption(f"Spread = log({reg['dependent']}) − {number(reg['intercept'])} − {number(reg['beta'])} × "
               f"log({reg['independent']}). Z uses mean {number(norm['mean'], 6)} and standard deviation "
               f"{number(norm['std'], 6)} from {norm['nobs']} sessions, {norm['fit_start']} to {norm['fit_end']}. "
               "The spread chart covers every session; the Z-score chart starts at that window. "
               "The yellow line marks the fit end; dashed lines are Z = −2, 0, 2.")
    zscore_chart(result["series"], result["signals"], result["fit"]["last_fit_session"], norm["fit_start"])

    st.subheader("Signals after the fit end")
    counts = result["signal_counts"]
    columns = st.columns(5)
    for column, (label, key) in zip(columns, [("Long entries", "long_entries"), ("Short entries", "short_entries"),
                                              ("Exits", "exits"), ("Long crossings", "long_crossings"),
                                              ("Short crossings", "short_crossings")]):
        column.metric(label, counts[key])
    st.caption("Rules: enter long when Z crosses below −2 and short when it crosses above 2 while flat; "
               "exit when Z returns to 0. Each signal is acted on at the next session, so the position shown "
               "on a row is the one held when that row's decision is made. No profit and loss is computed here.")
    signals = pd.DataFrame(result["signals"])
    active = signals[(signals.action != "hold") | signals.long_crossing | signals.short_crossing]
    st.dataframe(active[["date", "previous_z", "zscore", "position", "action", "ignored_reason"]],
                 hide_index=True)
    with st.expander(f"All {len(signals)} sessions"):
        st.dataframe(signals, hide_index=True)


def show_forecast(content, pair_id, last_session):
    st.subheader("Saved LSTM forecast")
    st.caption("This uses the Phase 5 model trained on 2018-2025 with its own fixed spread, not the fit above.")
    origin = st.date_input("Forecast from the close of", value=date.fromisoformat(PARAMS.get("origin", "2026-03-16")),
                           max_value=date.fromisoformat(last_session), key="origin")
    if st.button("Forecast five sessions") or once("forecast"):
        body, error = call("POST", "/forecast", files={"file": ("prices.csv", content, "text/csv")},
                           data={"pair": pair_id, "origin": origin.isoformat()})
        st.session_state["forecast"], st.session_state["forecast_error"] = body, error
    if st.session_state.get("forecast_error"):
        st.error(st.session_state["forecast_error"])
    forecast = st.session_state.get("forecast")
    if forecast and forecast["pair_id"] == pair_id:
        st.write(f"Origin {forecast['origin']}, Z = {number(forecast['origin_z'])}. Day-five change "
                 f"{number(forecast['day_five_change'])} ({forecast['day_five_direction']}).")
        st.dataframe(pd.DataFrame(forecast["forecasts"]), hide_index=True)
        st.info(forecast["note"])


st.title("Pair cointegration and signals")
(pairs, pairs_error), (health, _) = pairs_and_health()
if pairs_error:
    st.error(pairs_error)
    st.stop()
if health and health["status"] != "ok":
    failed = ", ".join(b["pair_id"] for b in health["bundles"] if b["status"] != "ok")
    st.warning(f"Forecasts are unavailable for {failed}: the saved model failed its startup check.")

with st.sidebar:
    st.header("Input")
    source = st.radio("Prices", ["Project prices", "Upload a CSV"])
    if source == "Project prices":
        names = [p["pair_id"] for p in pairs["pairs"]]
        pair_id = st.selectbox("Pair", names, index=names.index(PARAMS.get("pair", "AMZN_META"))
                               if PARAMS.get("pair") in names else names.index("AMZN_META"))
        upload = None
        st.caption(f"Daily closes from {pairs['first_session']} to {pairs['last_session']}.")
    else:
        pair_id = None
        upload = st.file_uploader("CSV with a header Date,<TICKER_A>,<TICKER_B>", type=["csv"])
        st.caption("Dates as YYYY-MM-DD in increasing order, one closing price per ticker, no blanks.")
    fit_end = st.date_input("Fit end", value=date.fromisoformat(PARAMS.get("fit_end", pairs["default_fit_end"])))
    exploratory = st.checkbox("Show spread and signals even if the pair fails",
                              value=PARAMS.get("exploratory") == "1")
    run = st.button("Run analysis", type="primary") or once("run")

if run:
    if source == "Project prices":
        content, error = call("GET", f"/samples/{pair_id}")
    else:
        content, error = (upload.getvalue(), None) if upload else (None, "Choose a CSV file first.")
    result = None
    if not error:
        result, error = call("POST", "/analyze", files={"file": ("prices.csv", content, "text/csv")},
                             data={"fit_end": fit_end.isoformat(), "exploratory": str(exploratory).lower()})
    st.session_state.update(result=result, error=error, content=content, forecast=None, forecast_error=None)

if st.session_state.get("error"):
    st.error(st.session_state["error"])
result = st.session_state.get("result")
if result:
    show_tests(result)
    if result["series"]:
        show_spread(result)
    else:
        st.write("The spread, Z-scores and signals are only shown for a pair that passes. "
                 "Tick the exploratory option to see them anyway.")
    bundles = {p["pair_id"] for p in pairs["pairs"] if p["has_forecast_model"]}
    if result["pair_id"] in bundles:
        show_forecast(st.session_state["content"], result["pair_id"], pairs["last_session"])
elif not run:
    st.write("Choose a pair or upload prices in the sidebar, then run the analysis.")
