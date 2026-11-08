"""Independent offline review: subprocess and credential provider always mocked."""
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import local_once_host as host


class LocalHostReviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.workspace = root / 'workspace'; self.workspace.mkdir()
        self.bridge = root / 'bridge.py'; self.bridge.write_text('# synthetic reviewed file\n')
        self.launcher = root / 'START_ONCE.bat'; self.launcher.write_text('@rem synthetic reviewed launcher\n')
        self.launcher_digest = hashlib.sha256(self.launcher.read_bytes()).hexdigest()
        self.digest = hashlib.sha256(self.bridge.read_bytes()).hexdigest()
        self.patches = [patch.object(host, 'ROOT', root), patch.object(host, 'WORKSPACE', self.workspace), patch.object(host, 'BRIDGE', self.bridge), patch.object(host, 'LAUNCHER', self.launcher)]
        for item in self.patches:
            item.start(); self.addCleanup(item.stop)

    def test_absent_git_never_calls_subprocess(self):
        with patch.object(host.shutil, 'which', return_value=None), patch.object(host.subprocess, 'run') as run:
            self.assertIsNone(host.cached_auth())
            run.assert_not_called()

    def test_helper_failure_and_exception_have_no_output(self):
        for behavior in (SimpleNamespace(returncode=1, stdout='SYNTHETIC_SECRET', stderr='SYNTHETIC_SECRET'), OSError('SYNTHETIC_SECRET')):
            capture = io.StringIO()
            kwargs = {'side_effect': behavior} if isinstance(behavior, Exception) else {'return_value': behavior}
            with patch.object(host.shutil, 'which', return_value='synthetic-git'), patch.object(host.subprocess, 'run', **kwargs), contextlib.redirect_stdout(capture), contextlib.redirect_stderr(capture):
                self.assertIsNone(host.cached_auth())
            self.assertEqual(capture.getvalue(), '')

    def test_fixed_helper_command_noninteractive_child_env_only(self):
        before = dict(os.environ)
        with patch.object(host.shutil, 'which', return_value='synthetic-git'), patch.object(host.subprocess, 'run', return_value=SimpleNamespace(returncode=0, stdout='password=SYNTHETIC_SECRET\n')) as run:
            self.assertEqual(host.cached_auth(), 'SYNTHETIC_SECRET')
            args, kwargs = run.call_args
            self.assertEqual(args[0][-2:], ['credential', 'fill'])
            self.assertNotIn('SYNTHETIC_SECRET', str(args))
            for key in ('GIT_TERMINAL_PROMPT', 'GCM_INTERACTIVE', 'GIT_TRACE', 'GIT_TRACE_CURL', 'GCM_TRACE_SECRETS'):
                self.assertEqual(kwargs['env'][key], '0')
            self.assertNotIn('GIT_ASKPASS', kwargs['env'])
            self.assertFalse(kwargs['shell'])
            self.assertTrue(kwargs['capture_output'])
        self.assertEqual(dict(os.environ), before)

    def test_hash_changed_blocks_before_auth(self):
        self.bridge.write_text('# modified synthetic file\n')
        with patch.object(host, 'cached_auth') as auth, patch.object(host.subprocess, 'run') as run:
            self.assertEqual(host.run_once(self.digest, self.launcher_digest)['status'], 'BLOCKED_CODE_CHANGED')
            auth.assert_not_called(); run.assert_not_called()

    def test_launcher_changed_blocks_before_auth(self):
        self.launcher.write_text('@rem modified synthetic launcher\n')
        with patch.object(host, 'cached_auth') as auth, patch.object(host.subprocess, 'run') as run:
            self.assertEqual(host.run_once(self.digest, self.launcher_digest)['status'], 'BLOCKED_LAUNCHER_CHANGED')
            auth.assert_not_called(); run.assert_not_called()

    def test_secret_only_child_env_no_raw_outputs(self):
        before = dict(os.environ); seen = {}; capture = io.StringIO()
        def child(*args, **kwargs):
            seen['command'] = args[0]; seen['token'] = kwargs['env']['AMIN_BRIDGE_GH_TOKEN']
            seen['env_reference'] = kwargs['env']
            self.assertEqual(args[0][1:], ['/d', '/c', str(self.launcher), str(self.workspace)])
            self.assertEqual(Path(args[0][0]).name.lower(), 'cmd.exe')
            self.assertEqual(kwargs['env']['AMIN_BRIDGE_PYTHON'], host.sys.executable)
            self.assertFalse(kwargs['shell'])
            return SimpleNamespace(returncode=9, stdout=b'SYNTHETIC_SECRET', stderr=b'SYNTHETIC_SECRET')
        with patch.object(host, 'cached_auth', return_value='SYNTHETIC_SECRET'), patch.object(host.subprocess, 'run', side_effect=child), contextlib.redirect_stdout(capture), contextlib.redirect_stderr(capture):
            result = host.run_once(self.digest, self.launcher_digest)
        self.assertEqual(seen['token'], 'SYNTHETIC_SECRET')
        self.assertNotIn('SYNTHETIC_SECRET', str(seen['command']))
        self.assertNotIn('AMIN_BRIDGE_GH_TOKEN', seen['env_reference'])
        self.assertNotIn('SYNTHETIC_SECRET', json.dumps(result))
        self.assertEqual(capture.getvalue(), '')
        self.assertEqual(dict(os.environ), before)
        self.assertFalse(result['handshake_verified_by_host'])

    def test_timeout_secret_not_forwarded(self):
        failure = subprocess.TimeoutExpired(['synthetic'], 90, output=b'SYNTHETIC_SECRET', stderr=b'SYNTHETIC_SECRET')
        capture = io.StringIO()
        with patch.object(host, 'cached_auth', return_value='SYNTHETIC_SECRET'), patch.object(host.subprocess, 'run', side_effect=failure), contextlib.redirect_stdout(capture), contextlib.redirect_stderr(capture):
            result = host.run_once(self.digest, self.launcher_digest)
        self.assertEqual(result['status'], 'LOCAL_CHILD_TIMEOUT')
        self.assertNotIn('SYNTHETIC_SECRET', json.dumps(result))
        self.assertEqual(capture.getvalue(), '')


if __name__ == '__main__':
    unittest.main(verbosity=2)

