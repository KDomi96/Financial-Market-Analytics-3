"""Select, refit, and evaluate the two exploratory spread models."""

import argparse
import hashlib
import json
import platform
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
import torch

from market_analytics.data.master import project_path, sha256
from market_analytics.features.sequences import (
    FEATURES, build_features, build_sequences, build_inference_inputs,
    fit_feature_scaler, apply_feature_scaler, training_input_rows, fit_selection_spread,
)
from market_analytics.trading.baseline import read_handoff, spread_from_prices, apply_normalization, validate_prices
from market_analytics.trading.forecast_filter import compare_backtest
from market_analytics.models.lstm import train_model, predict_changes, checkpoint_bytes, load_checkpoint


def forecast_metrics(forecasts):
    rows=[]
    for horizon in [str(h) for h in range(1,6)]+['pooled']:
        frame=forecasts if horizon=='pooled' else forecasts.loc[forecasts['horizon'].eq(int(horizon))]
        if frame.empty:
            continue
        base=frame['persistence_z'].to_numpy()-frame['actual_z'].to_numpy()
        base_rmse=float(np.sqrt(np.mean(base**2)))
        for model,column in [('lstm','forecast_z'),('persistence','persistence_z')]:
            error=frame[column].to_numpy()-frame['actual_z'].to_numpy()
            if not np.isfinite(error).all():
                raise ValueError('Non-finite forecast errors')
            rmse=float(np.sqrt(np.mean(error**2)))
            rows.append({'model':model,'horizon':horizon,'mae':float(np.abs(error).mean()),'rmse':rmse,
                         'rmse_improvement':1-rmse/base_rmse if base_rmse else np.nan,
                         'origins':frame['origin'].nunique(),'predictions':len(frame),
                         'unique_target_dates':frame['target_date'].nunique()})
    return pd.DataFrame(rows)


def direction_base_rates(h5):
    """Accuracy of simple no-model direction rules on the same origins."""
    realized=np.sign(h5['actual_z']-h5['origin_z'])
    return {'majority_sign_rate':float(max((realized>0).mean(),(realized<0).mean())),
            'toward_resting_rate':float((np.sign(h5['resting_z']-h5['origin_z'])==realized).mean()),
            'toward_zero_rate':float((np.sign(-h5['origin_z'])==realized).mean()),
            'predicted_rise_share':float((h5['predicted_change']>0).mean())}


def filter_decisions(runs,forecasts,resting_z,pair,period):
    """List each state-eligible filtered entry with its forecast and later outcome."""
    s=runs[('lstm_filtered','run')]['signals']
    s=s.loc[s['eligible_long']|s['eligible_short']].copy()
    h5=forecasts.loc[forecasts['horizon'].eq(5)].copy()
    h5['Date']=h5['origin'].dt.strftime('%Y-%m-%d')
    # Realized values are joined after the backtest has finished; they describe outcomes only.
    s=s.merge(h5[['Date','target_date','actual_z']],on='Date',how='left')
    s['direction']=np.where(s['eligible_long'],'long','short')
    s['resting_z']=resting_z
    s['realized_change_h5']=s['actual_z']-s['zscore']
    s['direction_correct']=np.where(s['actual_z'].notna(),
                                    np.sign(s['predicted_change_h5'])==np.sign(s['realized_change_h5']),np.nan)
    columns=['Date','direction','zscore','forecast_z_h5','predicted_change_h5','resting_z','entry_calendar_eligible',
             'entry_accepted','filter_rejected','calendar_excluded','order_status','execution_date',
             'target_date','actual_z','realized_change_h5','direction_correct']
    result=annotate(s[columns].rename(columns={'target_date':'target_date_h5','actual_z':'actual_z_h5'}),pair,period)
    result['period']=period
    return result


def choose_candidate(rows,tolerance=1e-6):
    if not rows or not np.isfinite([r['rmse'] for r in rows]).all():
        raise ValueError('Invalid candidate scores')
    minimum=min(r['rmse'] for r in rows)
    return min((r for r in rows if r['rmse']<=minimum+tolerance),
               key=lambda r:(r['hidden_size'],r['learning_rate'],r['trial_id']))


def load_config(config_path):
    path=Path(config_path).resolve()
    cfg=json.loads(path.read_text(encoding='utf-8'))
    if (cfg['feature_order']!=FEATURES or cfg['rolling_window']!=20 or cfg['lookback']!=20
            or cfg['horizon']!=5 or cfg['target']!='change_from_origin_z'
            or cfg['training']['shuffle'] is not True or cfg['runtime']['device']!='cpu'
            or cfg['filter']!={'horizon':5,'margin':0.,'exits':'observed_z',
                              'entry_calendar':'complete_five_day_targets_inside_period'}):
        raise ValueError('Settings differ from the adopted Phase 5 design')
    return path.parent.parent,cfg


def locations(cfg):
    v=cfg['model_version']
    return {'metrics':f'outputs/metrics/lstm/{v}', 'data':f'data/processed/lstm/{v}',
            'weights':f'artifacts/lstm/{v}', 'preprocessing':f'artifacts/preprocessing/{v}',
            'statistical':f'artifacts/statistical/{v}', 'predictions':f'outputs/predictions/lstm/{v}',
            'backtests':f'outputs/backtests/lstm_comparison/{v}', 'figures':f'outputs/figures/lstm/{v}'}


def versions():
    return {'python':platform.python_version(),'numpy':np.__version__,'pandas':pd.__version__,
            'matplotlib':matplotlib.__version__,'torch':torch.__version__, 'device':'cpu',
            'intra_op_threads':1,'inter_op_threads':1,'workers':0,'deterministic':True}


def annotate(frame,pair,stage,split=None):
    frame=frame.copy()
    for k in ['pair_id','dependent','independent','evidence_label']:
        frame[k]=pair[k]
    frame['stage']=stage
    if split is not None:
        frame['split']=split
    return frame


class Store:
    def __init__(self,root,cfg):
        self.root,self.cfg,self.paths=root,cfg,locations(cfg)
        self.outputs={}
        self.frozen=((root/self.paths['metrics']/'unseen_metadata.json').exists()
                     or (root/self.paths['metrics']/'evaluation_started.json').exists())

    def write(self,relative,content):
        path=project_path(self.root,relative)
        if self.frozen and path.exists() and path.read_bytes()!=content:
            raise ValueError(f'Evaluated output would change: {relative}; preserve the run and use another version')
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes(content)
        self.outputs[relative]=sha256(path)
        return relative

    def json(self,relative,data):
        return self.write(relative,(json.dumps(data,indent=2,allow_nan=False)+'\n').encode('utf-8'))

    def csv(self,relative,frame):
        return self.write(relative,frame.to_csv(index=False,lineterminator='\n',float_format='%.17g').encode('utf-8'))


def historical_handoff(root,cfg):
    baseline=json.loads(project_path(root,cfg['baseline_config']).read_text(encoding='utf-8'))
    h=read_handoff(root,baseline)
    contract_path=f"{baseline['outputs']['metrics']}/evaluation_contract.json"
    contract=json.loads(project_path(root,contract_path).read_text(encoding='utf-8'))
    if contract['config_sha256']!=sha256(root/cfg['baseline_config']):
        raise ValueError('Phase 4 settings differ from its contract')
    h['hashes'][cfg['baseline_config']]=sha256(root/cfg['baseline_config'])
    h['hashes'][contract_path]=sha256(root/contract_path)
    normalizations={}
    for p in h['parameters']:
        rel=f"{baseline['outputs']['artifacts']}/{p['pair_id']}/normalization_2025.json"
        path=project_path(root,rel)
        if sha256(path)!=contract['normalization'].get(rel):
            raise ValueError('Phase 4 normalization hash differs from its contract')
        norm=json.loads(path.read_text(encoding='utf-8'))
        if any(norm[k]!=p[k] for k in ['pair_id','dependent','independent','ols_sha256']):
            raise ValueError('Phase 4 normalization direction or lineage differs')
        if norm['fit_start']!='2025-01-02' or norm['fit_end']!='2025-12-31' or norm['nobs']!=250:
            raise ValueError('Phase 4 normalization dates differ')
        normalizations[p['pair_id']]=norm
        h['hashes'][rel]=sha256(path)
    return h,baseline,normalizations


def signature(root,cfg,h):
    package=Path(__file__).resolve().parents[1]
    names=['models/forecasting.py','models/lstm.py','models/plots.py','features/sequences.py',
           'trading/forecast_filter.py','trading/backtest.py','trading/signals.py','trading/baseline.py','data/master.py']
    code={f'src/market_analytics/{name}':sha256(package/name) for name in names}
    code['scripts/run_lstm_forecast.py']=sha256(root/'scripts/run_lstm_forecast.py')
    return {'inputs':h['hashes'], 'settings':cfg,'lock_sha256':sha256(root/'uv.lock'),
            'code':code,'versions':versions()}


def prepare_stage(store,h,pair,norms,stage):
    cfg,root=store.cfg,store.root
    if stage=='selection':
        ols,norm=fit_selection_spread(h['prices'],pair,cfg['selection_end'])
        ols.update(historical_sha256=h['hashes']['data/processed/master_historical.csv'])
        rel=f"{store.paths['statistical']}/selection/{pair['pair_id']}"
        store.json(f'{rel}/ols_20180102_20231229.json',ols)
        store.json(f'{rel}/normalization_2023.json',norm)
        cutoff=cfg['selection_end']
    else:
        ols=pair
        norm={**norms[pair['pair_id']], 'resting_z':-norms[pair['pair_id']]['mean']/norms[pair['pair_id']]['std']}
        cutoff=cfg['historical_end']
    z=apply_normalization(spread_from_prices(h['prices'],ols),norm)
    if stage=='final':
        reference=pd.read_csv(root/'data/processed/statistical_baseline/historical_zscores.csv')
        ref=reference.loc[reference['pair_id'].eq(pair['pair_id'])].set_index('Date')['zscore']
        if not np.allclose(z.to_numpy(),ref.to_numpy(),**cfg['tolerance']):
            raise ValueError('Final Z values differ from Phase 4')
    features=build_features(z)
    raw=build_sequences(features,z,'2018-01-01',cutoff)
    scaler=fit_feature_scaler(training_input_rows(features,raw['index']))
    scaler.update(pair_id=pair['pair_id'],dependent=pair['dependent'],independent=pair['independent'],
                  stage=stage,ols=ols,normalization=norm)
    store.json(f"{store.paths['preprocessing']}/{stage}/{pair['pair_id']}/scaler.json",scaler)
    scaled=apply_feature_scaler(features,scaler)
    train=build_sequences(scaled,z,'2018-01-01',cutoff)
    key='selection_train' if stage=='selection' else 'final_train'
    if len(train['X'])!=cfg['expected'][key] or scaler['nobs']!=cfg['expected'][stage+'_scaler']:
        raise ValueError('Training sample or scaler count differs from the reviewed calendar')
    batches={'train':train}
    if stage=='selection':
        batches['validation']=build_sequences(scaled,z,cfg['validation_start'],cfg['historical_end'])
        if len(batches['validation']['X'])!=cfg['expected']['validation']:
            raise ValueError('Validation sample count differs')
        if train['index']['target_h5'].max()>=batches['validation']['index']['target_h1'].min():
            raise ValueError('Training and validation targets overlap')
    return {'ols':ols,'norm':norm,'z':z,'features':features,'scaler':scaler,'batches':batches}


def save_prepared(store,prepared,stage):
    features,indices,excluded=[],[],[]
    for pair,p in prepared:
        f=p['features'].rename_axis('Date').reset_index()
        features.append(annotate(f,pair,stage))
        for split,b in p['batches'].items():
            indices.append(annotate(b['index'],pair,stage,split))
            excluded.append(annotate(b['excluded'],pair,stage,split))
    for name,frames in [('features',features),('sample_index',indices),('excluded_samples',excluded)]:
        store.csv(f"{store.paths['data']}/{stage}/{name}.csv",pd.concat(frames,ignore_index=True))


def forecast_frame(batch,changes,z,pair,stage,trial_id):
    rows=[]
    if changes.shape!=(len(batch['index']),5):
        raise ValueError('Wrong prediction shape')
    for i,row in enumerate(batch['index'].itertuples()):
        for h in range(1,6):
            date=getattr(row,f'target_h{h}')
            rows.append({'origin':row.origin,'horizon':h,'target_date':date,'origin_z':row.origin_z,
                         'predicted_change':float(changes[i,h-1]),'forecast_z':row.origin_z+float(changes[i,h-1]),
                         'actual_z':float(z.loc[date]),'persistence_z':row.origin_z,'trial_id':trial_id})
    return annotate(pd.DataFrame(rows),pair,stage)


def reconcile(run,prices,beta,capital,cost_rate,tolerance):
    """Rebuild cash and holdings directly from saved stock-leg fills."""
    cash=capital; quantities={'dependent':0.,'independent':0.}; costs=0.
    fills=run['executions']; daily=run['daily_account']
    maximum=0.
    for row in daily.itertuples():
        date=pd.Timestamp(row.Date)
        todays=fills.loc[fills['Date'].eq(row.Date)]
        entries=todays.loc[todays['action'].str.startswith('enter')]
        if len(entries):
            gross=min(capital,cash)/(1+cost_rate)
            notional=gross/(1+beta)
            sign=1 if entries.iloc[0]['action']=='enter_long' else -1
            expected=[sign*notional/prices.loc[date,'dependent_Open'],
                      -sign*beta*notional/prices.loc[date,'independent_Open']]
            np.testing.assert_allclose(entries['shares_change'],expected,**tolerance)
        for fill in todays.itertuples():
            cash-=fill.shares_change*fill.price+fill.cost
            quantities[fill.leg]+=fill.shares_change
            costs+=fill.cost
        equity=cash+sum(quantities[leg]*prices.loc[date,leg+'_Close'] for leg in quantities)
        maximum=max(maximum,abs(equity-row.net_equity))
        np.testing.assert_allclose([equity,costs,row.gross_equity-row.net_equity],
                                   [row.net_equity,row.cumulative_costs,costs],**tolerance)
    np.testing.assert_allclose(run['trades']['net_pnl'].sum(),daily.iloc[-1]['net_equity']-capital,**tolerance)
    return {'status':'pass','sessions':len(daily),'max_equity_difference':maximum,'beta':float(beta)}


def backtests(store,pair,prepared,forecasts,prices,baseline,period):
    z=prepared['z'].loc[prices.index]
    previous=float(prepared['z'].loc[prepared['z'].index<prices.index[0]].iloc[-1])
    h5=forecasts.loc[forecasts['horizon'].eq(5)].set_index('origin')['forecast_z']
    expected=pd.DatetimeIndex([prepared['z'].loc[prepared['z'].index<prices.index[0]].index[-1],*prices.index[:-5]])
    if (h5.index.has_duplicates or not h5.index.equals(expected) or not np.isfinite(h5).all()):
        raise ValueError('Forecast keys differ from the independent complete-target calendar')
    eligible=set(prices.index[:-5])
    legprices=prices[[pair[k]+'_'+f for k in ['dependent','independent'] for f in ['Open','Close']]].copy()
    legprices.columns=[k+'_'+f for k in ['dependent','independent'] for f in ['Open','Close']]
    summaries=[]; runs={}; audits=[]
    for name,filter_values in [('baseline_matched',None),('lstm_filtered',h5)]:
        run=compare_backtest(legprices,z,prepared['ols']['beta'],filter_values,eligible,previous_z=previous,
                             capital=baseline['accounting']['initial_capital'],cost_rate=baseline['accounting']['cost_rate'])
        if run['summary']['status']!='complete':
            raise ValueError('Incomplete comparison account')
        audit=reconcile(run,legprices,prepared['ols']['beta'],10000.,.0005,store.cfg['tolerance'])
        audits.append({'pair_id':pair['pair_id'],'period':period,'strategy':name,**audit})
        summary=annotate(pd.DataFrame([run['summary']]),pair,period)
        summary['strategy']=name; summaries.append(summary)
        for table in ['signals','executions','trades','daily_account']:
            frame=annotate(run[table],pair,period); frame['strategy']=name
            runs.setdefault((name,table),[]).append(frame)
        runs[(name,'summary')]=[summary]
        run['_prices']=legprices
        runs[(name,'run')]=run
    return summaries,runs,audits


def _save_comparisons(store,period,all_runs):
    for (name,table),frames in all_runs.items():
        store.csv(f"{store.paths['backtests']}/{period}/{name}/{table}.csv",pd.concat(frames,ignore_index=True))


def select(store,h,baseline,norms):
    cfg=store.cfg; trials=[]; histories=[]; predictions=[]; metrics=[]; prepared_all=[]
    selection={}; comparisons=[]; all_runs={}; audits=[]; directions=[]; agreements=[]; decisions=[]
    from market_analytics.models.plots import validation_figures
    for pair in h['parameters']:
        p=prepare_stage(store,h,pair,norms,'selection'); prepared_all.append((pair,p))
        train,val=p['batches']['train'],p['batches']['validation']
        candidate_rows=[]; pair_forecasts={}
        settings_list=[{**cfg['training'],**c} for c in cfg['candidates']]
        for i,settings in enumerate(settings_list):
            trial_id=f"h{settings['hidden_size']}_lr{settings['learning_rate']}_s{settings['seed']}"
            print(f"Selection {pair['pair_id']} {trial_id}",flush=True)
            try:
                model,history,best=train_model(train['X'],train['y'],settings,validation=(val['X'],val['y']))
            except Exception as exc:
                store.json(f"{store.paths['metrics']}/failed_trial.json",{'pair_id':pair['pair_id'],'trial_id':trial_id,'settings':settings,'error':str(exc)})
                raise
            f=forecast_frame(val,predict_changes(model,val['X']),p['z'],pair,'validation',trial_id)
            m=forecast_metrics(f); score=float(m.loc[(m['model']=='lstm') & (m['horizon']=='pooled'),'rmse'].iloc[0])
            row={**settings,'pair_id':pair['pair_id'],'trial_id':trial_id,'rmse':score,'best_epoch':best,'epochs_run':len(history),'role':'candidate'}
            candidate_rows.append(row); trials.append(row)
            histories.append(annotate(pd.DataFrame(history).assign(trial_id=trial_id),pair,'selection'))
            rel=f"{store.paths['weights']}/{pair['pair_id']}/selection/{trial_id}"
            store.write(rel+'/model.pt',checkpoint_bytes(model)); store.json(rel+'/metadata.json',row)
            pair_forecasts[trial_id]=f
            predictions.append(f); metrics.append(annotate(m.assign(trial_id=trial_id),pair,'validation'))
        chosen=choose_candidate(candidate_rows,cfg['selection_tolerance'])
        selection[pair['pair_id']]=chosen
        chosen_forecast=pair_forecasts[chosen['trial_id']]
        for seed in cfg['sensitivity_seeds']:
            settings={**cfg['training'],'hidden_size':chosen['hidden_size'],'learning_rate':chosen['learning_rate'],'seed':seed}
            trial_id=f"h{settings['hidden_size']}_lr{settings['learning_rate']}_s{seed}"
            print(f"Sensitivity {pair['pair_id']} seed {seed}",flush=True)
            model,history,best=train_model(train['X'],train['y'],settings,validation=(val['X'],val['y']))
            f=forecast_frame(val,predict_changes(model,val['X']),p['z'],pair,'validation',trial_id)
            m=forecast_metrics(f)
            row={**settings,'pair_id':pair['pair_id'],'trial_id':trial_id,'rmse':float(m.loc[(m['model']=='lstm')&(m['horizon']=='pooled'),'rmse'].iloc[0]),
                 'best_epoch':best,'epochs_run':len(history),'role':'sensitivity'}
            trials.append(row); histories.append(annotate(pd.DataFrame(history).assign(trial_id=trial_id),pair,'selection'))
            rel=f"{store.paths['weights']}/{pair['pair_id']}/selection/{trial_id}"
            store.write(rel+'/model.pt',checkpoint_bytes(model)); store.json(rel+'/metadata.json',row)
            pair_forecasts[trial_id]=f; predictions.append(f); metrics.append(annotate(m.assign(trial_id=trial_id),pair,'validation'))
        evalprices=h['prices'].loc[cfg['validation_start']:cfg['historical_end']]
        sums,runs,checks=backtests(store,pair,p,chosen_forecast,evalprices,baseline,'validation')
        comparisons.extend(sums); audits.extend(checks)
        decisions.append(filter_decisions(runs,chosen_forecast,p['norm']['resting_z'],pair,'validation'))
        for (name,table),frames in runs.items():
            if table!='run': all_runs.setdefault((name,table),[]).extend(frames)
        signals=runs[('baseline_matched','run')]['signals']
        crossing_dates=pd.to_datetime(signals.loc[signals['long_crossing']|signals['short_crossing'],'Date'])
        primary=chosen_forecast.loc[chosen_forecast['horizon'].eq(5)].set_index('origin')
        for trial_id,f in pair_forecasts.items():
            if trial_id!=chosen['trial_id'] and '_s42' in trial_id: continue
            h5=f.loc[f['horizon'].eq(5)].copy()
            h5['resting_z']=p['norm']['resting_z']
            h5['direction_correct']=np.sign(h5['predicted_change'])==np.sign(h5['actual_z']-h5['origin_z'])
            h5['crossing']=h5['origin'].isin(crossing_dates)
            h5['would_accept_crossing']=np.where(h5['origin_z']<0,h5['predicted_change']>0,h5['predicted_change']<0)
            directions.append(h5)
            for subset,mask in [('all',np.ones(len(h5),dtype=bool)),('crossings',h5['crossing'])]:
                q=h5.loc[mask]
                row={'pair_id':pair['pair_id'],'trial_id':trial_id,'subset':subset,'origins':len(q)}
                if len(q):
                    p42=primary.loc[q['origin']]
                    seed42=np.where(p42['origin_z']<0,p42['predicted_change']>0,p42['predicted_change']<0)
                    row.update(direction_accuracy=float(q['direction_correct'].mean()),
                               acceptance_agreement_with_seed42=float((q['would_accept_crossing'].to_numpy()==seed42).mean()),
                               **direction_base_rates(q))
                agreements.append(row)
        validation_figures(store,pair,chosen_forecast,pd.concat(histories,ignore_index=True),runs)
    save_prepared(store,prepared_all,'selection')
    _save_comparisons(store,'validation',all_runs)
    for name,frame in [('trials',pd.DataFrame(trials)),('epoch_history',pd.concat(histories)),
                       ('forecast_metrics',pd.concat(metrics)),('strategy_comparison',pd.concat(comparisons)),
                       ('direction_diagnostics',pd.concat(directions)),('seed_agreement',pd.DataFrame(agreements)),
                       ('filter_decisions',pd.concat(decisions,ignore_index=True))]:
        store.csv(f"{store.paths['metrics']}/{name}.csv",frame)
    store.csv(f"{store.paths['predictions']}/validation/forecasts.csv",pd.concat(predictions))
    store.json(f"{store.paths['metrics']}/selection.json",selection)
    return {'selected':selection,'reconciliation':audits,'outputs':dict(store.outputs)}


def validate_selection(store,current):
    path=store.root/store.paths['metrics']/'selection_metadata.json'
    if not path.exists(): raise ValueError('Refit requires saved selection provenance')
    meta=json.loads(path.read_text(encoding='utf-8'))
    if meta['signature']!=current:
        raise ValueError('Selection evidence uses different inputs/settings/code/runtime')
    for relative,expected in meta['outputs'].items():
        if not (store.root/relative).is_file() or sha256(store.root/relative)!=expected:
            raise ValueError(f'Selection output changed: {relative}')


def refit(store,h,norms):
    chosen=json.loads((store.root/store.paths['metrics']/'selection.json').read_text(encoding='utf-8'))
    prepared_all=[]; histories=[]
    for pair in h['parameters']:
        p=prepare_stage(store,h,pair,norms,'final'); prepared_all.append((pair,p))
        selection=chosen[pair['pair_id']]
        settings={**store.cfg['training'],'hidden_size':selection['hidden_size'],'learning_rate':selection['learning_rate']}
        train=p['batches']['train']
        print(f"Refit {pair['pair_id']} epochs {selection['best_epoch']}",flush=True)
        model,history,_=train_model(train['X'],train['y'],settings,epochs=selection['best_epoch'])
        histories.append(annotate(pd.DataFrame(history),pair,'final'))
        rel=f"{store.paths['weights']}/{pair['pair_id']}/final_20180102_20251231"
        store.write(rel+'/model.pt',checkpoint_bytes(model))
        metadata={'pair':{k:pair[k] for k in ['pair_id','dependent','independent','evidence_label','spread_column']},
                  'model_version':store.cfg['model_version'],'target':'change_from_origin_z','feature_order':FEATURES,
                  'lookback':20,'horizon':5,'settings':settings,'epochs':selection['best_epoch'],'selection':selection,
                  'versions':versions(),'ols':p['ols'],'normalization':p['norm'],'scaler':p['scaler'],
                  'train_target_start':str(train['index']['target_h1'].min().date()),
                  'train_target_end':str(train['index']['target_h5'].max().date()),'train_samples':len(train['X']),
                  'weights_sha256':sha256(store.root/rel/'model.pt'),
                  'training_sessions':[str(d.date()) for d in h['prices'].index]}
        metadata['preprocessing_sha256']=preprocessing_digest(metadata)
        store.json(rel+'/metadata.json',metadata)
        origin=train['index'].iloc[-1]['origin']
        raw_prices=h['prices'].loc[:origin].tail(39)
        price_example=raw_prices.reset_index().to_dict(orient='list')
        price_example={k:[str(v.date()) if isinstance(v,pd.Timestamp) else v for v in vals] for k,vals in price_example.items()}
        expected=forecast_from_prices(raw_prices,store.root/rel)
        store.json(rel+'/known_inference.json',{'prices':price_example,'forecast_z':expected.tolist(),'origin':str(origin.date())})
        np.testing.assert_allclose(expected,train['index'].iloc[-1]['origin_z']+predict_changes(model,train['X'][-1:])[0].astype(np.float64),**store.cfg['inference_tolerance'])
    save_prepared(store,prepared_all,'final')
    store.csv(f"{store.paths['metrics']}/final_epoch_history.csv",pd.concat(histories))
    audit=[]
    for stage in ['selection','final']:
        for pair in h['parameters']:
            scaler=json.loads((store.root/store.paths['preprocessing']/stage/pair['pair_id']/'scaler.json').read_text())
            for name,obj in [('ols',scaler['ols']),('normalization',scaler['normalization']),('feature_scaler',scaler)]:
                audit.append({'pair_id':pair['pair_id'],'stage':stage,'object':name,'fit_start':obj['fit_start'],'fit_end':obj['fit_end'],
                              'nobs':obj['nobs'],'applied_to':'2024-2025 conditional validation' if stage=='selection' else '2026 fixed application',
                              'resting_z':-scaler['normalization']['mean']/scaler['normalization']['std']})
    for pair in h['parameters']:
        audit.append({'pair_id':pair['pair_id'],'stage':'selection','object':'shortlist_and_direction','fit_start':'2018-01-02',
                      'fit_end':'2025-12-31','nobs':2011,'applied_to':'fixed shortlist; validation is conditional','resting_z':np.nan})
    store.csv(f"{store.paths['metrics']}/split_audit.csv",pd.DataFrame(audit))
    return {'outputs':dict(store.outputs)}


def preprocessing_digest(meta):
    fields={k:meta[k] for k in ['pair','ols','normalization','scaler','training_sessions']}
    return hashlib.sha256(json.dumps(fields,sort_keys=True).encode()).hexdigest()


def forecast_from_prices(prices,bundle_directory,*,session_calendar=None):
    """Load a portable bundle and forecast from dated Open/Close history alone."""
    path=Path(bundle_directory)
    meta=json.loads((path/'metadata.json').read_text(encoding='utf-8'))
    if (meta['feature_order']!=FEATURES or meta['target']!='change_from_origin_z'
            or meta['lookback']!=20 or meta['horizon']!=5 or sha256(path/'model.pt')!=meta['weights_sha256']):
        raise ValueError('Incompatible model bundle or changed weights')
    if meta.get('preprocessing_sha256')!=preprocessing_digest(meta):
        raise ValueError('Bundle preprocessing checksum differs')
    for obj in [meta['ols'],meta['normalization'],meta['scaler']]:
        if any(obj[k]!=meta['pair'][k] for k in ['pair_id','dependent','independent']):
            raise ValueError('Bundle pair or direction differs')
    if (meta['scaler']['stage']!='final' or meta['scaler']['ols']!=meta['ols']
            or meta['scaler']['normalization']!=meta['normalization']):
        raise ValueError('Bundle preprocessing lineage differs')
    calendar=pd.DatetimeIndex(meta['training_sessions'] if session_calendar is None else session_calendar)
    if calendar.has_duplicates or not calendar.is_monotonic_increasing or calendar.hasnans:
        raise ValueError('Invalid independent session calendar')
    if prices.index[0]<calendar[0] or prices.index[-1]>calendar[-1]:
        raise ValueError('Supply an independent session calendar covering the inference dates')
    expected=calendar[(calendar>=prices.index[0])&(calendar<=prices.index[-1])]
    if not prices.index.equals(expected):
        raise ValueError('Inference history has missing or unexpected trading sessions')
    z=apply_normalization(spread_from_prices(prices,meta['ols']),meta['normalization'])
    inputs=build_inference_inputs(apply_feature_scaler(build_features(z),meta['scaler']),[prices.index[-1]])
    model=load_checkpoint(path/'model.pt',meta['settings']['hidden_size'])
    return float(z.iloc[-1])+predict_changes(model,inputs)[0].astype(np.float64)


def read_unseen(root,baseline):
    relative=baseline['unseen']; path=project_path(root,relative)
    manifest=json.loads(project_path(root,baseline['manifest']).read_text(encoding='utf-8'))
    actual=sha256(path)
    if actual!=manifest['outputs'].get(relative): raise ValueError('Unseen master hash differs')
    columns=[s+'_'+f for s in ['AMZN','META','NVDA'] for f in ['Open','Close']]
    frame=pd.read_csv(path,usecols=['Date']+columns,parse_dates=['Date']).set_index('Date')
    validate_prices(frame,baseline['periods']['unseen'])
    return frame,actual


def evaluate(store,h,baseline,norms):
    from market_analytics.models.plots import evaluation_figures
    cfg=store.cfg; unseen,unseen_hash=read_unseen(store.root,baseline)
    prices=pd.concat([h['prices'],unseen]); predictions=[]; metrics=[]; comparisons=[]; audits=[]; all_runs={}; decisions=[]
    for pair in h['parameters']:
        rel=store.root/store.paths['weights']/pair['pair_id']/'final_20180102_20251231'
        meta=json.loads((rel/'metadata.json').read_text())
        z=apply_normalization(spread_from_prices(prices,meta['ols']),meta['normalization'])
        features=apply_feature_scaler(build_features(z),meta['scaler'])
        b=build_sequences(features,z,cfg['unseen_start'],cfg['unseen_end'])
        if len(b['X'])!=cfg['expected']['unseen']: raise ValueError('Unseen origin count differs')
        model=load_checkpoint(rel/'model.pt',meta['settings']['hidden_size'])
        changes=predict_changes(model,b['X'])
        # Prediction uses only input windows; realized targets are joined afterward.
        f=forecast_frame(b,changes,z,pair,'unseen','final_seed42'); predictions.append(f)
        metrics.append(annotate(forecast_metrics(f),pair,'unseen'))
        p={'z':z,'ols':meta['ols']}
        sums,runs,checks=backtests(store,pair,p,f,unseen,baseline,'unseen')
        comparisons.extend(sums); audits.extend(checks)
        decisions.append(filter_decisions(runs,f,meta['normalization']['resting_z'],pair,'unseen'))
        for (name,table),frames in runs.items():
            if table!='run': all_runs.setdefault((name,table),[]).extend(frames)
        evaluation_figures(store,pair,f,runs)
        store.csv(f"{store.paths['data']}/final/{pair['pair_id']}_unseen_sample_index.csv",annotate(b['index'],pair,'unseen'))
        store.csv(f"{store.paths['data']}/final/{pair['pair_id']}_unseen_features.csv",annotate(build_features(z).loc[unseen.index].rename_axis('Date').reset_index(),pair,'unseen'))
        store.csv(f"{store.paths['data']}/final/{pair['pair_id']}_unseen_excluded_samples.csv",annotate(b['excluded'].loc[b['excluded']['origin']>=pd.Timestamp('2025-12-31')],pair,'unseen'))
    _save_comparisons(store,'unseen',all_runs)
    store.csv(f"{store.paths['predictions']}/unseen/forecasts.csv",pd.concat(predictions))
    store.csv(f"{store.paths['metrics']}/unseen_forecast_metrics.csv",pd.concat(metrics))
    store.csv(f"{store.paths['metrics']}/unseen_filter_decisions.csv",pd.concat(decisions,ignore_index=True))
    reference=pd.read_csv(store.root/baseline['outputs']['metrics']/'unseen/summary.csv')
    reference['strategy']='baseline_full_period'; reference['stage']='unseen'
    store.csv(f"{store.paths['metrics']}/unseen_strategy_comparison.csv",pd.concat([*comparisons,reference],ignore_index=True))
    return {'outputs':dict(store.outputs),'reconciliation':audits,'unseen_sha256':unseen_hash,'status':'complete'}


def run_lstm_forecast(config_path,*,stage='all',historical_only=False):
    matplotlib.use('Agg')
    root,cfg=load_config(config_path); store=Store(root,cfg)
    if stage not in ['all','select','refit','evaluate'] or (historical_only and stage!='all'):
        raise ValueError('Invalid stage combination')
    h,baseline,norms=historical_handoff(root,cfg)
    current=signature(root,cfg,h)
    contract_path=root/store.paths['metrics']/'evaluation_contract.json'
    if contract_path.exists():
        old=json.loads(contract_path.read_text(encoding='utf-8'))
        if old['signature']!=current and (store.frozen or stage=='evaluate'):
            raise ValueError('Frozen Phase 5 inputs/settings/code/runtime differ; preserve this run and use a new version')
        if store.frozen or stage=='evaluate':
            for relative,expected in old['artifacts'].items():
                if not (root/relative).is_file() or sha256(root/relative)!=expected:
                    raise ValueError(f'Frozen artifact changed: {relative}')
    results={}
    if stage in ['all','select']:
        store.outputs.clear()
        results['selection']=select(store,h,baseline,norms)
        store.json(f"{store.paths['metrics']}/selection_metadata.json",{'signature':current,**results['selection']})
    if stage in ['all','refit']:
        validate_selection(store,current)
        store.outputs.clear()
        results['refit']=refit(store,h,norms)
        store.json(f"{store.paths['metrics']}/refit_metadata.json",{'signature':current,**results['refit']})
        artifact_dirs=[store.paths['weights'],store.paths['preprocessing'],store.paths['statistical']]
        artifacts={str(p.relative_to(root)).replace('\\','/'):sha256(p) for d in artifact_dirs for p in sorted((root/d).rglob('*')) if p.is_file()}
        selection_file=f"{store.paths['metrics']}/selection.json"
        artifacts[selection_file]=sha256(root/selection_file)
        store.json(f"{store.paths['metrics']}/evaluation_contract.json",{'signature':current,'artifacts':artifacts})
    if stage in ['all','evaluate'] and not historical_only:
        store.outputs.clear()
        if not contract_path.exists(): raise ValueError('Evaluation requires a frozen final bundle')
        store.json(f"{store.paths['metrics']}/evaluation_started.json",{'signature':current,
                   'unseen_sha256':sha256(project_path(root,baseline['unseen']))})
        store.frozen=True
        results['unseen']=evaluate(store,h,baseline,norms)
        store.json(f"{store.paths['metrics']}/unseen_metadata.json",{'signature':current,**results['unseen']})
    return results


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',type=Path,default=Path('configs/lstm_forecast.json'))
    mode=parser.add_mutually_exclusive_group()
    mode.add_argument('--stage',choices=['select','refit','evaluate'],default=None)
    mode.add_argument('--historical-only',action='store_true')
    args=parser.parse_args()
    matplotlib.use('Agg')
    result=run_lstm_forecast(args.config,stage=args.stage or 'all',historical_only=args.historical_only)
    print('Phase 5 completed stages: '+', '.join(result),flush=True)
