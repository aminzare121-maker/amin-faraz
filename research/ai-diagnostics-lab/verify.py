import sys
import unittest
from pathlib import Path
sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).resolve().parent))
from run import offline_audit
sys.addaudithook(offline_audit)
result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.discover(str(Path(__file__).resolve().parent/'tests')))
sys.exit(not result.wasSuccessful())
