import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base
from models import Card, Set
from services.jp_import import import_jp_cards

SETS = [
    {"id": 1, "language": "ja", "released": True, "name": "Known", "code": "SV1S"},
    {"id": 2, "language": "ja", "released": True, "name": "Unknown", "code": "XX"},
    {"id": 3, "language": "ja", "released": False, "name": "Future", "code": "FUT"},
]
CARDS = [
    {"id": 10, "set_id": 1, "language": "ja", "name": "A", "number": "001", "image_url": "https://i/a.jpg"},
    {"id": 11, "set_id": 2, "language": "ja", "name": "B", "number": "005", "image_url": "https://i/b.jpg"},
    {"id": 12, "set_id": 2, "language": "ja", "name": "C", "number": "006", "image_url": None},
]


class JpImportTests(unittest.TestCase):
    def test_fills_known_sets_and_creates_unknown(self):
        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(engine)
        db = sessionmaker(bind=engine)()
        db.add(Set(id="SV1S_ja", tcg_set_id="SV1S", name="x", lang="ja"))
        db.add(Card(id="SV1S-001_ja", tcg_card_id="SV1S-001", name="a", set_id="SV1S", number="001", lang="ja"))
        db.commit()
        result = import_jp_cards(db, (SETS, CARDS))
        self.assertEqual(result, {"filled": 1, "sets": 1, "cards": 1})
        self.assertEqual(db.query(Card).filter(Card.id == "SV1S-001_ja").one().images_small, "https://i/a.jpg")
        self.assertEqual(db.query(Set).filter(Set.id == "pkmndb-2_ja").one().total, 1)
        self.assertEqual(import_jp_cards(db, (SETS, CARDS))["filled"], 0)
        db.close()


if __name__ == "__main__":
    unittest.main()
