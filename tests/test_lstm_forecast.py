"""Forecast measurements, checkpoint selection, and deterministic reload."""

import tempfile
import unittest
from pathlib import Path
import numpy as np
import pandas as pd
import torch
import json
import hashlib
import shutil
from unittest.mock import patch
from market_analytics.models.lstm import train_model, predict_changes, save_checkpoint, load_checkpoint, EarlyStopping
from market_analytics.models.forecasting import forecast_metrics, choose_candidate, forecast_from_prices, backtests, Store, signature, run_lstm_forecast, direction_base_rates


class ForecastTests(unittest.TestCase):
    def bundle(self, root):
        from market_analytics.models.lstm import SpreadLSTM
        from market_analytics.features.sequences import FEATURES
        dates=pd.bdate_range('2025-02-03',periods=45)
        prices=pd.DataFrame({'AMZN_Close':100+np.arange(45),'META_Close':200+np.arange(45)},index=dates)
        pair={'pair_id':'AMZN_META','dependent':'AMZN','independent':'META','evidence_label':'exploratory'}
        ols={**pair,'intercept':0.,'beta':.5}
        norm={**pair,'mean':0.,'std':1.,'ddof':1}
        scaler={**pair,'features':FEATURES,'mean':[0.]*5,'scale':[1.]*5,'ddof':0,'stage':'final','ols':ols,'normalization':norm}
        meta={'pair':pair,'feature_order':FEATURES,'target':'change_from_origin_z','lookback':20,'horizon':5,
              'settings':{'hidden_size':16},'ols':ols,'normalization':norm,'scaler':scaler,
              'training_sessions':[str(d.date()) for d in dates]}
        save_checkpoint(SpreadLSTM(16),root/'model.pt')
        meta['weights_sha256']=hashlib.sha256((root/'model.pt').read_bytes()).hexdigest()
        fields={k:meta[k] for k in ['pair','ols','normalization','scaler','training_sessions']}
        meta['preprocessing_sha256']=hashlib.sha256(json.dumps(fields,sort_keys=True).encode()).hexdigest()
        (root/'metadata.json').write_text(json.dumps(meta))
        return prices,meta

    def test_bundle_rejects_changed_normalization(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); prices,meta=self.bundle(root)
            meta['normalization']={**meta['normalization'],'mean':5.}
            (root/'metadata.json').write_text(json.dumps(meta))
            with self.assertRaises(ValueError):
                forecast_from_prices(prices,root)

    def test_inference_rejects_missing_interior_session(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); prices,meta=self.bundle(root)
            with self.assertRaises(ValueError):
                forecast_from_prices(prices.drop(prices.index[-10]),root)

    def test_missing_forecast_does_not_shrink_common_calendar(self):
        dates=pd.bdate_range('2026-01-02',periods=10)
        prior=dates[0]-pd.offsets.BDay(1)
        forecasts=pd.DataFrame({'origin':[prior,*dates[:-6]],'horizon':5,'forecast_z':0.})
        z=pd.Series(0.,index=pd.DatetimeIndex([prior,*dates]))
        pair={'pair_id':'AMZN_META','dependent':'AMZN','independent':'META','evidence_label':'exploratory'}
        prices=pd.DataFrame({s+'_'+f:10. for s in ['AMZN','META'] for f in ['Open','Close']},index=dates)
        baseline={'accounting':{'initial_capital':10000.,'cost_rate':.0005}}
        with tempfile.TemporaryDirectory() as d:
            store=Store(Path(d),{'model_version':'test','tolerance':{'rtol':1e-7,'atol':1e-9}})
            with self.assertRaises(ValueError):
                backtests(store,pair,{'z':z,'ols':{'beta':.5}},forecasts,prices,baseline,'unseen')

    def test_reused_code_and_lockfile_are_in_frozen_signature(self):
        project=Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            (root/'scripts').mkdir(); shutil.copy2(project/'scripts/run_lstm_forecast.py',root/'scripts/run_lstm_forecast.py')
            shutil.copy2(project/'uv.lock',root/'uv.lock')
            first=signature(root,{},{'hashes':{}})
            for name in ['models/forecasting.py','models/lstm.py','models/plots.py','features/sequences.py',
                         'trading/forecast_filter.py','trading/backtest.py','trading/signals.py','trading/baseline.py']:
                self.assertIn(f'src/market_analytics/{name}',first['code'])
            with open(root/'uv.lock','a',encoding='utf-8') as lock:
                lock.write('\n')
            self.assertNotEqual(signature(root,{},{'hashes':{}})['lock_sha256'],first['lock_sha256'])

    def test_standalone_refit_rejects_stale_selection_before_training(self):
        project=Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); (root/'configs').mkdir()
            shutil.copy2(project/'configs/lstm_forecast.json',root/'configs/lstm_forecast.json')
            version=json.loads((root/'configs/lstm_forecast.json').read_text())['model_version']
            metrics=root/f'outputs/metrics/lstm/{version}'; metrics.mkdir(parents=True)
            (metrics/'selection_metadata.json').write_text(json.dumps({'signature':{'old':True},'outputs':{}}))
            with patch('market_analytics.models.forecasting.historical_handoff',return_value=({'hashes':{}},{},{})), \
                 patch('market_analytics.models.forecasting.signature',return_value={'new':True}), \
                 patch('market_analytics.models.forecasting.refit',side_effect=AssertionError('stale selection reached training')):
                with self.assertRaises(ValueError):
                    run_lstm_forecast(root/'configs/lstm_forecast.json',stage='refit')

    def test_metrics_use_pooled_cells_and_zero_benchmark_status(self):
        rows=[]
        for origin in range(2):
            for h in range(1,6):
                rows.append({'origin':origin,'horizon':h,'target_date':origin+h,
                             'actual_z':0.,'forecast_z':float(h),'persistence_z':0.})
        m=forecast_metrics(pd.DataFrame(rows))
        pooled=m.loc[(m['model']=='lstm') & (m['horizon']=='pooled')].iloc[0]
        self.assertAlmostEqual(pooled['mae'],3.)
        self.assertAlmostEqual(pooled['rmse'],np.sqrt(11))
        self.assertTrue(pd.isna(pooled['rmse_improvement']))
        self.assertEqual(pooled['predictions'],10)

    def test_direction_base_rates_by_hand(self):
        h5=pd.DataFrame({'origin_z':[-2.,-1.,1.,3.],'actual_z':[-1.,-2.,2.,2.],
                         'resting_z':2.5,'predicted_change':[.1,.1,-.1,.1]})
        rates=direction_base_rates(h5)
        # Realized signs are +,-,+,-: two rises and two falls.
        self.assertEqual(rates['majority_sign_rate'],.5)
        self.assertEqual(rates['toward_resting_rate'],.75)
        self.assertEqual(rates['toward_zero_rate'],.5)
        self.assertEqual(rates['predicted_rise_share'],.75)

    def test_checkpoint_patience_and_config_ties(self):
        stopping=EarlyStopping(patience=2,min_delta=1e-6)
        for epoch, loss in enumerate([1.,.5,.5000001,.5000002],1):
            stopping.update(loss,epoch)
        self.assertEqual(stopping.best_epoch,2)
        self.assertTrue(stopping.stopped)
        rows=[{'hidden_size':32,'learning_rate':.001,'rmse':1.,'trial_id':'a'},
              {'hidden_size':16,'learning_rate':.0003,'rmse':1.0000001,'trial_id':'b'}]
        self.assertEqual(choose_candidate(rows)['trial_id'],'b')

    def test_seeded_training_reload_and_change_output(self):
        rng=np.random.default_rng(11)
        x=rng.normal(size=(12,20,5)).astype('float32'); y=np.zeros((12,5),dtype='float32')
        cfg={'hidden_size':16,'learning_rate':.001,'seed':42,'batch_size':4,
             'max_epochs':3,'patience':2,'min_delta':1e-6,'gradient_clip':1.}
        model,hist,best=train_model(x,y,cfg,validation=(x,y))
        a=predict_changes(model,x)
        other,_,_=train_model(x,y,cfg,validation=(x,y))
        np.testing.assert_array_equal(a,predict_changes(other,x))
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'model.pt'
            save_checkpoint(model,p)
            loaded=load_checkpoint(p,16)
            np.testing.assert_array_equal(a,predict_changes(loaded,x))
        self.assertEqual(a.shape,(12,5))
        self.assertTrue(1<=best<=3)
        self.assertEqual(len(hist),3)
        for param in model.parameters():
            param.data.zero_()
        np.testing.assert_array_equal(predict_changes(model,x),0.)
