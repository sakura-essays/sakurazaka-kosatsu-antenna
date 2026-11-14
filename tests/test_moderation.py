"""Mixed writers can be enabled; their fiction cannot bypass article review."""
import pathlib,sys,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts'))
import collect
class ArticleGate(unittest.TestCase):
 def test_fiction_body_blocks_group_title(self):
  self.assertEqual(collect.publication_gate({},'日向坂46 三期生ライブ','妄想の中で開催したライブです','published','',{})[0],'excluded')
 def test_mixed_source_needs_verified_article(self):
  s={'article_policy':'review_required'}
  self.assertEqual(collect.publication_gate(s,'乃木坂46 ライブ感想','','published','',{})[0],'pending')
  self.assertEqual(collect.publication_gate(s,'乃木坂46 ライブ感想','','published','',{'status':'published'})[0],'pending')
  self.assertEqual(collect.publication_gate(s,'乃木坂46 ライブ感想','','published','',{'status':'published','verified_nonfiction':True})[0],'published')
 def test_criticism_is_not_automatically_excluded(self):
  self.assertEqual(collect.fiction_guard('乃木坂の妄ツイ文化について考察','これは批評です')[0],'pending')
 def test_ordinary_diary_is_not_fiction(self):
  self.assertIsNone(collect.fiction_guard('日向坂46 ライブ日記','今日のライブを見た。'))
 def test_explicit_fiction_title(self):
  self.assertEqual(collect.fiction_guard('森田ひかる 夢小説','')[0],'excluded')

class DeploymentAssets(unittest.TestCase):
 def test_updated_index_requests_new_data_url(self):
  import tempfile,re
  from unittest.mock import patch
  import build
  with tempfile.TemporaryDirectory() as tmp:
   root=pathlib.Path(tmp);(root/'web').mkdir()
   (root/'web/index.html').write_text('<head></head><script defer src="data.js"></script><script defer src="app.js"></script><link href="style.css">')
   for name in ('app.js','style.css','contact.html','songs.html','analytics.js'):(root/'web'/name).write_text('')
   collect.write(root/'config/settings.json',{})
   collect.write(root/'config/rules.json',{'categories':{}})
   collect.write(root/'config/sources.json',[])
   collect.write(root/'state/articles.json',[])
   with patch.object(build,'ROOT',root):
    build.build()
    first=re.search(r'src="(data.js[^\"]*)"',(root/'dist/index.html').read_text())[1]
    collect.write(root/'state/status.json',{'attempted_at':'2026-11-08T00:00:00Z'})
    build.build()
    second=re.search(r'src="(data.js[^\"]*)"',(root/'dist/index.html').read_text())[1]
    self.assertNotEqual(first,second)

if __name__=='__main__':unittest.main()
