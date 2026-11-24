import unittest
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api.collection import get_user_collection
from database import Base
from models import Card, CollectionItem, Set, User, UserSetting


class UserCollectionPricesTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.db = sessionmaker(bind=engine)()
        self.owner = User(username="owner", hashed_password="x", role="trainer", is_active=True)
        self.viewer = User(username="viewer", hashed_password="x", role="admin", is_active=True)
        self.db.add_all([self.owner, self.viewer, Set(id="a_en", tcg_set_id="a", name="A", lang="en")])
        self.db.add(Card(id="a-1_en", name="Zard", set_id="a", number="1", lang="en", is_custom=False,
                         price_trend=10.0, price_tcg_normal_market=40.0))
        self.db.commit()
        self.db.add(CollectionItem(user_id=self.owner.id, card_id="a-1_en", quantity=1, variant="Normal"))
        self.db.add(UserSetting(user_id=self.owner.id, key="price_market", value="tcgplayer"))
        self.db.commit()

    def test_prices_follow_the_owners_choices(self):
        with patch("services.price_context.get_usd_to_eur_rate", return_value=1.0):
            items = get_user_collection(self.owner.id, price_field="price_trend", current_user=self.viewer, db=self.db)
        self.assertEqual(items[0].effective_price, 40.0)
        self.assertEqual(items[0].price_used_market, "tcgplayer")


if __name__ == "__main__":
    unittest.main()
