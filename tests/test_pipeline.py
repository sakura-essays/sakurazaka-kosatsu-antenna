import copy,json,pathlib,sys,tempfile,unittest
from unittest.mock import patch
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts'))
import collect,build
RULES=collect.read(collect.ROOT/'config/rules.json',{})
RSS=b'''<rss version="2.0"><channel><title>Test</title><item><title>\xe6\xab\xbb\xe5\x9d\x8246 MV</title><link>https://note.com/test/n/abc?utm_source=x</link><pubDate>Thu, 01 Jan 2026 09:00:00 +0900</pubDate><description>Test body</description></item></channel></rss>'''
class Rules(unittest.TestCase):
 def test_rss_dates(self):self.assertEqual(list(collect.parse(RSS))[0]['published_at'],'2026-01-01T00:00:00+00:00')
 def test_atom_original_not_updated(self):
  x=b'<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>A</title><link href="https://example.org/a"/><published>2020-01-01T00:00:00Z</published><updated>2026-01-01T00:00:00Z</updated></entry></feed>'
  self.assertTrue(list(collect.parse(x))[0]['published_at'].startswith('2020'))
 def test_no_fake_date(self):self.assertIsNone(collect.date('unknown'))
 def test_title_without_group(self):self.assertEqual(collect.classify('藤吉夏鈴はなぜ目を引くか','',RULES)[0],'published')
 def test_body_related(self):self.assertEqual(collect.classify('あの夜に見たもの','櫻坂46のライブを見た感想です',RULES)[0],'published')
 def test_unrelated(self):self.assertEqual(collect.classify('今日のお昼ご飯','カレーを食べた。',RULES)[0],'excluded')
 def test_ambiguous(self):self.assertEqual(collect.classify('最近の暮らし','櫻坂のCDも買いました。',RULES)[0],'pending')
 def test_cross_group_uses_title(self):
  self.assertEqual(collect.classify('乃木坂46 ライブ感想','櫻坂にも触れる',RULES)[0],'published')
  self.assertEqual(collect.detect_groups('乃木坂46 ライブ感想','櫻坂にも触れる',RULES),['乃木坂46'])
 def test_each_group(self):
  self.assertEqual(collect.detect_groups('藤吉夏鈴の表現','',RULES),['櫻坂46'])
  self.assertEqual(collect.detect_groups('井上和のセンター論','',RULES),['乃木坂46'])
  self.assertEqual(collect.detect_groups('正源司陽子の歌唱','',RULES),['日向坂46'])
  self.assertEqual(collect.detect_groups('乃木坂46と日向坂46','',RULES),['乃木坂46','日向坂46'])
  self.assertEqual(collect.detect_groups('AKB48の衣装','',RULES),[])
 def test_akimoto_creator_focus(self):
  examples=['秋元康は今、いくつのアイドルをプロデュースしているのか？',
            '秋元康氏は坂道グループから離れるべきか？',
            '秋元康の作詞観とAKB48の関係について']
  for title in examples:
   self.assertTrue(collect.creator_focus(title))
   status,_,cats,_,_=collect.classify(title,'',RULES)
   self.assertEqual(status,'published')
   self.assertIn('秋元康・制作者論',cats)
 def test_incidental_reference_not_focus(self):
  for title,text in [('今週のアイドルニュース','秋元康が作詞する。'),
                     ('秋元康さん誕生日おめでとう',''),
                     ('AKB48 新曲の感想','')]:
   self.assertFalse(collect.creator_focus(title,text))
   self.assertNotIn('秋元康・制作者論',collect.classify(title,text,RULES)[2])
 def test_production_magazine_title_variants(self):
  for title in ['秋元康やめろ。でも曲は書け。――AKBを聴き直して分かったこと',
                'TAKAHIROがいなかったら、櫻坂46はどうなっていたのか',
                '櫻坂46の表現は誰が作っているのか']:
   self.assertTrue(collect.creator_focus(title),title)
 def test_non_akimoto_creator_requires_group(self):
  self.assertTrue(collect.creator_focus('茅野しのぶのAKB48衣装制作を考察'))
  self.assertFalse(collect.creator_focus('茅野しのぶの衣装制作を考察'))
 def test_song_context(self):
  self.assertEqual(collect.classify('帰り道は遠回りしたくなる 歌詞考察','',RULES)[0],'published')
  self.assertEqual(collect.classify('乃木坂46 自己紹介','',RULES)[0],'pending')
 def test_english_song_false_match(self):self.assertFalse(collect.song_match('BAN',collect.norm('urban research')))
 def test_promotion_hold(self):self.assertEqual(collect.classify('櫻坂46 自己紹介','',RULES)[0],'pending')
 def test_canonical(self):self.assertEqual(collect.canonical('https://note.com/test/n/abc?utm_source=x#foo'),'https://note.com/test/n/abc')
 def test_unsafe_link(self):
  with self.assertRaises(ValueError):collect.canonical('javascript:alert(1)')
 def test_entity_block(self):
  with self.assertRaises(ValueError):list(collect.parse(b'<!DOCTYPE rss [<!ENTITY x SYSTEM "file:///etc/passwd">]><rss/>'))
 def test_html_not_feed(self):
  with self.assertRaises(ValueError):list(collect.parse(b'<html/>'))

class Picks(unittest.TestCase):
 def setUp(self):
  self.article={'url':'https://note.com/test/n/abc','title':'実在の考察','author_id':'test'}
 def test_pickup_requires_published_article(self):
  picks=[{'url':self.article['url'],'note':'具体的な読みを提示している'}]
  self.assertEqual(build.curated_pickups([self.article],picks),picks)
  self.assertEqual(build.curated_pickups([],picks),[])
 def test_pickup_deduplicates_and_hides_private_scores(self):
  picks=[{'url':self.article['url'],'note':'要再読','score':98}]*2
  self.assertEqual(build.curated_pickups([self.article],picks),[{'url':self.article['url'],'note':'要再読'}])
 def test_pickup_invalid_entry_rejected(self):
  for x in [{'url':'javascript:alert(1)','note':'いい記事'}, {'url':self.article['url'],'note':''}]:
   with self.assertRaises(ValueError):build.curated_pickups([self.article],[x])

class Integration(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=pathlib.Path(self.tmp.name);self.mock=patch.object(collect,'ROOT',self.root);self.mock.start()
  collect.write(self.root/'config/rules.json',RULES)
  collect.write(self.root/'config/sources.json',[{'id':'test','url':'https://note.com/test','feed':'https://note.com/test/rss','enabled':True}])
  collect.write(self.root/'config/overrides.json',{})
  self.cache=self.root/'cache';self.cache.mkdir();(self.cache/'test.xml').write_bytes(RSS)
 def tearDown(self):self.mock.stop();self.tmp.cleanup()
 def rows(self):return collect.read(self.root/'state/articles.json',[])
 def test_dedup_and_date(self):
  collect.run(self.cache);collect.run(self.cache);self.assertEqual(len(self.rows()),1);self.assertEqual(self.rows()[0]['published_at'],'2026-01-01T00:00:00+00:00')
  self.assertNotIn('text',self.rows()[0])
 def test_failure_retains(self):
  collect.run(self.cache);(self.cache/'test.xml').write_bytes(b'broken');self.assertEqual(collect.run(self.cache),2);self.assertEqual(len(self.rows()),1)
 def test_takedown_not_reimported(self):
  collect.run(self.cache);collect.write(self.root/'config/overrides.json',{'blocked_urls':['https://note.com/test/n/abc']});collect.run(self.cache);self.assertEqual(self.rows(),[])
 def test_author_removed(self):
  collect.run(self.cache);collect.write(self.root/'config/overrides.json',{'blocked_authors':['test']});collect.run(self.cache);self.assertEqual(self.rows(),[])
 def test_future_hold(self):
  (self.cache/'test.xml').write_bytes(RSS.replace(b'2026',b'2099'));collect.run(self.cache);self.assertEqual(self.rows()[0]['status'],'pending')
 def test_body_fiction_cannot_be_republished_by_unverified_override(self):
  (self.cache/'test.xml').write_bytes(RSS.replace(b'Test body','ここからはフィクションです'.encode()))
  collect.write(self.root/'config/overrides.json',{'articles':{'https://note.com/test/n/abc':{'status':'published'}}})
  collect.run(self.cache)
  self.assertEqual(self.rows()[0]['status'],'excluded')
  self.assertNotIn('text',self.rows()[0])
 def test_mixed_source_article_approval_is_separate(self):
  sources=collect.read(self.root/'config/sources.json',[]);sources[0]['article_policy']='review_required'
  collect.write(self.root/'config/sources.json',sources);collect.run(self.cache)
  self.assertEqual(self.rows()[0]['status'],'pending')
  collect.write(self.root/'config/overrides.json',{'articles':{'https://note.com/test/n/abc':{'status':'published','verified_nonfiction':True}}})
  collect.run(self.cache);self.assertEqual(self.rows()[0]['status'],'published')
 def test_absent_from_feed_retained(self):
  collect.run(self.cache);(self.cache/'test.xml').write_bytes(RSS.replace(b'/abc?',b'/def?'));collect.run(self.cache);self.assertEqual(len(self.rows()),2)
 def test_legacy_other_group_reclassification(self):
  old={'id':'legacy','url':'https://note.com/test/n/old','author_id':'test',
       'title':'乃木坂46の楽曲考察','published_at':'2026-01-01T00:00:00+00:00',
       'status':'pending','reason':'他グループ中心の可能性・比較内容の確認待ち',
       'categories':['楽曲・歌詞考察'],'members':[],'songs':[]}
  collect.write(self.root/'state/articles.json',[old])
  collect.run(self.cache)
  restored=next(a for a in self.rows() if a['id']=='legacy')
  self.assertEqual(restored['status'],'pending')
  collect.write(self.root/'config/overrides.json',{'articles':{old['url']:{'status':'published','verified_nonfiction':True}}})
  collect.run(self.cache)
  self.assertEqual(next(a for a in self.rows() if a['id']=='legacy')['status'],'published')
  self.assertEqual(restored['groups'],['乃木坂46'])
 def test_previous_published_survives_changed_description(self):
  old={'id':'legacy','url':'https://note.com/test/n/abc','author_id':'test',
       'title':'櫻坂46 MV','published_at':'2026-01-01T00:00:00+00:00',
       'status':'published','reason':'管理者承認済み','categories':['楽曲・歌詞考察'],
       'members':[],'songs':[],'groups':['櫻坂46']}
  collect.write(self.root/'state/articles.json',[old])
  rules=copy.deepcopy(RULES)
  rules['group_rules']={}
  rules['members']=[]
  rules['songs']=[]
  collect.write(self.root/'config/rules.json',rules)
  collect.run(self.cache)
  self.assertEqual(self.rows()[0]['status'],'published')
 def test_previously_published_remains_published(self):
  old={'id':'legacy','url':'https://note.com/test/n/abc','author_id':'test',
       'title':'櫻坂46 MV','published_at':'2026-01-01T00:00:00+00:00',
       'status':'published','reason':'管理者承認済み','categories':['楽曲・歌詞考察'],
       'members':[],'songs':[],'groups':['櫻坂46']}
  collect.write(self.root/'state/articles.json',[old])
  (self.cache/'test.xml').write_bytes(RSS.replace(b'\xe6\xab\xbb\xe5\x9d\x8246 MV',b'Unrelated'))
  collect.run(self.cache)
  # Changed titles are intentionally re-evaluated instead of whitelisted.
  self.assertEqual(self.rows()[0]['status'],'excluded')
 def test_group_neutral_creator_is_published(self):
  item='''<rss><channel><item><title>秋元康は今、いくつのアイドルをプロデュースしているのか？</title>
  <link>https://note.com/test/n/abc</link><pubDate>Thu, 01 Jan 2026 09:00:00 +0900</pubDate>
  <description>作詞家の制作体制を検討</description></item></channel></rss>'''.encode()
  (self.cache/'test.xml').write_bytes(item)
  collect.run(self.cache)
  row=self.rows()[0]
  self.assertEqual(row['status'],'published')
  self.assertEqual(row['groups'],[])
  self.assertIn('秋元康・制作者論',row['categories'])
  collect.run(self.cache)
  self.assertEqual(self.rows()[0]['groups'],[])
 def test_legacy_creator_group_does_not_fall_back_to_sakura(self):
  old={'id':'legacy','url':'https://note.com/test/n/old','author_id':'test',
       'title':'秋元康やめろ。でも曲は書け。――AKBを聴き直して分かったこと',
       'published_at':'2026-01-01T00:00:00+00:00','status':'published',
       'reason':'旧分類','categories':['グループ運営・アイドル論'],
       'members':[],'songs':[],'groups':['櫻坂46']}
  collect.write(self.root/'state/articles.json',[old]);collect.run(self.cache)
  fixed=next(x for x in self.rows() if x['id']=='legacy')
  self.assertEqual(fixed['status'],'published')
  self.assertEqual(fixed['groups'],[])
  self.assertIn('秋元康・制作者論',fixed['categories'])
 def test_explicit_empty_group_override_for_creator_essay(self):
  item='''<rss><channel><item><title>秋元康と櫻坂46の制作論</title>
  <link>https://note.com/test/n/abc</link><pubDate>Thu, 01 Jan 2026 09:00:00 +0900</pubDate>
  <description>グループの制作</description></item></channel></rss>'''.encode()
  (self.cache/'test.xml').write_bytes(item)
  collect.write(self.root/'config/overrides.json',{'articles':{'https://note.com/test/n/abc':{'groups':[]}}})
  collect.run(self.cache)
  self.assertEqual(self.rows()[0]['status'],'published')
  self.assertEqual(self.rows()[0]['groups'],[])
 def test_foreign_author_skipped(self):
  (self.cache/'test.xml').write_bytes(RSS.replace(b'/test/n/',b'/other/n/'));collect.run(self.cache);self.assertEqual(self.rows(),[])
if __name__=='__main__':unittest.main()
