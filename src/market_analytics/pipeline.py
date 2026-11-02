"""Stage helpers for the ordered batch pipeline."""

import json
import platform

import matplotlib
import numpy as np
import pandas as pd
import statsmodels

from market_analytics.cointegration.selection import run_pair_selection
from market_analytics.data.master import sha256
from market_analytics.trading.baseline import read_handoff


def pair_selection_versions():
    return {'python':platform.python_version(),'numpy':np.__version__,'pandas':pd.__version__,
            'statsmodels':statsmodels.__version__,'matplotlib':matplotlib.__version__}


def pair_selection_stage(config_path,baseline_path):
    """Reuse the Phase 3 handoff once Phase 4 has frozen it.

    Rerunning Phase 3 would rewrite its metadata, whose hash Phase 4's evaluation
    contract records. A fresh checkout without that contract runs Phase 3 normally.
    """
    root=baseline_path.resolve().parent.parent
    cfg=json.loads(baseline_path.read_text(encoding='utf-8'))
    contract_path=root/cfg['outputs']['metrics']/'evaluation_contract.json'
    if not contract_path.exists():
        return run_pair_selection(config_path)
    contract=json.loads(contract_path.read_text(encoding='utf-8'))
    relative=cfg['phase3_metadata']; path=root/relative
    if sha256(path)!=contract['historical_inputs'].get(relative):
        raise ValueError('Frozen Phase 3 metadata changed')
    meta=json.loads(path.read_text(encoding='utf-8'))
    if meta['settings']['sha256']!=sha256(config_path) or meta['versions']!=pair_selection_versions():
        raise ValueError('Frozen Phase 3 settings/runtime differ; preserve the earlier version')
    for relative,expected in meta['code'].items():
        if sha256(root/relative)!=expected:
            raise ValueError('Frozen Phase 3 source changed; preserve the earlier version')
    read_handoff(root,cfg)
    print('Pair selection: reusing the validated handoff frozen by Phase 4')
    return meta
