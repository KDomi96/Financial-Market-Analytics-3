"""Figures from saved dated forecasts and comparison accounts."""

import io
import matplotlib.pyplot as plt
import pandas as pd


def save(store,figure,relative):
    buffer=io.BytesIO()
    figure.savefig(buffer,format='png',dpi=140,bbox_inches='tight')
    plt.close(figure)
    store.write(relative,buffer.getvalue())


def evaluation_figures(store,pair,forecasts,runs,period='unseen'):
    from market_analytics.models.forecasting import forecast_metrics
    errors=forecast_metrics(forecasts)
    figure,ax=plt.subplots(figsize=(8,4))
    for i,(model,label) in enumerate([('lstm','LSTM'),('persistence','Persistence')]):
        values=errors.loc[(errors['model']==model)&(errors['horizon']!='pooled')]
        x=values['horizon'].astype(int)+(i-.5)*.3
        ax.bar(x,values['rmse'],width=.3,label=label)
    ax.set_xticks(range(1,6)); ax.set_xlabel('Forecast horizon (sessions)'); ax.set_ylabel('RMSE (Z units)')
    ax.set_title(f"{pair['pair_id']}: {period} errors (exploratory)"); ax.legend()
    save(store,figure,f"{store.paths['figures']}/{period}/{pair['pair_id']}_errors.png")
    figure,axes=plt.subplots(2,1,figsize=(11,7),sharex=True)
    for ax,h in zip(axes,[1,5]):
        f=forecasts.loc[forecasts['horizon'].eq(h)]
        ax.plot(f['target_date'],f['actual_z'],label='Observed',color='black',lw=1)
        ax.plot(f['target_date'],f['forecast_z'],label='LSTM',lw=1)
        ax.plot(f['target_date'],f['persistence_z'],label='Persistence',lw=.8,alpha=.6)
        ax.set_ylabel(f'Z, horizon {h}'); ax.legend(loc='best'); ax.grid(alpha=.2)
    figure.suptitle(f"{pair['pair_id']}: {period} forecasts (exploratory)")
    save(store,figure,f"{store.paths['figures']}/{period}/{pair['pair_id']}_forecasts.png")
    figure,axes=plt.subplots(3,1,figsize=(11,9),sharex=True)
    for name,label in [('baseline_matched','Matched baseline'),('lstm_filtered','LSTM filter')]:
        run=runs[(name,'run')]; d=run['daily_account']; dates=pd.to_datetime(d['Date'])
        axes[0].plot(dates,d['net_equity'],label=label)
        axes[1].plot(dates,d['net_drawdown']*100,label=label)
    signals=runs[('lstm_filtered','run')]['signals']; dates=pd.to_datetime(signals['Date'])
    axes[2].plot(dates,signals['zscore'],color='black',lw=1)
    for field,marker,label in [('entry_accepted','^','Accepted entry'),('filter_rejected','x','Rejected entry')]:
        mask=signals[field]
        axes[2].scatter(dates[mask],signals.loc[mask,'zscore'],marker=marker,label=label)
    for value in [-2,0,2]: axes[2].axhline(value,color='gray',lw=.7,ls='--')
    for ax in axes: ax.grid(alpha=.2); ax.legend(loc='best')
    axes[0].set_ylabel('Net equity (USD)'); axes[1].set_ylabel('Drawdown (%)'); axes[2].set_ylabel('Z')
    figure.suptitle(f"{pair['pair_id']}: {period} strategy comparison (exploratory)")
    save(store,figure,f"{store.paths['figures']}/{period}/{pair['pair_id']}_strategy.png")


def validation_figures(store,pair,forecasts,history,runs):
    evaluation_figures(store,pair,forecasts,runs,period='validation')
    figure,ax=plt.subplots(figsize=(10,5))
    history=history.loc[history['pair_id'].eq(pair['pair_id'])]
    for trial,rows in history.groupby('trial_id',sort=False):
        ax.plot(rows['epoch'],rows['validation_mse'],label=trial)
    persistence=float(((forecasts['persistence_z']-forecasts['actual_z'])**2).mean())
    ax.axhline(persistence,color='black',ls='--',lw=1,label='Persistence')
    ax.set_xlabel('Epoch'); ax.set_ylabel('Validation change MSE'); ax.legend(fontsize=8)
    ax.set_title(f"{pair['pair_id']}: historical model selection (exploratory)"); ax.grid(alpha=.2)
    save(store,figure,f"{store.paths['figures']}/validation/{pair['pair_id']}_learning_curves.png")
