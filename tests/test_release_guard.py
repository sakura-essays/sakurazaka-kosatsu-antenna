import pathlib,sys,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts'))
from check_release import unexpected_losses
class ReleaseGuard(unittest.TestCase):
 def test_unexplained_drop_stops_and_moderation_allows(self):
  old=[{'url':'https://note.com/x/n/1','author_id':'x'}];sources=[{'id':'x','enabled':True}]
  self.assertEqual(unexpected_losses(old,[],sources,{}),[old[0]['url']])
  for overrides in [{'blocked_urls':[old[0]['url']]},{'blocked_authors':['x']},{'articles':{old[0]['url']:{'status':'pending'}}},{'articles':{old[0]['url']:{'status':'excluded'}}}]:
   self.assertEqual(unexpected_losses(old,[],sources,overrides),[])
  self.assertEqual(unexpected_losses(old,[],[{'id':'x','enabled':False}],{}),[])
  self.assertEqual(unexpected_losses(old,[old[0]|{'status':'published'}],sources,{}),[])
if __name__=='__main__':unittest.main()
