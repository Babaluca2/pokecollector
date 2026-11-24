import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base
from models import Card, Set
from services.chs_import import import_chs_cards

INFOS = {"collections": [{
    "id": 1, "commodityCode": "CSV1C", "name": "朱", "salesDate": "2023-01-01", "seriesText": "朱&紫",
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
        self.assertEqual(card.id, "chs-1-7_zh-cn")
        self.assertEqual(card.lang, "zh-cn")
        self.assertEqual(card.number, "001")
        self.assertEqual(card.artist, "A, B")
        self.assertTrue(card.images_small.endswith("/img/1/1.png"))
        self.assertEqual(db.query(Set).one().total, 1)

    def test_same_card_in_two_products_is_kept_in_both(self):
        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(engine)
        db = sessionmaker(bind=engine)()
        card = {"id": 7, "name": "皮卡丘", "image": "img/1/1.png", "details": {}}
        infos = {"collections": [
            {"id": 1, "commodityCode": "A", "name": "a", "cards": [card]},
            {"id": 2, "commodityCode": "B", "name": "b", "cards": [card]},
        ]}
        import_chs_cards(db, infos)
        self.assertEqual(sorted(c.set_id for c in db.query(Card).all()), ["chs-A", "chs-B"])
        db.close()
        db.close()



class ExternalCardsAreNotSentToTcgdexTests(unittest.TestCase):
    def test_external_ids_never_hit_tcgdex(self):
        from services import pokemon_api

        self.assertTrue(pokemon_api.is_external_card_id("chs-1-7"))
        self.assertTrue(pokemon_api.is_external_card_id("pkmndb-5"))
        self.assertFalse(pokemon_api.is_external_card_id("sv1-001"))
        self.assertIsNone(pokemon_api.get_card("pkmndb-5", lang="ja"))

    def test_enrichment_skips_external_cards(self):
        from services.card_metadata import card_needs_metadata_enrichment

        self.assertFalse(card_needs_metadata_enrichment(Card(id="pkmndb-5_ja", tcg_card_id="pkmndb-5", name="x", lang="ja")))


if __name__ == "__main__":
    unittest.main()
