import unittest

from services.pokemon_api import parse_set_for_db
from services.set_names import english_set_name


class SetNameTests(unittest.TestCase):
    def test_japanese_set_gets_english_name(self):
        name = english_set_name("SV1S", "ja", "スカーレットex")
        self.assertNotEqual(name, "スカーレットex")
        self.assertTrue(name.isascii())

    def test_en_and_fr_keep_native_name(self):
        self.assertEqual(english_set_name("SV1S", "fr", "Écarlate"), "Écarlate")
        self.assertEqual(english_set_name("sv1", "en", "Scarlet & Violet"), "Scarlet & Violet")

    def test_unknown_code_keeps_native_name(self):
        self.assertEqual(english_set_name("zzz", "ko", "원본"), "원본")

    def test_english_set_with_same_id_wins(self):
        self.assertEqual(english_set_name("sv1", "zh-tw", "朱", english_by_id={"sv1": "Scarlet & Violet"}), "Scarlet & Violet")

    def test_parse_set_keeps_native_name(self):
        parsed = parse_set_for_db({"id": "SV1S", "name": "スカーレットex", "_lang": "ja"})
        self.assertEqual(parsed["native_name"], "スカーレットex")
        self.assertTrue(parsed["name"].isascii())
        french = parse_set_for_db({"id": "sv1", "name": "Écarlate", "_lang": "fr"})
        self.assertEqual((french["name"], french["native_name"]), ("Écarlate", None))


if __name__ == "__main__":
    unittest.main()
