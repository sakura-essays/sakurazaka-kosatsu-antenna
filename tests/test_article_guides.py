"""Public metadata may expose only explicit, title-matched editorial guides."""
import pathlib,sys,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts'))
from build import attach_article_guides
class ArticleGuideTests(unittest.TestCase):
 def test_matched_and_mismatched_titles(self):
  rows=[{'url':'https://example.com/a','title':'A'},{'url':'https://example.com/b','title':'Changed'}]
  items={'https://example.com/a':{'title':'A','guide':'This is an editorial guide.'},'https://example.com/b':{'title':'Old','guide':'Stale editorial summary.'}}
  attach_article_guides(rows,items)
  self.assertEqual(rows[0]['guide'],'This is an editorial guide.')
  self.assertNotIn('guide',rows[1])
 def test_invalid_guide_is_rejected(self):
  with self.assertRaises(ValueError):attach_article_guides([],{'https://example.com':{'title':'A','guide':'x'}})
if __name__=='__main__':unittest.main()
