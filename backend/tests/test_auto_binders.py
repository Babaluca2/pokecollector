import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base
from models import Binder, BinderCard, Card, CollectionItem, Set, User
from services.auto_binders import sync_auto_binder


class AutoBinderTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(engine)
        self.db = sessionmaker(bind=engine)()
        self.user = User(username="u", hashed_password="x")
        self.db.add(self.user)
        self.db.add(Set(id="sv3pt5_fr", tcg_set_id="sv3pt5", name="151", lang="fr"))
        self.db.add(Card(id="sv3pt5-6_fr", tcg_card_id="sv3pt5-6", name="Dracaufeu ex", set_id="sv3pt5", number="6", lang="fr"))
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def _item(self, qty=1):
        item = CollectionItem(user_id=self.user.id, card_id="sv3pt5-6_fr", quantity=qty, variant="Normal")
        self.db.add(item)
        self.db.commit()
        return item

    def test_first_card_creates_the_set_binder_and_next_copies_update_it(self):
        item = self._item()
        sync_auto_binder(self.db, self.user, item)
        binder = self.db.query(Binder).one()
        self.assertEqual(binder.auto_owned_set_id, "sv3pt5_fr")
        self.assertEqual(binder.name, "151 (FR)")
        entry = self.db.query(BinderCard).one()
        self.assertEqual(entry.required_quantity, 1)

        item.quantity = 3
        self.db.commit()
        sync_auto_binder(self.db, self.user, item)
        self.assertEqual(self.db.query(Binder).count(), 1)
        self.assertEqual(self.db.query(BinderCard).one().required_quantity, 3)

    def test_card_without_a_known_set_is_ignored(self):
        self.db.add(Card(id="x-1_en", tcg_card_id="x-1", name="Orphan", set_id="nope", lang="en"))
        item = CollectionItem(user_id=self.user.id, card_id="x-1_en", quantity=1, variant="Normal")
        self.db.add(item)
        self.db.commit()
        sync_auto_binder(self.db, self.user, item)
        self.assertEqual(self.db.query(Binder).count(), 0)


if __name__ == "__main__":
    unittest.main()
