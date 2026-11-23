import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base
from models import Card, Set
from services.chs_import import import_chs_cards

INFOS = {"collections": [{
    "commodityCode": "CSV1C", "name": "朱", "salesDate": "2023-01-01", "seriesText": "朱&紫",
    "image": "img/1/cover.png",
    "cards": [{"id": 7, "name": "皮卡丘", "image": "img/1/1.png",
               "details": {"collectionNumber": "001/078", "rarityText": "C", "hp": 60,
                           "cardTypeText": "宝可梦", "illustratorName": ["A", "B"]}}],
}, {"commodityCode": "EMPTY", "cards": []}]}


class ChsImportTests(unittest.TestCase):
    def test_import_creates_sets_and_cards_idempotently(self):
        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(engine)
        db = sessionmaker(bind=engine)()
        self.assertEqual(import_chs_cards(db, INFOS), {"sets": 1, "cards": 1})
        self.assertEqual(import_chs_cards(db, INFOS), {"sets": 1, "cards": 1})
        card = db.query(Card).one()
        self.assertEqual(card.id, "chs-7_zh-cn")
        self.assertEqual(card.lang, "zh-cn")
        self.assertEqual(card.artist, "A, B")
        self.assertTrue(card.images_small.endswith("/img/1/1.png"))
        self.assertEqual(db.query(Set).one().total, 1)
        db.close()


if __name__ == "__main__":
    unittest.main()
