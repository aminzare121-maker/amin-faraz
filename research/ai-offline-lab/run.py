"""Entry point: local lab only; guard denies all socket/process attempts."""
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))


def offline_audit(event, args):
    if event.startswith("socket.") or event in {"subprocess.Popen", "os.system", "os.exec"}:
        raise RuntimeError("Offline research prohibits network and external processes")


sys.addaudithook(offline_audit)

from faraz_lab.runner import main

if __name__ == "__main__":
    main()
