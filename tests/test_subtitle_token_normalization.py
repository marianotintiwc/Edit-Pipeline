import unittest

from ugc_pipeline.subtitle_tokens import normalize_subtitle_tokens


class TestSubtitleTokenNormalization(unittest.TestCase):
    def test_al_tiro_to_altiro(self):
        self.assertEqual(
            normalize_subtitle_tokens("Te lo mando al tiro"),
            "Te lo mando altiro",
        )

    def test_case_insensitive(self):
        self.assertEqual(normalize_subtitle_tokens("Al Tiro"), "altiro")

    def test_passthrough_empty(self):
        self.assertEqual(normalize_subtitle_tokens(""), "")

    def test_output_is_exactly_altiro(self):
        self.assertEqual(normalize_subtitle_tokens("al tiro"), "altiro")
        self.assertEqual(normalize_subtitle_tokens("AL TIRO"), "altiro")

    def test_karaoke_brackets(self):
        self.assertEqual(normalize_subtitle_tokens("[al] tiro"), "[altiro]")
        self.assertEqual(normalize_subtitle_tokens("al [tiro]"), "[altiro]")


if __name__ == "__main__":
    unittest.main()
