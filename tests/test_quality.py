import unittest
from backend.quality import review_months

def m(month,c,shares,coverage=100):return {'month':month,'acquisition':{'available':True,'source_count':c},'coverage':coverage,'shares':[{'class_id':k,'percent':v} for k,v in shares.items()]}
class QualityTests(unittest.TestCase):
 def test_sparse_and_abrupt_change(self):
  q=review_months([m('2026-01',3,{7:100}),m('2026-02',1,{7:91,8:9})],{'values':[.1,.2]})
  self.assertEqual({x['code'] for x in q[1]['warnings']},{'limited_scene_count','dominant_class','large_monthly_shift','snow_ice_surge'})
  self.assertEqual(q[1]['source_scene_count'],1)
  self.assertEqual(q[1]['biggest_class_shift']['change_percentage_points'],-9)
  self.assertEqual(q[1]['normalized_entropy'],.2)
 def test_no_fabricated_confidence(self):
  q=review_months([m('2026-01',3,{6:60,1:40})])[0]
  self.assertEqual(q['quality_label'],'NO_RULE_TRIGGERED')
  self.assertIsNone(q['normalized_entropy'])
  self.assertIn('NOT probability of error',q['entropy_interpretation'])
 def test_missing_metadata_is_explicit(self):
  month=m('2026-01',3,{6:70,1:30});month['acquisition']={'available':False}
  q=review_months([month])[0]
  self.assertIsNone(q['source_scene_count']);self.assertIn('missing_acquisition_receipt',[x['code'] for x in q['warnings']])
 def test_coverage_warning(self):
  q=review_months([m('2026-01',4,{1:80},90)])[0]
  self.assertIn('incomplete_coverage',[x['code'] for x in q['warnings']])
if __name__=='__main__':unittest.main()
