"""Valuing a card from Cardmarket, TCGPlayer or a manual price.

Cardmarket (EUR) and TCGPlayer (USD) sometimes disagree a lot, and one of them
is occasionally simply wrong. These tests hold the rules in place: the user's
default market applies unless a copy pins its own choice, a large gap is flagged
for the copy until a choice is made (once), and the choice can always be changed.
"""

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from services.card_values import (
    DEFAULT_DIVERGENCE_PCT,
    compare_markets,
    effective_item_price,
    normalize_item_price_source,
    resolve_item_price,
    tcgplayer_price_usd,
)

try:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from api.auth import get_current_user
    from api.collection import router as collection_router
    from api.settings import router as settings_router
    from database import get_db
    API_TEST_DEPS_AVAILABLE = True
except ModuleNotFoundError:
    API_TEST_DEPS_AVAILABLE = False


def make_card(**overrides):
    values = dict(
        price_market=10.0, price_trend=10.0, price_avg1=10.0, price_avg7=10.0,
        price_avg30=10.0, price_low=8.0,
        price_market_holo=None, price_trend_holo=None, price_avg1_holo=None,
        price_avg7_holo=None, price_avg30_holo=None, price_low_holo=None,
        price_tcg_normal_market=None, price_tcg_holo_market=None,
        price_tcg_reverse_market=None,
    )
    values.update(overrides)
    return SimpleNamespace(**values)


def make_item(card, variant="Normal", price_source=None, price_override=None):
    return SimpleNamespace(card=card, variant=variant, price_source=price_source, price_override=price_override)


class PureMarketRulesTests(unittest.TestCase):
    def test_tcgplayer_variant_mapping_with_fallback(self):
        card = make_card(price_tcg_holo_market=20.0)
        self.assertEqual(tcgplayer_price_usd(card, "Holo"), 20.0)
        # No normal price: a Normal copy falls back to the holofoil one.
        self.assertEqual(tcgplayer_price_usd(card, "Normal"), 20.0)
        self.assertIsNone(tcgplayer_price_usd(make_card(), "Normal"))

    def test_default_market_is_cardmarket(self):
        item = make_item(make_card(price_tcg_normal_market=20.0))
        self.assertEqual(resolve_item_price(item, "price_trend", "cardmarket", 1.0), (10.0, "cardmarket"))

    def test_default_market_can_be_tcgplayer_and_converts_usd(self):
        item = make_item(make_card(price_tcg_normal_market=20.0))
        price, market = resolve_item_price(item, "price_trend", "tcgplayer", 0.9)
        self.assertEqual(market, "tcgplayer")
        self.assertAlmostEqual(price, 18.0)

    def test_item_choice_beats_default_market(self):
        item = make_item(make_card(price_tcg_normal_market=20.0), price_source="tcgplayer")
        price, market = resolve_item_price(item, "price_trend", "cardmarket", 0.9)
        self.assertEqual(market, "tcgplayer")
        self.assertAlmostEqual(price, 18.0)

    def test_manual_price_wins_over_both_markets(self):
        item = make_item(make_card(price_tcg_normal_market=20.0), price_source="manual", price_override=3.5)
        self.assertEqual(resolve_item_price(item, "price_trend", "cardmarket", 0.9), (3.5, "manual"))

    def test_manual_price_of_zero_is_respected(self):
        item = make_item(make_card(), price_source="manual", price_override=0.0)
        self.assertEqual(effective_item_price(item, "price_trend", "cardmarket", 0.9), 0.0)

    def test_missing_market_falls_back_to_the_other_one(self):
        only_tcg = make_item(make_card(price_market=None, price_trend=None, price_avg1=None,
                                       price_avg7=None, price_avg30=None, price_low=None,
                                       price_tcg_normal_market=10.0))
        self.assertEqual(resolve_item_price(only_tcg, "price_trend", "cardmarket", 0.5), (5.0, "tcgplayer"))
        only_cm = make_item(make_card(), price_source="tcgplayer")
        self.assertEqual(resolve_item_price(only_cm, "price_trend", "cardmarket", 0.9), (10.0, "cardmarket"))

    def test_no_price_anywhere_is_zero(self):
        item = make_item(make_card(price_market=None, price_trend=None, price_avg1=None,
                                   price_avg7=None, price_avg30=None, price_low=None))
        self.assertEqual(resolve_item_price(item, "price_trend", "cardmarket", 0.9), (0, None))

    def test_exchange_rate_is_only_requested_when_needed(self):
        calls = []

        def rate():
            calls.append(1)
            return 0.9

        item = make_item(make_card(price_tcg_normal_market=20.0))
        resolve_item_price(item, "price_trend", "cardmarket", rate)
        self.assertEqual(calls, [])
        resolve_item_price(item, "price_trend", "tcgplayer", rate)
        self.assertEqual(calls, [1])

    def test_divergence_needs_both_a_percentage_and_an_absolute_gap(self):
        card = make_card(price_tcg_normal_market=20.0)
        result = compare_markets(card, "Normal", "price_trend", 1.0)
        self.assertTrue(result["diverges"])
        self.assertEqual(result["difference_pct"], 100.0)
        # Close prices: no warning.
        close = compare_markets(make_card(price_tcg_normal_market=11.0), "Normal", "price_trend", 1.0)
        self.assertFalse(close["diverges"])
        # Cheap bulk: 300% apart but under one euro.
        bulk = compare_markets(
            make_card(price_trend=0.10, price_market=0.10, price_tcg_normal_market=0.40),
            "Normal", "price_trend", 1.0,
        )
        self.assertFalse(bulk["diverges"])

    def test_divergence_threshold_is_configurable(self):
        card = make_card(price_tcg_normal_market=14.0)
        self.assertFalse(compare_markets(card, "Normal", "price_trend", 1.0, DEFAULT_DIVERGENCE_PCT + 10)["diverges"])
        self.assertTrue(compare_markets(card, "Normal", "price_trend", 1.0, 30)["diverges"])

    def test_no_comparison_without_an_exchange_rate(self):
        result = compare_markets(make_card(price_tcg_normal_market=20.0), "Normal", "price_trend", None)
        self.assertIsNone(result["tcgplayer"])
        self.assertFalse(result["diverges"])

    def test_source_normalisation(self):
        self.assertIsNone(normalize_item_price_source(None))
        self.assertIsNone(normalize_item_price_source(" "))
        self.assertEqual(normalize_item_price_source("TCGPlayer"), "tcgplayer")
        with self.assertRaises(ValueError):
            normalize_item_price_source("ebay")


@unittest.skipUnless(API_TEST_DEPS_AVAILABLE, "FastAPI/httpx are not installed in this lightweight test environment")
class CollectionPriceChoiceApiTests(unittest.TestCase):
    def setUp(self):
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from sqlalchemy.pool import StaticPool
        from database import Base
        from models import Card, Set, User

        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine)()
        self.user = User(username="owner", hashed_password="x")
        self.db.add(self.user)
        self.db.add(Set(id="sv1_en", tcg_set_id="sv1", name="Scarlet & Violet", lang="en"))
        # Cardmarket says 10 EUR, TCGPlayer says 20 USD (18 EUR at 0.9): a large gap.
        self.db.add(Card(
            id="sv1-1_en", tcg_card_id="sv1-1", name="Sprigatito", set_id="sv1", number="1", lang="en",
            price_market=10.0, price_trend=10.0, price_tcg_normal_market=20.0,
        ))
        self.db.commit()

        app = FastAPI()
        app.include_router(collection_router, prefix="/api/collection")
        app.include_router(settings_router, prefix="/api/settings")
        app.dependency_overrides[get_current_user] = lambda: self.user
        app.dependency_overrides[get_db] = lambda: self.db
        self.client = TestClient(app)
        patcher = patch("services.price_context.get_usd_to_eur_rate", return_value=0.9)
        patcher.start()
        self.addCleanup(patcher.stop)

    def tearDown(self):
        self.db.close()

    def _add(self, **extra):
        return self.client.post("/api/collection/", json={"card_id": "sv1-1_en", "quantity": 1, **extra})

    def test_adding_a_card_with_a_large_gap_asks_for_a_choice(self):
        resp = self._add()
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertTrue(body["needs_price_choice"])
        self.assertTrue(body["price_comparison"]["diverges"])
        self.assertEqual(body["price_comparison"]["cardmarket"], 10.0)
        self.assertEqual(body["price_comparison"]["tcgplayer"], 18.0)
        self.assertEqual(body["price_used_market"], "cardmarket")
        self.assertEqual(body["effective_price"], 10.0)

    def test_choosing_a_market_stops_the_prompt_and_changes_the_value(self):
        item_id = self._add().json()["id"]
        resp = self.client.put(f"/api/collection/{item_id}", json={"price_source": "tcgplayer"})
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertFalse(body["needs_price_choice"])
        self.assertEqual(body["price_used_market"], "tcgplayer")
        self.assertEqual(body["effective_price"], 18.0)
        stats = self.client.get("/api/collection/stats/summary").json()
        self.assertEqual(stats["total_value"], 18.0)

    def test_the_choice_can_be_changed_again_and_reset(self):
        item_id = self._add().json()["id"]
        self.client.put(f"/api/collection/{item_id}", json={"price_source": "tcgplayer"})
        manual = self.client.put(f"/api/collection/{item_id}", json={"price_source": "manual", "price_override": 7.25})
        self.assertEqual(manual.json()["price_used_market"], "manual")
        self.assertEqual(self.client.get("/api/collection/stats/summary").json()["total_value"], 7.25)
        reset = self.client.put(f"/api/collection/{item_id}", json={"price_source": None})
        body = reset.json()
        self.assertIsNone(body["price_source"])
        self.assertIsNone(body["price_override"])
        self.assertTrue(body["needs_price_choice"])

    def test_sending_only_an_override_means_a_manual_price(self):
        item_id = self._add().json()["id"]
        body = self.client.put(f"/api/collection/{item_id}", json={"price_override": 4.0}).json()
        self.assertEqual(body["price_source"], "manual")
        self.assertEqual(body["price_override"], 4.0)

    def test_manual_without_a_price_is_rejected(self):
        self.assertEqual(self._add(price_source="manual").status_code, 422)
        item_id = self._add().json()["id"]
        self.assertEqual(self.client.put(f"/api/collection/{item_id}", json={"price_source": "manual"}).status_code, 422)

    def test_unknown_market_is_rejected(self):
        self.assertEqual(self._add(price_source="ebay").status_code, 422)

    def test_adding_with_a_choice_does_not_prompt(self):
        body = self._add(price_source="cardmarket").json()
        self.assertFalse(body["needs_price_choice"])

    def test_another_copy_merges_into_the_row_that_already_has_a_choice(self):
        first = self._add(price_source="tcgplayer").json()
        second = self._add().json()
        self.assertEqual(second["id"], first["id"])
        self.assertEqual(second["quantity"], 2)
        self.assertFalse(second["needs_price_choice"])

    def test_a_different_explicit_choice_gets_its_own_row(self):
        first = self._add(price_source="tcgplayer").json()
        second = self._add(price_source="cardmarket").json()
        self.assertNotEqual(first["id"], second["id"])

    def test_default_market_setting_changes_valuation_for_unpinned_cards(self):
        self._add()
        resp = self.client.put("/api/settings/", json={"price_market": "tcgplayer"})
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(self.client.get("/api/collection/stats/summary").json()["total_value"], 18.0)

    def test_market_settings_are_validated(self):
        self.assertEqual(self.client.put("/api/settings/", json={"price_market": "ebay"}).status_code, 422)
        self.assertEqual(self.client.put("/api/settings/", json={"price_divergence_pct": "2"}).status_code, 422)
        self.assertEqual(self.client.put("/api/settings/", json={"price_divergence_pct": "25"}).status_code, 200)


    def test_dashboard_lists_cards_still_needing_a_choice(self):
        from api.dashboard import router as dashboard_router
        self.client.app.include_router(dashboard_router, prefix="/api/dashboard")
        item_id = self._add().json()["id"]
        data = self.client.get("/api/dashboard/").json()
        self.assertEqual(data["price_choice_count"], 1)
        self.assertEqual(data["price_choices"][0]["collection_item_id"], item_id)
        self.client.put(f"/api/collection/{item_id}", json={"price_source": "cardmarket"})
        self.assertEqual(self.client.get("/api/dashboard/").json()["price_choice_count"], 0)


if __name__ == "__main__":
    unittest.main()
