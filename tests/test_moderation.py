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
if __name__=='__main__':unittest.main()
