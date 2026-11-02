"""Date-bound entry decisions and common accounting."""

import unittest
import numpy as np
import pandas as pd
from market_analytics.trading.forecast_filter import ForecastDecision, compare_backtest
from market_analytics.trading.backtest import simulate


class FilterTests(unittest.TestCase):
    def fixture(self, z):
        dates = pd.bdate_range('2026-01-02', periods=len(z))
        s = pd.Series(z, index=dates, dtype=float)
        prices = pd.DataFrame({'dependent_Open':10.,'independent_Open':20.,
                               'dependent_Close':11.,'independent_Close':19.},index=dates)
        return prices, s

    def test_acceptance_rejection_and_no_delayed_entry(self):
        p,z = self.fixture([-2.2,-2.3,0,-2.2,0,0])
        forecasts = pd.Series([-2.5,-1,0,-1.5,0,0],index=z.index)
        run = compare_backtest(p,z,.5,forecasts,set(z.index),previous_z=-1)
        self.assertEqual(run['signals']['action'].tolist(), ['hold','hold','hold','enter_long','exit','hold'])
        self.assertEqual(run['summary']['executed_entries'],1)
        self.assertEqual(run['summary']['filter_rejections'],1)
        self.assertTrue(run['signals'].iloc[0]['eligible_long'])
        # A rejection is a filter outcome, not an ignored crossing in the Phase 4 sense.
        self.assertTrue(run['signals'].iloc[0]['filter_rejected'])
        self.assertEqual(run['signals'].iloc[0]['ignored_reason'],'')
        self.assertEqual(run['summary']['ignored_crossings'],0)

    def test_exit_priority_tail_calendar_and_equality(self):
        p,z = self.fixture([-2.2,0,3,3])
        f = pd.Series([-1.,0],index=z.index[:2])
        run = compare_backtest(p,z,.5,f,set(z.index[:2]),previous_z=-1)
        self.assertEqual(run['signals'].iloc[1]['action'],'exit')
        self.assertEqual(run['summary']['closed_trades'],1)
        self.assertEqual(run['summary']['calendar_exclusions'],1)
        reject = ForecastDecision(z,pd.Series(z,index=z.index),set(z.index),previous_z=-1)
        self.assertEqual(reject(-1,-2.2,0)['action'],'hold')

    def test_always_accept_reproduces_existing_engine(self):
        p,z=self.fixture([-2.2,-2.3,0,0])
        plain=simulate(p,z,.5,previous_z=-1)
        filtered=compare_backtest(p,z,.5,pd.Series([-1,-1,0,0],index=z.index),set(z.index),previous_z=-1)
        for name in ['executions','trades','daily_account']:
            pd.testing.assert_frame_equal(plain[name],filtered[name])

    def test_missing_duplicate_keys_and_cursor_mismatch_fail(self):
        p,z=self.fixture([-2.2,0,3,0])
        with self.assertRaises(ValueError):
            ForecastDecision(z,pd.Series([],dtype=float),set(z.index))
        cb=ForecastDecision(z,z+1,set(z.index),previous_z=-1)
        with self.assertRaises(ValueError):
            cb(-1,-3,0)

    def test_short_filter_and_explicit_beta_sizing(self):
        p,z=self.fixture([2.2,0,0])
        result=compare_backtest(p,z,.25,z-1,set(z.index),previous_z=1)
        q=result['trades'].iloc[0]
        self.assertAlmostEqual(abs(q['q_independent']*20/(q['q_dependent']*10)),.25)

    def test_cursor_exhaustion_and_insolvency_stop(self):
        p,z=self.fixture([2.2,2.3,2.4,2.5])
        cb=ForecastDecision(z,z-1,set(z.index),previous_z=1)
        previous=1
        for value in z:
            cb(previous,float(value),0); previous=float(value)
        with self.assertRaises(ValueError): cb(previous,2.5,0)
        p.iloc[1,p.columns.get_loc('dependent_Close')]=1e8
        result=compare_backtest(p,z,.5,z-1,set(z.index),previous_z=1)
        self.assertEqual(result['summary']['status'],'incomplete_nonpositive_equity')
        self.assertEqual(len(result['daily_account']),2)
