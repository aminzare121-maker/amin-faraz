"""Pure public tests: no private Artin audiovisual material committed to CI."""
import unittest
from artin_9_visual_context_gate import validate_boundaries, validate_media_member, media_identity_matches

class PublicArtinVisualContextGate(unittest.TestCase):
    def test_exact_relative_interval(self):
        self.assertEqual(validate_boundaries(12.125, 14.5, 10, 20),(2.125,4.5))
    def test_start_below_media_is_rejected(self):
        with self.assertRaises(ValueError):validate_boundaries(9, 11, 10, 20)
    def test_end_after_media_is_rejected(self):
        with self.assertRaises(ValueError):validate_boundaries(13, 23, 10, 20)
    def test_zero_length_utterance_rejected(self):
        with self.assertRaises(ValueError):validate_boundaries(13, 13, 10, 20)
    def test_non_numeric_timing_rejected(self):
        with self.assertRaises(ValueError):validate_boundaries('13',14,10,20)
    def test_valid_image_path(self):
        validate_media_member('original_mp4_frames/session_19_capture.jpg')
    def test_path_traversal_rejected(self):
        with self.assertRaises(ValueError):validate_media_member('original_mp4_frames/../../hidden.wav')
    def test_absolute_path_rejected(self):
        with self.assertRaises(ValueError):validate_media_member('/original_mp4_frames/frame.jpg')
    def test_unsupported_path_rejected(self):
        with self.assertRaises(ValueError):validate_media_member('original_mp4_frames/secrets.txt')
    def test_source_audio_equality_is_sha_linked(self):
        self.assertTrue(media_identity_matches(b'original PCM',b'original PCM'))
        self.assertFalse(media_identity_matches(b'original PCM',b'changed PCM'))

if __name__=='__main__':unittest.main()