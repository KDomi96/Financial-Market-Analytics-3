"""Known windows, change targets, and training-only transformations."""

import unittest
import numpy as np
import pandas as pd
from market_analytics.features.sequences import (
    build_features, build_sequences, build_inference_inputs, fit_feature_scaler,
    apply_feature_scaler, training_input_rows, fit_selection_spread,
)


class SequenceTests(unittest.TestCase):
    def setUp(self):
        self.z = pd.Series(np.arange(100.), index=pd.bdate_range('2023-09-01', periods=100))

    def test_windows_and_changes_have_explicit_dates(self):
        f = build_features(self.z)
        b = build_sequences(f, self.z, str(self.z.index[0].date()), str(self.z.index[-1].date()))
        self.assertEqual(b['X'].shape, (57, 20, 5))
        np.testing.assert_array_equal(b['y'][0], [1, 2, 3, 4, 5])
        np.testing.assert_array_equal(b['X'][0, -1, :4], [38, 37, 36, 35])
        self.assertAlmostEqual(f.iloc[38, 4], np.std(np.arange(20.), ddof=1))
        self.assertAlmostEqual(b['X'][0, -1, 4], np.std(np.arange(20.), ddof=1), places=6)
        self.assertEqual(b['index'].iloc[0]['origin'], self.z.index[38])
        self.assertEqual(b['index'].iloc[0]['target_h5'], self.z.index[43])

    def test_target_cutoff_and_prior_context(self):
        f = build_features(self.z)
        a = build_sequences(f, self.z, self.z.index[0], self.z.index[69])
        b = build_sequences(f, self.z, self.z.index[70], self.z.index[-1])
        self.assertEqual(a['index'].iloc[-1]['target_h5'], self.z.index[69])
        self.assertEqual(b['index'].iloc[0]['origin'], self.z.index[69])
        self.assertEqual(b['index'].iloc[0]['target_h1'], self.z.index[70])
        later = self.z.copy(); later.iloc[70:] += 1000
        changed = build_sequences(build_features(later), later, self.z.index[0], self.z.index[69])
        np.testing.assert_array_equal(a['X'], changed['X'])
        np.testing.assert_array_equal(a['y'], changed['y'])

    def test_unique_scaler_rows_and_constant_column(self):
        f = build_features(self.z)
        b = build_sequences(f, self.z, self.z.index[0], self.z.index[69])
        rows = training_input_rows(f, b['index'])
        self.assertEqual(len(rows), 46)
        rows = rows.copy(); rows['rolling_std'] = 2.
        scaler = fit_feature_scaler(rows)
        self.assertEqual(scaler['constant_columns'], ['rolling_std'])
        scaled = apply_feature_scaler(rows, scaler)
        np.testing.assert_allclose(scaled.mean(), 0., atol=1e-14)
        with self.assertRaises(ValueError):
            apply_feature_scaler(rows[rows.columns[::-1]], scaler)

    def test_inference_needs_no_future_target(self):
        f = build_features(self.z)
        inputs = build_inference_inputs(f.iloc[:39], [self.z.index[38]])
        self.assertEqual(inputs.shape, (1, 20, 5))
        with self.assertRaises(ValueError):
            build_inference_inputs(f.iloc[:38], [self.z.index[37]])
        with self.assertRaises(ValueError):
            build_features(pd.concat([self.z, self.z.iloc[-1:]]))

    def test_earlier_ols_and_normalization_ignore_later_prices(self):
        d = pd.bdate_range('2022-01-03', '2025-12-31')
        x = np.linspace(3, 6, len(d))
        p = pd.DataFrame({'X_Close':np.exp(x), 'Y_Close':np.exp(.2+.6*x+.01*np.sin(np.arange(len(d))))}, index=d)
        pair = {'dependent':'Y','independent':'X'}
        ols, norm = fit_selection_spread(p, pair, '2023-12-31')
        p.loc['2024':, 'Y_Close'] *= 10
        second = fit_selection_spread(p, pair, '2023-12-31')
        self.assertEqual((ols,norm), second)
        self.assertEqual(norm['fit_end'], '2023-12-29')
        self.assertAlmostEqual(norm['resting_z'], -norm['mean']/norm['std'])
