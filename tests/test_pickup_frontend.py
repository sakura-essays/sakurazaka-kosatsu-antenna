"""Frontend regression check uses the Node runtime supplied on GitHub runners."""
import pathlib,subprocess,unittest
class PickupFrontend(unittest.TestCase):
 def test_real_app_pickup_rendering(self):
  subprocess.run(['node',str(pathlib.Path(__file__).with_name('test_pickup_cards.js'))],check=True)
