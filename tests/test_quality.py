import unittest
from datetime import datetime, timezone, timedelta
from research_quality import candidate_quality, freshness, injury_review
from market_audit import audit

class QualityTests(unittest.TestCase):
    def test_no_injury_claims(self):
        r=injury_review([{'ticker':'T','matchup':'A vs B'}])[0]
        self.assertEqual(r['status'],'NOT VERIFIED')
        self.assertIn('NONE',r['forecast_adjustment'])
    def test_evidence_gate(self):
        self.assertEqual(candidate_quality({'games per team (min)':30},{'games':250,'brier':.27,'baseline_brier':.25}),'MODEL FAILED BASELINE')
    def test_stale(self):
        d=(datetime.now(timezone.utc)-timedelta(days=2)).isoformat()
        self.assertIn('STALE',freshness(d))
    def test_no_resolved(self):
        self.assertEqual(audit([])['contracts'],0)
        self.assertIsNone(audit([])['model_brier_advantage'])

if __name__=='__main__': unittest.main()
