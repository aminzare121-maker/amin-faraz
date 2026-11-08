"""Run only this standalone lab's synthetic unittest suite, with no network."""
import sys
import unittest
from pathlib import Path

root = Path(__file__).resolve().parent
sys.dont_write_bytecode = True
sys.path.insert(0, str(root))


def offline_audit(event, args):
    if event.startswith("socket.") or event in {"subprocess.Popen", "os.system", "os.exec"}:
        raise RuntimeError("Offline synthetic verification prohibits network/processes")


sys.addaudithook(offline_audit)
suite = unittest.defaultTestLoader.discover(str(root/"tests"), pattern="test_*.py")
result = unittest.TextTestRunner(verbosity=2).run(suite)
raise SystemExit(not result.wasSuccessful())
