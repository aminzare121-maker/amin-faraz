import unittest
import local_once_host as host

class SafeDiagnosticTests(unittest.TestCase):
    def test_network_error_never_reflects_secret(self):
        secret='test-placeholder-not-a-real-credential'
        result=host.safe_child_diagnostic(1, ('Authorization: Bearer '+secret+'\n[WinError 10013]').encode())
        self.assertEqual(result,'LOCAL_NETWORK_PERMISSION_DENIED')
        self.assertNotIn(secret,result)
    def test_http_forbidden_is_not_assumed_invalid_token(self):
        self.assertEqual(host.safe_child_diagnostic(1,b'HTTPError: HTTP Error 403: Forbidden'), 'HTTP_STATUS_403')
    def test_unknown_error_has_no_output_reflection(self):
        self.assertEqual(host.safe_child_diagnostic(1,b'private path and arbitrary content'), 'CHILD_ERROR_CLASS_UNAVAILABLE')
    def test_exit_zero_is_not_handshake(self):
        self.assertEqual(host.safe_child_diagnostic(0,b''),'PROCESS_EXITED_ZERO_NOT_HANDSHAKE_VERIFIED')

if __name__=='__main__':unittest.main()

