"""Preserve the evaluated Phase 4 handoff when later dependencies are added."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from market_analytics import pipeline
from market_analytics.data.master import sha256


class PipelineFreezeTests(unittest.TestCase):
    def test_frozen_handoff_is_validated_and_reused(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); (root/'configs').mkdir()
            cfg={'phase3_metadata':'outputs/phase3.json','outputs':{'metrics':'outputs/phase4'}}
            baseline=root/'configs/statistical_baseline.json'; baseline.write_text(json.dumps(cfg))
            settings=root/'configs/pair_selection.json'; settings.write_text('{}')
            metadata=root/'outputs/phase3.json'; metadata.parent.mkdir()
            meta={'settings':{'sha256':sha256(settings)},'code':{},'versions':pipeline.pair_selection_versions()}
            metadata.write_text(json.dumps(meta))
            contract=metadata.parent/'phase4/evaluation_contract.json'; contract.parent.mkdir()
            contract.write_text(json.dumps({'historical_inputs':{'outputs/phase3.json':sha256(metadata)}}))
            with patch.object(pipeline,'read_handoff',return_value={}) as checked, \
                 patch.object(pipeline,'run_pair_selection',side_effect=AssertionError('Frozen metadata would be rewritten')):
                self.assertEqual(pipeline.pair_selection_stage(settings,baseline),meta)
                checked.assert_called_once()
            metadata.write_text('{}')
            with self.assertRaises(ValueError): pipeline.pair_selection_stage(settings,baseline)

    def test_fresh_pipeline_builds_pair_selection(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); (root/'configs').mkdir()
            baseline=root/'configs/statistical_baseline.json'
            baseline.write_text(json.dumps({'outputs':{'metrics':'outputs/phase4'}}))
            settings=root/'configs/pair_selection.json'
            with patch.object(pipeline,'run_pair_selection',return_value={'fresh':True}) as run:
                self.assertEqual(pipeline.pair_selection_stage(settings,baseline),{'fresh':True})
                run.assert_called_once_with(settings)
