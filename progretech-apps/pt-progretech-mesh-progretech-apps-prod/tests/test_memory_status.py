import json
import tempfile
import unittest
from pathlib import Path
from control_center.memory_status import memory_status

class MemoryStatusTests(unittest.TestCase):
    def test_receipts_are_scoped_and_failure_not_hidden_by_prior_verified_record(self):
        with tempfile.TemporaryDirectory() as home:
            path=Path(home)/'.local/state/rend/hindsight/completion-audit.jsonl';path.parent.mkdir(parents=True)
            rows=[{'agent':'architect','status':'runtime_activity','activity_recall_verified':True,'activity_memory_id':'other','activity_kind':'runtime_activity','private':'NOT_EXPOSED'}, {'agent':'reviewer','status':'no_change','activity_recall_verified':True,'activity_memory_id':'prior','activity_kind':'reviewed_activity'}, {'agent':'reviewer','status':'activity_write_unavailable','at':'2026-10-01T10:00:00Z'}]
            path.write_text('\n'.join(json.dumps(r) for r in rows))
            result=memory_status(home,'reviewer');self.assertEqual(result['latest_status'],'activity_write_unavailable');self.assertFalse(result['recall_verified']);self.assertEqual(result['last_verified']['activity_memory_id'],'prior');self.assertNotIn('other',str(result))
            other=memory_status(home,'architect');self.assertTrue(other['recall_verified']);self.assertNotIn('NOT_EXPOSED',str(other));self.assertNotIn('private',str(other))
    def test_missing_audit_cannot_claim_logging_or_recall(self):
        with tempfile.TemporaryDirectory() as home:
            result=memory_status(home,'rend');self.assertEqual(result['latest_status'],'not_observed');self.assertFalse(result['recall_verified'])
