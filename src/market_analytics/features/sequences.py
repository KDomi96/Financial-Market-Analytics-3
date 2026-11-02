"""Trailing spread features and dated five-horizon change targets."""

import numpy as np
import pandas as pd

FEATURES = ['z', 'lag1', 'lag2', 'lag3', 'rolling_std']


def check_dates(obj):
    dates = obj.index
    if (not isinstance(dates, pd.DatetimeIndex) or len(dates) == 0 or dates.hasnans
            or dates.has_duplicates or not dates.is_monotonic_increasing
            or dates.tz is not None or not dates.equals(dates.normalize())):
        raise ValueError('Expected unique increasing daily dates')


def build_features(z, rolling_window=20):
    """Use observations available at each after-close origin."""
    check_dates(z)
    if rolling_window != 20 or not np.isfinite(z).all():
        raise ValueError('Expected finite Z values and the adopted 20-session window')
    return pd.DataFrame({'z':z, 'lag1':z.shift(1), 'lag2':z.shift(2), 'lag3':z.shift(3),
                         'rolling_std':z.rolling(rolling_window, min_periods=rolling_window).std(ddof=1)})


def build_inference_inputs(features, origins):
    check_dates(features)
    if list(features.columns) != FEATURES:
        raise ValueError('Wrong feature order')
    dates = pd.DatetimeIndex(origins)
    if dates.has_duplicates or not dates.is_monotonic_increasing:
        raise ValueError('Origins must be unique and ordered')
    arrays = []
    for origin in dates:
        if origin not in features.index:
            raise ValueError('Origin is absent from feature dates')
        i = features.index.get_loc(origin)
        rows = features.iloc[i-19:i+1] if i >= 19 else features.iloc[:0]
        if len(rows) != 20 or not np.isfinite(rows.to_numpy()).all():
            raise ValueError('Insufficient finite feature history')
        arrays.append(rows.to_numpy(dtype=np.float32))
    return np.stack(arrays) if arrays else np.empty((0,20,5), dtype=np.float32)


def build_sequences(features, z, target_start, target_end):
    check_dates(z)
    if not features.index.equals(z.index) or list(features.columns) != FEATURES:
        raise ValueError('Features and targets are misaligned')
    start, end = pd.Timestamp(target_start), pd.Timestamp(target_end)
    if start > end or not np.isfinite(z).all():
        raise ValueError('Invalid target period or values')
    index, excluded, ys = [], [], []
    for i, origin in enumerate(z.index):
        reason = ''
        if i < 19 or not np.isfinite(features.iloc[max(0,i-19):i+1].to_numpy()).all():
            reason = 'insufficient_feature_history'
        elif i+5 >= len(z):
            reason = 'incomplete_future_targets'
        elif z.index[i+1] < start:
            reason = 'targets_before_period'
        elif z.index[i+5] > end:
            reason = 'target_crosses_boundary'
        if reason:
            excluded.append({'origin':origin, 'reason':reason})
            continue
        row = {'input_start':z.index[i-19], 'input_end':origin, 'origin':origin,
               'origin_z':float(z.iloc[i])}
        row.update({f'target_h{h}':z.index[i+h] for h in range(1,6)})
        index.append(row)
        ys.append(z.iloc[i+1:i+6].to_numpy(dtype=np.float64)-z.iloc[i])
    frame = pd.DataFrame(index)
    if frame.empty:
        raise ValueError('No complete samples in target period')
    return {'X':build_inference_inputs(features, frame['origin']),
            'y':np.asarray(ys, dtype=np.float32), 'index':frame,
            'excluded':pd.DataFrame(excluded)}


def training_input_rows(features, sample_index):
    selected = np.zeros(len(features), dtype=bool)
    for row in sample_index.itertuples():
        selected |= (features.index >= row.input_start) & (features.index <= row.input_end)
    rows = features.loc[selected]
    if rows.empty or not np.isfinite(rows.to_numpy()).all():
        raise ValueError('Invalid training input rows')
    return rows


def fit_feature_scaler(training_rows):
    check_dates(training_rows)
    if list(training_rows.columns) != FEATURES or not np.isfinite(training_rows.to_numpy()).all():
        raise ValueError('Invalid scaler rows')
    mean = training_rows.mean().to_numpy()
    std = training_rows.std(ddof=0).to_numpy()
    constant = std == 0
    return {'features':FEATURES, 'mean':mean.tolist(), 'scale':np.where(constant,1.,std).tolist(),
            'ddof':0, 'constant_columns':[f for f,c in zip(FEATURES,constant) if c],
            'fit_start':str(training_rows.index[0].date()), 'fit_end':str(training_rows.index[-1].date()),
            'nobs':len(training_rows), 'fit_dates':[str(x.date()) for x in training_rows.index]}


def apply_feature_scaler(features, scaler):
    if list(features.columns) != FEATURES or scaler['features'] != FEATURES or scaler['ddof'] != 0:
        raise ValueError('Wrong feature order or scaler convention')
    mean, scale = np.asarray(scaler['mean']), np.asarray(scaler['scale'])
    if mean.shape != (5,) or scale.shape != (5,) or not np.isfinite([mean,scale]).all() or (scale<=0).any():
        raise ValueError('Invalid scaler values')
    return (features - mean)/scale


def fit_selection_spread(prices, pair, cutoff='2023-12-31'):
    check_dates(prices)
    end = pd.Timestamp(cutoff)
    if end != pd.Timestamp('2023-12-31'):
        raise ValueError('Selection fit must end in 2023')
    p = prices.loc['2018-01-01':cutoff]
    vals = p[[pair['dependent']+'_Close',pair['independent']+'_Close']].to_numpy()
    if len(vals)<3 or not np.isfinite(vals).all() or (vals<=0).any():
        raise ValueError('Invalid earlier fit prices')
    y,x = np.log(vals).T
    design = np.column_stack([np.ones(len(x)),x])
    coefficients,_,rank,_ = np.linalg.lstsq(design,y,rcond=None)
    intercept,beta = map(float,coefficients)
    if rank != 2 or beta<=0 or not np.isfinite(coefficients).all():
        raise ValueError('Earlier OLS needs a finite positive beta and full rank')
    residual = pd.Series(y-design@coefficients,index=p.index)
    year = residual.loc['2023-01-01':'2023-12-31']
    mean,std = float(year.mean()),float(year.std(ddof=1))
    if len(year)<2 or not np.isfinite([mean,std]).all() or std<=0:
        raise ValueError('Invalid 2023 normalization')
    ols = {**pair,'intercept':intercept,'beta':beta,'fit_start':str(p.index[0].date()),
           'fit_end':str(p.index[-1].date()),'nobs':len(p), 'transformation':'natural log of Yahoo Close; dividends excluded'}
    norm = {'mean':mean,'std':std,'ddof':1,'resting_z':-mean/std,
            'fit_start':str(year.index[0].date()),'fit_end':str(year.index[-1].date()),'nobs':len(year)}
    return ols,norm
