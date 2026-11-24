import datetime
import unittest

from services.product_opening import allocate_unit_costs

try:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from api.auth import get_current_user
    from api.products import router as products_router
    from database import get_db
    API_DEPS = True
except Exception:  # pragma: no cover
    API_DEPS = False


class AllocationTests(unittest.TestCase):
    def test_equal_split_adds_back_up_to_the_price(self):
        costs = allocate_unit_costs(10.0, [{"quantity": 2, "value": 5}, {"quantity": 1, "value": 1}], "equal")
        self.assertAlmostEqual(costs[0] * 2 + costs[1] * 1, 10.0, places=2)
        self.assertAlmostEqual(costs[0], costs[1], places=2)

    def test_value_split_weights_by_market_value(self):
        costs = allocate_unit_costs(12.0, [{"quantity": 1, "value": 9}, {"quantity": 1, "value": 3}], "value")
        self.assertEqual(costs, [9.0, 3.0])

    def test_value_split_falls_back_to_equal_without_prices(self):
        costs = allocate_unit_costs(6.0, [{"quantity": 1, "value": 0}, {"quantity": 2, "value": 0}], "value")
        self.assertEqual(costs, [2.0, 2.0])

    def test_none_assigns_no_cost(self):
        self.assertEqual(allocate_unit_costs(10.0, [{"quantity": 1, "value": 1}], "none"), [None])

    def test_rounding_remainder_keeps_the_total_exact(self):
        costs = allocate_unit_costs(10.0, [{"quantity": 1, "value": 0}] * 3, "equal")
        self.assertAlmostEqual(sum(costs), 10.0, places=2)


@unittest.skipUnless(API_DEPS, "FastAPI/httpx are not installed")
class OpenProductApiTests(unittest.TestCase):
    def setUp(self):
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from sqlalchemy.pool import StaticPool
        from database import Base
        from models import Card, ProductPurchase, Set, User

        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(engine)
        self.db = sessionmaker(bind=engine)()
        self.user = User(username="owner", hashed_password="x")
        self.db.add(self.user)
        self.db.add(Set(id="sv1_en", tcg_set_id="sv1", name="SV1", lang="en"))
        self.db.add(Card(id="sv1-1_en", tcg_card_id="sv1-1", name="A", set_id="sv1", number="1", lang="en", price_trend=6.0))
        self.db.add(Card(id="sv1-2_en", tcg_card_id="sv1-2", name="B", set_id="sv1", number="2", lang="en", price_trend=2.0))
        self.product = ProductPurchase(
            product_name="Pack", product_type="Booster", purchase_price=4.0,
            purchase_date=datetime.date(2026, 11, 1), user_id=None,
        )
        self.db.add(self.product)
        self.db.commit()
        self.product.user_id = self.user.id
        self.db.commit()
        app = FastAPI()
        app.include_router(products_router, prefix="/api/products")
        app.dependency_overrides[get_current_user] = lambda: self.user
        app.dependency_overrides[get_db] = lambda: self.db
        self.client = TestClient(app)

    def tearDown(self):
        self.db.close()

    def test_opening_adds_cards_with_allocated_cost_and_marks_opened(self):
        from models import CollectionItem
        resp = self.client.post(f"/api/products/{self.product.id}/open", json={
            "allocation": "value",
            "cards": [{"card_id": "sv1-1_en", "quantity": 1}, {"card_id": "sv1-2_en", "quantity": 1}],
        })
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertEqual(body["lifecycle_status"], "opened")
        self.assertEqual(body["linked_cards_count"], 2)
        prices = {i.card_id: i.purchase_price for i in self.db.query(CollectionItem).all()}
        self.assertEqual(prices, {"sv1-1_en": 3.0, "sv1-2_en": 1.0})


if __name__ == "__main__":
    unittest.main()
