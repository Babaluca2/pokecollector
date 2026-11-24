import unittest

try:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from api.cards import search_cards
    from database import Base
    from models import Card, Set, Setting, User

    DEPS = True
except ModuleNotFoundError:
    DEPS = False


@unittest.skipUnless(DEPS, "deps missing")
class SmartSearchTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.db = sessionmaker(bind=engine)()
        self.user = User(username="ash", hashed_password="x", role="trainer", is_active=True)
        self.db.add_all([
            self.user,
            Setting(key="tcgdex_sync_languages", value="en"),
            Set(id="a_en", tcg_set_id="a", name="Obsidian Flames", abbreviation="OBF", lang="en"),
            Set(id="b_en", tcg_set_id="b", name="Paldea Evolved", abbreviation="PAL", lang="en"),
            Card(id="a-125_en", name="Charizard ex", set_id="a", number="125", lang="en", is_custom=False),
            Card(id="b-125_en", name="Pikachu", set_id="b", number="125", lang="en", is_custom=False),
            Card(id="b-7_en", name="Charizard", set_id="b", number="7", lang="en", is_custom=False),
        ])
        self.db.commit()
        self.db.refresh(self.user)

    def ids(self, q):
        res = search_cards(q=q, type_filter=None, db=self.db, current_user=self.user, lang="en")
        return sorted(c["id"] for c in res["data"])

    def test_set_name_and_number(self):
        self.assertEqual(self.ids("obsidian flames 125"), ["a-125_en"])

    def test_set_name_card_name_and_number(self):
        self.assertEqual(self.ids("Obsidian Flames Charizard 125"), ["a-125_en"])

    def test_card_name_and_number(self):
        self.assertEqual(self.ids("charizard 125"), ["a-125_en"])

    def test_number_with_total(self):
        self.assertEqual(self.ids("paldea evolved pikachu 125/193"), ["b-125_en"])

    def test_short_set_code_and_abbreviation(self):
        self.assertEqual(self.ids("obf charizard 125"), ["a-125_en"])
        self.assertEqual(self.ids("PAL pikachu"), ["b-125_en"])
        self.assertEqual(self.ids("pal 125"), ["b-125_en"])
        self.assertEqual(self.ids("b charizard"), [])  # one-letter codes are ignored
        self.assertEqual(sorted(self.ids("pal")), ["b-125_en", "b-7_en"])

    def test_plain_name_unchanged(self):
        self.assertEqual(self.ids("charizard"), ["a-125_en", "b-7_en"])

    def test_no_match_falls_back_to_plain_name_search(self):
        self.assertEqual(self.ids("charizard 999"), [])


if __name__ == "__main__":
    unittest.main()
