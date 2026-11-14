import pathlib,subprocess,unittest
class Analytics(unittest.TestCase):
 def test_analytics_behavior(self):
  subprocess.run(['node',str(pathlib.Path(__file__).with_suffix('.js'))],check=True)
