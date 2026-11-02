"""Bind dated forecasts to the existing close-time signal interface."""

import numpy as np
import pandas as pd
from market_analytics.trading.signals import decide_signal
from market_analytics.trading.backtest import simulate
from market_analytics.features.sequences import check_dates


class ForecastDecision:
    """Consume one dated context for each call made by the accounting engine."""

    def __init__(self, z, forecasts, eligible_dates, *, previous_z=None):
        check_dates(z)
        if not np.isfinite(z).all():
            raise ValueError('Non-finite Z context')
        self.z, self.previous_z, self.calls = z.copy(), previous_z, 0
        self.eligible = set(pd.DatetimeIndex(list(eligible_dates)))
        if not self.eligible.issubset(set(z.index)):
            raise ValueError('Entry calendar includes an absent session')
        self.forecasts = None if forecasts is None else forecasts.copy()
        if forecasts is not None:
            check_dates(forecasts)
            if not np.isfinite(forecasts).all() or not self.eligible.issubset(set(forecasts.index)):
                raise ValueError('Forecasts do not cover the entry calendar')

    def __call__(self, previous_z, z, position, entry_threshold=2., exit_threshold=0.):
        if self.calls >= len(self.z):
            raise ValueError('Decision cursor exhausted')
        expected_previous = self.previous_z if self.calls==0 else float(self.z.iloc[self.calls-1])
        if previous_z != expected_previous or z != float(self.z.iloc[self.calls]):
            raise ValueError('Decision context differs from dated Z values')
        date = self.z.index[self.calls]
        self.calls += 1
        decision = decide_signal(previous_z,z,position,entry_threshold,exit_threshold)
        entry = decision['eligible_long'] or decision['eligible_short']
        allowed = date in self.eligible
        forecast = float(self.forecasts.loc[date]) if self.forecasts is not None and date in self.forecasts.index else np.nan
        accepted = bool(entry and allowed and (self.forecasts is None or
                       (forecast>z if decision['eligible_long'] else forecast<z)))
        decision.update(entry_calendar_eligible=allowed, forecast_z_h5=forecast,
                        predicted_change_h5=forecast-z, entry_accepted=accepted,
                        calendar_excluded=bool(entry and not allowed),
                        filter_rejected=bool(entry and allowed and not accepted))
        # Rejections are recorded in the filter columns; ignored_reason keeps its
        # Phase 4 meaning so summary counts stay comparable with that baseline.
        if entry and not accepted:
            decision['action']='hold'
        return decision


def compare_backtest(prices,z,beta,forecasts,eligible_dates,*,previous_z=None,capital=10000.,cost_rate=.0005):
    decision = ForecastDecision(z,forecasts,eligible_dates,previous_z=previous_z)
    run = simulate(prices,z,beta,previous_z=previous_z,capital=capital,cost_rate=cost_rate,decision=decision)
    if decision.calls != len(run['daily_account']):
        raise AssertionError('Decision calls differ from daily account rows')
    s = run['signals']
    run['summary'].update(filter_rejections=int(s['filter_rejected'].sum()),
                          calendar_exclusions=int(s['calendar_excluded'].sum()),
                          accepted_entries=int(s['entry_accepted'].sum()),
                          submitted_orders=int(s['action'].ne('hold').sum()),
                          entry_eligible_origins=int(s['entry_calendar_eligible'].sum()))
    return run
