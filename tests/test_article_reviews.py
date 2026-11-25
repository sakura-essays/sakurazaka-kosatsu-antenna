import copy,json,pathlib,sys,tempfile,unittest
from unittest.mock import patch
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts'))
import collect,review,admin,eligibility
RULES=collect.read(collect.ROOT/'config/rules.json',{})
class Gate(unittest.TestCase):
 def verdict(self,title,body='',override=None,prior=None):
  now=collect.dt.datetime(2026,11,25,tzinfo=collect.UTC)
  row={'title':title,'url':'https://note.com/mixed/n/abc','author_id':'mixed',
       'published_at':'2026-11-24','first_seen_at':'2026-11-25',
       'status':(prior or {}).get('status','retry'),'groups':['櫻坂46'],'categories':[]}
  eligibility.apply(row,eligibility.Eligibility(RULES,[],{}),override or {},prior or {},now,
                    body=body,warning=collect.fiction_guard(title,body))
  return row
 def test_fiction_and_names_not_evidence(self):
  for title,body in [('藤吉夏鈴と同棲','櫻坂46のメンバーと暮らす話'),('井上和のライブ感想【妄ツイ】','乃木坂46の考察です'),('日向坂46の休日','△△：「好きです」')]:
   self.assertNotEqual(self.verdict(title,body)['status'],'published')
 def test_culture_criticism_auto_passes(self):
  self.assertEqual(self.verdict('櫻坂46の妄ツイ文化を批評する','ファンダム文化論です。')['status'],'published')
 def test_short_excerpt_with_clear_subject(self):
  self.assertEqual(self.verdict('藤吉夏鈴の表現について','良かった')['status'],'published')
  self.assertEqual(self.verdict('夏のこと','良かった')['status'],'retry')
 def test_previous_publication_survives_missing_evidence(self):
  title='少し遠い夜'
  self.assertEqual(self.verdict(title)['status'],'retry')
  self.assertEqual(self.verdict(title,prior={'title':title,'status':'published'})['status'],'published')
 def test_circle_section_heading_is_not_fictional_dialogue(self):
  self.assertIsNone(collect.fiction_guard('レコードを整理しようとしたけれど／青い影のこと','〇「青い影」のその後。乃木坂46の音楽についての感想。'))
  self.assertEqual(collect.fiction_guard('アイドルとの休日','〇：おはよう。')[0],'pending')
 def test_moderation_wins_over_fiction_and_verification(self):
  for status in ('pending','excluded'):
   self.assertEqual(self.verdict('櫻坂46のMV感想',override={'status':status,'verified_nonfiction':True,'manual_hold':True})['status'],status)
 def test_changed_title_is_reassessed_without_old_override(self):
  self.assertEqual(self.verdict('新しいタイトル',override={'status':'published','verified_nonfiction':True,'reviewed_title':'元のタイトル'})['status'],'retry')
 def test_new_human_hold_and_legacy_evidence_holds_are_distinct(self):
  self.assertEqual(self.verdict('櫻坂46のライブ感想',override={'status':'pending','reviewed_at':'2026-11-12','review_note':'初期収集'})['status'],'published')
  self.assertEqual(self.verdict('櫻坂46の活動について',override={'status':'pending','reviewed_at':'2026-11-18','reason':'私生活に関する未確認の疑惑'})['status'],'pending')
 def test_retry_expires_but_better_evidence_can_publish(self):
  first=self.verdict('時間の話')
  old=first|{'retry_until':'2026-11-24T00:00:00+00:00'}
  self.assertEqual(self.verdict('時間の話',prior=old)['status'],'unresolved')
  self.assertEqual(self.verdict('時間の話','乃木坂46のダンスで感じたこと',prior=old)['status'],'published')
 def test_author_class_does_not_waive_article_evidence(self):
  history=[{'url':str(i),'title':'乃木坂46の選抜感想','author_id':'mixed',
            'published_at':'2026-01-01','status':'published'} for i in range(11)]
  engine=eligibility.Eligibility(RULES,history,{})
  self.assertEqual(engine.profiles['mixed'],('A',['乃木坂46']))
  self.assertEqual(engine.decide('今日のお昼ご飯','カレー','', 'mixed',{},None)[0],'excluded')
  self.assertEqual(engine.decide('推しメンのこと','',(), 'mixed',{},None)[0],'published')
  self.assertEqual(engine.decide('推しメンのこと','',(), 'unknown',{},None)[0],'retry')
 def test_confirmed_group_neutral_creator_uses_editorial_categories(self):
  override={'status':'published','verified_nonfiction':True,'groups':[],
            'categories':['制作者・クリエイター論']}
  row=self.verdict('バラバラなのに、並ぶとAKB48になる――茅野しのぶの衣装',override=override)
  self.assertEqual(row['status'],'published')
  self.assertEqual(row['groups'],[])
 def test_song_subject_disclaimed_in_feed(self):
  self.assertEqual(self.verdict('君に叱られた','乃木坂の楽曲の話じゃないです。家族にスマホの見すぎだと叱られました。')['status'],'retry')
 def test_group_evidence_requires_related_context(self):
  engine=eligibility.Eligibility(RULES,[],{})
  for title in ('日向坂46からのお知らせ', '承認欲求について'):
   self.assertNotEqual(engine.decide(title,'',(), 'unknown',{},None)[0],'published')
  self.assertEqual(engine.decide('夏の映像を見た','',('乃木坂46',), 'unknown',{},None)[0],'retry')
  self.assertEqual(engine.decide('ステージの振付を見た','',('乃木坂46',), 'unknown',{},None)[0],'published')

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
 def test_confirmed_alias_members_are_retained_as_metadata(self):
  e=self.e|{'title':'増本論','groups':['櫻坂46'],'categories':['メンバー考察・人物論'],'members':['増本綺良','増本綺良']}
  review.apply_reviews([e])
  o=collect.read(self.root/'config/overrides.json',{})['articles'][e['url']]
  self.assertEqual(o['members'],['増本綺良'])
  cache=self.root/'cache';cache.mkdir();(cache/'mixed.xml').write_text('<rss><channel/></rss>')
  sources=collect.read(self.root/'config/sources.json',[]);sources[0]['feed']='https://note.com/mixed/rss'
  collect.write(self.root/'config/sources.json',sources)
  collect.run(cache)
  a=collect.read(self.root/'state/articles.json',[])[0]
  self.assertEqual(a['members'],['増本綺良']);self.assertEqual(a['status'],'published')
  self.assertEqual(a['published_at'],'2025-01-02')
  collect.run(cache)
  self.assertEqual(collect.read(self.root/'state/articles.json',[])[0]['members'],['増本綺良'])
 def test_unknown_confirmed_members_reject_whole_batch(self):
  bad=self.e|{'url':'https://note.com/mixed/n/bad','members':['架空の人']}
  with self.assertRaises(ValueError):review.apply_reviews([self.e,bad])
  self.assertEqual(collect.read(self.root/'config/overrides.json',{}),{})
  self.assertFalse((self.root/'config/manual_articles.json').exists())
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
