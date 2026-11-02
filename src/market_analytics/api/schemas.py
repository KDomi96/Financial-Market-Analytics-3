"""Response models; they fix the JSON the interface relies on and appear on the /docs page."""

from typing import Literal

from pydantic import BaseModel


class BundleStatus(BaseModel):
    pair_id: str
    status: Literal["ok", "failed"]
    model_version: str | None
    max_abs_difference: float | None
    error: str | None


class Health(BaseModel):
    status: Literal["ok", "degraded"]
    bundles: list[BundleStatus]


class PairInfo(BaseModel):
    pair_id: str
    tickers: list[str]
    rank: int
    evidence_label: str
    dependent: str
    independent: str
    has_forecast_model: bool


class Pairs(BaseModel):
    tickers: list[str]
    default_fit_end: str
    first_session: str
    last_session: str
    pairs: list[PairInfo]


class FitWindow(BaseModel):
    fit_end: str
    first_session: str
    last_fit_session: str
    last_session: str
    fit_sessions: int
    later_sessions: int


class Direction(BaseModel):
    dependent: str
    independent: str
    intercept: float
    beta: float
    r_squared: float
    eg_statistic: float
    eg_pvalue: float
    eg_critical_5: float
    usedlag: int


class Johansen(BaseModel):
    levels_lag: int
    trace_stat_r0: float
    trace_critical_r0_95: float
    trace_stat_r1: float
    trace_critical_r1_95: float
    trace_rank_95: int


class Tests(BaseModel):
    alpha: float
    directions: list[Direction]
    kept_dependent: str
    kept_independent: str
    johansen: Johansen
    eg_pair_pvalue: float
    eg_pass: bool
    johansen_pass: bool
    cointegrated: bool


class Integration(BaseModel):
    symbol: str
    transform: str
    pvalue: float
    i1_status: str


class Phase3Note(BaseModel):
    rank: int
    evidence_label: str
    dependent: str
    independent: str
    eg_pvalue: float
    holm_pair_pvalue: float
    note: str


class Regression(BaseModel):
    dependent: str
    independent: str
    intercept: float
    beta: float


class Normalization(BaseModel):
    mean: float
    std: float
    ddof: int
    fit_start: str
    fit_end: str
    nobs: int


class SeriesPoint(BaseModel):
    date: str
    spread: float
    zscore: float
    fitting: bool


class Signal(BaseModel):
    date: str
    previous_z: float
    zscore: float
    position: int
    outside_long: bool
    outside_short: bool
    long_crossing: bool
    short_crossing: bool
    eligible_long: bool
    eligible_short: bool
    exit_signal: bool
    action: str
    ignored_reason: str


class SignalCounts(BaseModel):
    long_crossings: int
    short_crossings: int
    long_entries: int
    short_entries: int
    exits: int


class Analysis(BaseModel):
    pair_id: str
    tickers: list[str]
    project_pair: bool
    fit: FitWindow
    tests: Tests
    integration: list[Integration]
    warnings: list[str]
    phase3: Phase3Note | None
    view: Literal["cointegrated", "exploratory", "tests_only"]
    regression: Regression | None
    normalization: Normalization | None
    series: list[SeriesPoint] | None
    signals: list[Signal] | None
    signal_counts: SignalCounts | None


class ForecastPoint(BaseModel):
    horizon: int
    target_date: str | None
    forecast_z: float


class Forecast(BaseModel):
    pair_id: str
    model_version: str
    dependent: str
    independent: str
    training_end: str
    origin: str
    origin_z: float
    forecasts: list[ForecastPoint]
    day_five_change: float
    day_five_direction: Literal["up", "down", "flat"]
    note: str
