import copy,json,pathlib,sys,tempfile,unittest
from unittest.mock import patch
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts'))
import collect,review,admin
RULES=collect.read(collect.ROOT/'config/rules.json',{})
class Gate(unittest.TestCase):
 def test_fiction_and_names_not_evidence(self):
  for title,text in [('藤吉夏鈴と同棲','櫻坂46のメンバーと暮らす話'),('井上和のライブ感想【妄ツイ】','乃木坂46の考察です'),('日向坂46の休日','△△：「好きです」')]:
   status,reason,*_=collect.classify(title,text,RULES)
   self.assertNotEqual(collect.rss_publication_gate({'article_policy':'review_required'},title,text,status,reason,{})[0],'published')
 def test_culture_criticism_is_reviewable(self):
  title='妄ツイを公開するのはやめよう';body='櫻坂46に関する妄ツイの消費と表現の倫理を考えます。'
  self.assertEqual(collect.fiction_guard(title,body)[0],'pending')
  self.assertEqual(collect.publication_gate({},title,body,'published','',{'status':'published','verified_nonfiction':True})[0],'published')
 def test_insufficient_rss_and_previous_publication(self):
  args=({},'藤吉夏鈴の表現','感想','published','',{})
  self.assertEqual(collect.rss_publication_gate(*args)[0],'pending')
  self.assertEqual(collect.rss_publication_gate(*args,{'title':args[1],'status':'published'})[0],'published')
 def test_circle_section_heading_is_not_fictional_dialogue(self):
  self.assertIsNone(collect.fiction_guard('レコードを整理しようとしたけれど／青い影のこと','〇「青い影」のその後。乃木坂46の音楽についての感想。'))
  self.assertEqual(collect.fiction_guard('アイドルとの休日','〇：おはよう。')[0],'pending')
 def test_moderation_wins_over_fiction_and_verification(self):
  for status in ('pending','excluded'):
   self.assertEqual(collect.publication_gate({},'妄ツイ','〇〇「会話」','published','',{'status':status,'verified_nonfiction':True})[0],status)
 def test_reviewed_title_changes_require_review(self):
  self.assertEqual(collect.publication_gate({},'新しいタイトル','','published','',{'status':'published','verified_nonfiction':True,'reviewed_title':'元のタイトル'})[0],'pending')

class Reviews(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=pathlib.Path(self.tmp.name)
  self.patches=[patch.object(m,'ROOT',self.root) for m in (review,admin,collect)]
  for p in self.patches:p.start()
  collect.write(self.root/'config/rules.json',RULES)
  collect.write(self.root/'config/sources.json',[{'id':'mixed','url':'https://note.com/mixed','enabled':True,'article_policy':'review_required'}])
  collect.write(self.root/'config/overrides.json',{})
  self.e={'url':'https://note.com/mixed/n/abc','author_id':'mixed','title':'乃木坂46の制度を考える','published_at':'2025-01-02','groups':['乃木坂46'],'categories':['グループ運営・アイドル論'],'body_checked':True,'evidence_url':'https://note.com/mixed/n/abc','reason':'公開本文で実際の選抜制度の批評と確認'}
 def tearDown(self):
  for p in self.patches:p.stop()
  self.tmp.cleanup()
 def test_backfill_dedup_dry_run_and_metadata_only(self):
  review.apply_reviews([self.e],True);self.assertFalse((self.root/'config/manual_articles.json').exists())
  review.apply_reviews([self.e]);review.apply_reviews([self.e])
  rows=collect.read(self.root/'config/manual_articles.json',[]);self.assertEqual(len(rows),1);self.assertEqual(rows[0]['published_at'],'2025-01-02')
  self.assertNotIn('body_checked',rows[0]);self.assertNotIn('text',rows[0])
 def test_batch_validation_is_atomic(self):
  bad=copy.deepcopy(self.e);bad['url']='https://note.com/other/n/bad'
  with self.assertRaises(ValueError):review.apply_reviews([self.e,bad])
  self.assertFalse((self.root/'config/overrides.json').read_text().find('verified_nonfiction')>=0)
 def test_blocks_and_explicit_holds_are_preserved(self):
  for o in [{'blocked_urls':[self.e['url']]},{'blocked_authors':['mixed']},{'articles':{self.e['url']:{'status':'excluded'}}},{'articles':{self.e['url']:{'status':'pending'}}}]:
   collect.write(self.root/'config/overrides.json',o)
   with self.assertRaises(ValueError):review.apply_reviews([self.e])
   self.assertEqual(collect.read(self.root/'config/overrides.json',{}),o)
 def test_unconfirmed_body_date_group_and_duplicates_rejected(self):
  for key,value in [('body_checked',False),('published_at','unknown'),('published_at','2099-01-01'),('groups',['架空坂46'])]:
   e=copy.deepcopy(self.e);e[key]=value
   with self.assertRaises(ValueError):review.apply_reviews([e])
  with self.assertRaises(ValueError):review.apply_reviews([self.e,self.e|{'url':self.e['url']+'?utm_source=x'}])
 def test_date_conflict_and_title_conflict(self):
  collect.write(self.root/'state/articles.json',[self.e|{'published_at':'2025-01-03'}])
  with self.assertRaises(ValueError):review.apply_reviews([self.e])
 def test_admin_preserves_groups_categories_and_evidence(self):
  review.apply_reviews([self.e])
  with patch.dict('os.environ',{'ADMIN_ACTION':'hold_article','TARGET_URL':self.e['url']}):admin.main()
  o=collect.read(self.root/'config/overrides.json',{})['articles'][self.e['url']]
  self.assertEqual(o['groups'],self.e['groups']);self.assertEqual(o['categories'],self.e['categories']);self.assertIn('evidence_url',o);self.assertEqual(o['status'],'pending')
if __name__=='__main__':unittest.main()
