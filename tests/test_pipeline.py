import copy,json,pathlib,shutil,sys,tempfile,unittest
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
 def test_aobazaka_detection(self):
  self.assertEqual(collect.detect_groups('青葉坂46のオーディション制度を考察','',RULES),['青葉坂46'])
  self.assertEqual(collect.detect_groups('青葉坂46の坂道選抜に藤吉夏鈴がいない理由','',RULES),['櫻坂46','青葉坂46'])
  self.assertEqual(collect.detect_groups('Aobazaka46の構造','',RULES),['青葉坂46'])
  self.assertEqual(collect.detect_groups('青葉の写真を考察','',RULES),[])
  self.assertEqual(collect.detect_groups('青葉坂46の仕組み','櫻坂46とも関係する',RULES),['青葉坂46'])
  self.assertEqual(collect.classify('青葉坂46のオーディション制度を考察','',RULES)[0],'published')
  self.assertEqual(collect.classify('青葉坂46 自己紹介','',RULES)[0],'pending')
 def test_akimoto_creator_focus(self):
  examples=['秋元康は今、いくつのアイドルをプロデュースしているのか？',
            '秋元康氏は坂道グループから離れるべきか？',
            '秋元康の作詞観とAKB48の関係について']
  for title in examples:
   self.assertTrue(collect.creator_focus(title))
   status,_,cats,_,_=collect.classify(title,'',RULES)
   self.assertEqual(status,'published')
   self.assertIn('制作者・クリエイター論',cats)
 def test_incidental_reference_not_focus(self):
  for title,text in [('今週のアイドルニュース','秋元康が作詞する。'),
                     ('秋元康さん誕生日おめでとう',''),
                     ('AKB48 新曲の感想','')]:
   self.assertFalse(collect.creator_focus(title,text))
   self.assertNotIn('制作者・クリエイター論',collect.classify(title,text,RULES)[2])
 def test_production_magazine_title_variants(self):
  for title in ['秋元康やめろ。でも曲は書け。――AKBを聴き直して分かったこと',
                'TAKAHIROがいなかったら、櫻坂46はどうなっていたのか',
                '櫻坂46の表現は誰が作っているのか']:
   self.assertTrue(collect.creator_focus(title),title)
 def test_non_akimoto_creator_requires_group(self):
  self.assertTrue(collect.creator_focus('茅野しのぶのAKB48衣装制作を考察'))
  self.assertFalse(collect.creator_focus('茅野しのぶの衣装制作を考察'))
 def test_choreographers_and_creators_across_three_groups(self):
  examples=[
   ('TAKAHIROがいなかったら、櫻坂46の振付はどうなっていたか','櫻坂46'),
   ('INFINITYのダンサーが日向坂46のライブ表現を支える理由','日向坂46'),
   ('川村茜が乃木坂46の振付に与えた影響','乃木坂46'),
   ('米山美優のステージングは日向坂46をどう変えるか','日向坂46'),
   ('CRE8BOYによる乃木坂46の振付を考察','乃木坂46'),
   ('Seishiroの乃木坂46ダンス演出を分析','乃木坂46'),
   ('北畑向夏花による櫻坂46のMV振付の表現を読む','櫻坂46')]
  for title,group in examples:
   with self.subTest(title=title):
    self.assertTrue(collect.creator_focus(title))
    status,_,cats,_,_=collect.classify(title,'',RULES)
    self.assertEqual(status,'published')
    self.assertIn('制作者・クリエイター論',cats)
    self.assertIn(group,collect.detect_groups(title,'',RULES))
 def test_creator_news_or_unrelated_terms_do_not_trigger_creator_category(self):
  cases=[
   ('乃木坂46の新曲振付をCRE8BOYが担当',''),
   ('日向坂46の振付にINFINITYのダンサーが参加',''),
   ('川村茜のライブ振付を考察','他アーティストの話です'),
   ('INFINITYの新サービスを分析','乃木坂46とは無関係なサービスです'),
   ('乃木坂46のDeliciousを考察','LICOではありません')]
  for title,text in cases:
   with self.subTest(title=title):
    self.assertFalse(collect.creator_focus(title,text))
    self.assertNotIn('制作者・クリエイター論',collect.classify(title,text,RULES)[2])
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


class SongIndex(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory()
  self.root=pathlib.Path(self.tmp.name)
  shutil.copytree(collect.ROOT/'web',self.root/'web')
  collect.write(self.root/'config/rules.json',RULES)
  collect.write(self.root/'config/settings.json',{'base_url':'https://example.com/antenna','title':'坂道考察アンテナ'})
  collect.write(self.root/'config/sources.json',[{'id':'author1','enabled':True,'name':'架空の書き手','url':'https://note.com/author1','platform':'note'}])
  collect.write(self.root/'config/overrides.json',{})
  collect.write(self.root/'config/pickups.json',[])
 def tearDown(self):self.tmp.cleanup()
 def article(self,title,slug='one',status='published',groups=None,songs=None):
  return {'id':slug,'url':'https://note.com/author1/n/'+slug,
          'title':title,'author_id':'author1','status':status,
          'published_at':'2026-11-09T00:00:00+00:00','groups':groups if groups is not None else ['櫻坂46'],
          'categories':['楽曲・歌詞考察'],'members':[],'songs':songs or []}
 def render(self,articles):
  collect.write(self.root/'state/articles.json',articles)
  with patch.object(build,'ROOT',self.root):
   build.build()
  return (self.root/'dist/songs.html').read_text(encoding='utf-8')
 def test_song_index_has_real_titles_authors_and_sitemap(self):
  html_doc=self.render([self.article('『無言の宇宙』を考える'),
                        self.article('サヨナラの意味の歌詞考察',slug='two',groups=['乃木坂46'])])
  self.assertIn('無言の宇宙',html_doc)
  self.assertIn('サヨナラの意味',html_doc)
  self.assertIn('架空の書き手',html_doc)
  self.assertIn('https://note.com/author1/n/one',html_doc)
  self.assertNotIn('data.js',html_doc)
  self.assertIn("gtag('config', 'G-48Y73ZJHVL')",html_doc)
  self.assertIn('href="songs.html"',(self.root/'dist/index.html').read_text())
  self.assertIn('https://example.com/antenna/songs.html',(self.root/'dist/sitemap.xml').read_text())
  self.assertIn('rel="canonical" href="https://example.com/antenna/songs.html"',html_doc)
 def test_unpublished_and_rss_only_song_mentions_not_indexed(self):
  html_doc=self.render([
    self.article('『無言の宇宙』の感想',slug='pending',status='pending'),
    self.article('『無言の宇宙』の考察',slug='excluded',status='excluded'),
    self.article('日々の活動を振り返る',slug='rss-only',songs=['無言の宇宙']),
    self.article('BANANAの話',slug='banana')])
  self.assertNotIn('href="https://note.com/author1/n/pending"',html_doc)
  self.assertNotIn('href="https://note.com/author1/n/excluded"',html_doc)
  self.assertNotIn('href="https://note.com/author1/n/rss-only"',html_doc)
  self.assertNotIn('href="https://note.com/author1/n/banana"',html_doc)
  self.assertIn('現在、楽曲名が記事タイトルに含まれる収録記事はありません',html_doc)
 def test_wrong_group_not_indexed(self):
  html_doc=self.render([self.article('無言の宇宙を考える',groups=['乃木坂46'])])
  self.assertNotIn('href="https://note.com/author1/n/one"',html_doc)
 def test_escapes_article_title_and_does_not_copy_text(self):
  title='無言の宇宙 <script>alert(1)</script> を読む'
  html_doc=self.render([self.article(title)])
  self.assertIn('無言の宇宙 &lt;script&gt;alert(1)&lt;/script&gt; を読む',html_doc)
  self.assertNotIn('<script>alert(1)</script>',html_doc)
 def test_empty_songs_still_has_navigable_page(self):
  html_doc=self.render([])
  self.assertIn('楽曲別索引',html_doc)
  self.assertIn('現在、楽曲名が記事タイトルに含まれる収録記事はありません',html_doc)

class Integration(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=pathlib.Path(self.tmp.name);self.mock=patch.object(collect,'ROOT',self.root);self.mock.start()
  collect.write(self.root/'config/rules.json',RULES)
  collect.write(self.root/'config/sources.json',[{'id':'test','url':'https://note.com/test','feed':'https://note.com/test/rss','enabled':True}])
  collect.write(self.root/'config/overrides.json',{})
  self.cache=self.root/'cache';self.cache.mkdir();(self.cache/'test.xml').write_bytes(RSS)
 def tearDown(self):self.mock.stop();self.tmp.cleanup()
 def rows(self):return collect.read(self.root/'state/articles.json',[])
 def write_rss(self,title,body):
  payload=RSS.replace('櫻坂46 MV'.encode(),title.encode()).replace(b'Test body',body.encode())
  (self.cache/'test.xml').write_bytes(payload)
 def require_review_for_test_author(self):
  sources=collect.read(self.root/'config/sources.json',[])
  sources[0]['article_policy']='review_required'
  collect.write(self.root/'config/sources.json',sources)
 def test_selected_refresh_preserves_other_sources_and_feed_status(self):
  sources=collect.read(self.root/'config/sources.json',[])
  sources.append({'id':'other','url':'https://note.com/other','feed':'https://note.com/other/rss','enabled':True})
  collect.write(self.root/'config/sources.json',sources)
  other={'id':'other','url':'https://note.com/other/n/old','author_id':'other','title':'乃木坂46の歌詞考察','published_at':'2025-01-01','status':'published','reason':'確認済み','categories':['楽曲・歌詞考察'],'groups':['乃木坂46']}
  collect.write(self.root/'state/articles.json',[other])
  collect.write(self.root/'state/status.json',{'feeds':[{'id':'other','checked_at':'2025-01-01','status':'ok','last_success':'2025-01-01'}]})
  self.assertEqual(collect.run(self.cache,['test']),0)
  self.assertEqual(next(a for a in self.rows() if a['author_id']=='other'),other)
  report=collect.read(self.root/'state/status.json',{})
  self.assertEqual(report['scope'],'selected');self.assertEqual(report['total_feeds'],2)
  self.assertEqual(next(f for f in report['feeds'] if f['id']=='other')['checked_at'],'2025-01-01')
 def test_selected_disabled_or_unknown_source_rejected(self):
  with self.assertRaises(ValueError):collect.run(self.cache,['unknown'])
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
 def test_mixed_author_plain_live_impression_is_auto_published(self):
  # An ordinary impression is eligible; depth and literary merit are not scored.
  self.require_review_for_test_author()
  self.write_rss('櫻坂46のライブ感想',
                 '櫻坂46のライブを見て感じたことを書きました。歌やダンスについての感想をいくつか並べただけですが、自分が見た範囲で印象に残った場面を振り返っています。')
  collect.run(self.cache)
  self.assertEqual(self.rows()[0]['status'],'published')
 def test_mixed_author_creator_essay_is_auto_published(self):
  self.require_review_for_test_author()
  self.write_rss('秋元康の作詞についての考察',
                 '秋元康の作詞がアイドルの楽曲制作にどう関わるかを考えました。複数の作品を見比べ、詞と歌唱について思ったことをまとめています。')
  collect.run(self.cache)
  self.assertEqual(self.rows()[0]['status'],'published')
  self.assertEqual(self.rows()[0]['groups'],[])
 def test_mixed_author_labeled_fiction_still_excluded(self):
  self.require_review_for_test_author()
  self.write_rss('【妄ツイ】櫻坂46と過ごした日の感想',
                 '櫻坂46のメンバーと休日を過ごすフィクションを書きました。実際の活動に関する批評ではなく、架空のストーリーを描いた創作です。')
  collect.run(self.cache)
  self.assertEqual(self.rows()[0]['status'],'excluded')
 def test_mixed_author_unlabeled_fiction_like_title_held(self):
  self.require_review_for_test_author()
  self.write_rss('藤吉夏鈴と過ごす放課後',
                 '藤吉夏鈴と学校から一緒に帰る物語を想像しました。帰り道で話をして、放課後の教室に戻り、二人だけで秘密の会話を続ける架空の物語です。')
  collect.run(self.cache)
  self.assertNotEqual(self.rows()[0]['status'],'published')
 def test_mixed_author_ambiguous_generic_essay_held(self):
  self.require_review_for_test_author()
  self.write_rss('日々の考察',
                 '櫻坂46の活動について考えることもありましたが、日々の暮らしの話が中心です。自分の感想としてさまざまな話題を書いています。')
  collect.run(self.cache)
  self.assertEqual(self.rows()[0]['status'],'pending')
 def test_mixed_author_short_rss_excerpt_held(self):
  self.require_review_for_test_author()
  self.write_rss('日向坂46のライブ感想','とても楽しかったです。')
  collect.run(self.cache)
  self.assertEqual(self.rows()[0]['status'],'pending')
 def test_mixed_author_admin_hold_wins(self):
  self.require_review_for_test_author()
  self.write_rss('櫻坂46のライブ感想',
                 '櫻坂46のライブに行った日の感想です。楽曲やメンバーの歌唱、ダンス、舞台演出などについて、自分の印象をまとめています。')
  collect.write(self.root/'config/overrides.json',{'articles':{'https://note.com/test/n/abc':{'status':'pending','reason':'管理者確認待ち'}}})
  collect.run(self.cache)
  self.assertEqual(self.rows()[0]['status'],'pending')
 def test_mixed_author_critique_of_fiction_is_not_auto_excluded(self):
  self.require_review_for_test_author()
  self.write_rss('櫻坂46の妄ツイ文化を批評する',
                 '妄ツイという表現形式が櫻坂46のファンダムに与える影響を考えます。書き手と読み手が何を楽しんでいるかという文化論です。')
  collect.run(self.cache)
  self.assertEqual(self.rows()[0]['status'],'pending')
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
 def test_aobazaka_legacy_groups_and_override(self):
  old={'id':'legacy','url':'https://note.com/test/n/old','author_id':'test',
       'title':'青葉坂46の坂道選抜に藤吉夏鈴はいない理由','published_at':'2026-09-24T00:00:00+00:00',
       'status':'published','reason':'管理者承認済み','categories':['グループ運営・アイドル論'],
       'members':['藤吉夏鈴'],'songs':[],'groups':['櫻坂46']}
  collect.write(self.root/'state/articles.json',[old])
  collect.run(self.cache)
  restored=next(a for a in self.rows() if a['id']=='legacy')
  self.assertEqual(restored['groups'],['櫻坂46','青葉坂46'])
  self.assertEqual(restored['status'],'published')
  self.assertEqual(restored['published_at'],old['published_at'])
  collect.write(self.root/'config/overrides.json',{'articles':{old['url']:{'groups':['櫻坂46']}}})
  collect.run(self.cache)
  self.assertEqual(next(a for a in self.rows() if a['id']=='legacy')['groups'],['櫻坂46'])
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
 def test_legacy_creator_category_migrates_without_changing_publication(self):
  old={'id':'legacy','url':'https://note.com/test/n/old','author_id':'test',
       'title':'秋元康は坂道グループから離れるべきか','published_at':'2026-01-01T00:00:00+00:00',
       'status':'published','reason':'旧分類','categories':['秋元康・制作者論'],
       'members':[],'songs':[],'groups':[]}
  collect.write(self.root/'state/articles.json',[old])
  collect.run(self.cache)
  fixed=next(x for x in self.rows() if x['id']=='legacy')
  self.assertEqual(fixed['status'],'published')
  self.assertEqual(fixed['groups'],[])
  self.assertEqual(fixed['categories'],['制作者・クリエイター論'])
 def test_group_neutral_creator_is_published(self):
  item='''<rss><channel><item><title>秋元康は今、いくつのアイドルをプロデュースしているのか？</title>
  <link>https://note.com/test/n/abc</link><pubDate>Thu, 01 Jan 2026 09:00:00 +0900</pubDate>
  <description>作詞家の制作体制を検討。多くのグループを同時に担当する制作体制が各楽曲の歌詞にどのような影響を及ぼすのか、過去の作品と比較しながら考察します。</description></item></channel></rss>'''.encode()
  (self.cache/'test.xml').write_bytes(item)
  collect.run(self.cache)
  row=self.rows()[0]
  self.assertEqual(row['status'],'published')
  self.assertEqual(row['groups'],[])
  self.assertIn('制作者・クリエイター論',row['categories'])
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
  self.assertIn('制作者・クリエイター論',fixed['categories'])
 def test_explicit_empty_group_override_for_creator_essay(self):
  item='''<rss><channel><item><title>秋元康と櫻坂46の制作論</title>
  <link>https://note.com/test/n/abc</link><pubDate>Thu, 01 Jan 2026 09:00:00 +0900</pubDate>
  <description>グループの制作体制を考察します。櫻坂46の歌詞や演出に関する具体的な作品を比較しながら、作詞家と制作チームの役割について検討します。</description></item></channel></rss>'''.encode()
  (self.cache/'test.xml').write_bytes(item)
  collect.write(self.root/'config/overrides.json',{'articles':{'https://note.com/test/n/abc':{'groups':[]}}})
  collect.run(self.cache)
  self.assertEqual(self.rows()[0]['status'],'published')
  self.assertEqual(self.rows()[0]['groups'],[])
 def test_foreign_author_skipped(self):
  (self.cache/'test.xml').write_bytes(RSS.replace(b'/test/n/',b'/other/n/'));collect.run(self.cache);self.assertEqual(self.rows(),[])
if __name__=='__main__':unittest.main()
