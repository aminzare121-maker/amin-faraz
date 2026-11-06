import contextlib
import io
import unittest
from unittest.mock import patch
import local_secret_once as entry

class LocalSecretTests(unittest.TestCase):
    def test_piped_stdin_cannot_read_or_launch(self):
        with patch.object(entry.sys.stdin,'isatty',return_value=False),patch.object(entry.getpass,'getpass') as read,patch.object(entry.host,'run_once') as run,contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(entry.main(),2);read.assert_not_called();run.assert_not_called()

    def test_decline_cannot_read_or_launch(self):
        with patch.object(entry.sys.stdin,'isatty',return_value=True),patch('builtins.input',return_value='NO'),patch.object(entry.getpass,'getpass') as read,patch.object(entry.host,'run_once') as run,contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(entry.main(),2);read.assert_not_called();run.assert_not_called()

    def test_secret_is_local_and_hook_restored(self):
        output=io.StringIO();before=entry.host.cached_auth
        def run(code,launcher):
            self.assertEqual(entry.host.cached_auth(),'SYNTHETIC_ONLY_CREDENTIAL')
            self.assertEqual(code,entry.CODE_SHA);self.assertEqual(launcher,entry.LAUNCHER_SHA)
            return {'status':'CHILD_EXITED','returncode':0}
        with patch.object(entry.sys.stdin,'isatty',return_value=True),patch('builtins.input',return_value='YES'),patch.object(entry.getpass,'getpass',return_value='SYNTHETIC_ONLY_CREDENTIAL'),patch.object(entry.host,'run_once',side_effect=run),contextlib.redirect_stdout(output):
            self.assertEqual(entry.main(),0)
        self.assertIs(entry.host.cached_auth,before)
        self.assertNotIn('SYNTHETIC_ONLY_CREDENTIAL',output.getvalue())

if __name__=='__main__':unittest.main(verbosity=2)
