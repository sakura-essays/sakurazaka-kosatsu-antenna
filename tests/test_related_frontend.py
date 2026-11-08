import pathlib, subprocess, unittest
class RelatedFrontend(unittest.TestCase):
 def test_related_articles(self):
  subprocess.run(['node',str(pathlib.Path(__file__).with_name('test_related_articles.js'))],check=True)
