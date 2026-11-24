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
    {"id": 10, "set_id": 1, "language": "ja", "name": "A", "number": "001", "image_url": "https://pub-54a82c9e988c459da62f95d0bd9c78d9.r2.dev/a.jpg"},
    {"id": 11, "set_id": 2, "language": "ja", "name": "B", "number": "005", "image_url": "https://pub-54a82c9e988c459da62f95d0bd9c78d9.r2.dev/b.jpg"},
    {"id": 12, "set_id": 2, "language": "ja", "name": "C", "number": "006", "image_url": None},
    {"id": 13, "set_id": 2, "language": "ja", "name": "D", "number": "007", "image_url": "http://169.254.169.254/x.jpg"},
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
        self.assertEqual(db.query(Card).filter(Card.id == "SV1S-001_ja").one().images_small, "https://pub-54a82c9e988c459da62f95d0bd9c78d9.r2.dev/a.jpg")
        self.assertEqual(db.query(Set).filter(Set.id == "pkmndb-2_ja").one().total, 1)
        self.assertEqual(import_jp_cards(db, (SETS, CARDS))["filled"], 0)
        db.close()



class SyncKeepsDatasetImageTests(unittest.TestCase):
    def test_empty_tcgdex_sync_keeps_dataset_image_but_tcgdex_image_wins(self):
        from services.card_upsert import upsert_card

        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(engine)
        db = sessionmaker(bind=engine)()
        db.add(Card(id="X-1_ja", tcg_card_id="X-1", name="a", set_id="X", number="1", lang="ja",
                    images_small="https://r2/x.jpg", images_large="https://r2/x.jpg", image_source_lang="ja"))
        db.commit()
        base = {"id": "X-1_ja", "tcg_card_id": "X-1", "name": "a", "set_id": "X", "number": "1", "lang": "ja"}
        upsert_card(db, {**base, "images_small": None, "images_large": None})
        db.commit()
        card = db.query(Card).one()
        self.assertEqual(card.images_small, "https://r2/x.jpg")
        upsert_card(db, {**base, "images_small": "https://assets.tcgdex.net/ja/X/1/low.webp",
                         "images_large": "https://assets.tcgdex.net/ja/X/1/high.webp"})
        db.commit()
        card = db.query(Card).one()
        self.assertEqual(card.images_small, "https://assets.tcgdex.net/ja/X/1/low.webp")
        self.assertIsNone(card.image_source_lang)
        db.close()


if __name__ == "__main__":
    unittest.main()
