import unittest
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api.social import get_leaderboard
from database import Base
from models import Card, CollectionItem, Set, User, UserSetting


class LeaderboardMarketTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.db = sessionmaker(bind=engine)()
        self.user = User(username="ash", hashed_password="x", role="admin", is_active=True)
        self.db.add(self.user)
        self.db.add(Set(id="a_en", tcg_set_id="a", name="A", lang="en"))
        self.db.add(Card(id="a-1_en", name="Zard", set_id="a", number="1", lang="en", is_custom=False,
                         price_trend=10.0, price_tcg_normal_market=40.0))
        self.db.commit()
        self.db.add(CollectionItem(user_id=self.user.id, card_id="a-1_en", quantity=1, variant="Normal"))
        self.db.add(UserSetting(user_id=self.user.id, key="price_market", value="tcgplayer"))
        self.db.commit()

    def test_top_card_and_total_use_the_owners_market(self):
        with patch("services.price_context.get_usd_to_eur_rate", return_value=1.0):
            board = get_leaderboard(price_field="price_trend", db=self.db, current_user=self.user)
        self.assertEqual(board[0]["most_valuable_card"]["price_market"], 40.0)
        self.assertEqual(board[0]["total_value"], 40.0)


if __name__ == "__main__":
    unittest.main()
