import unittest

try:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from api.auth import get_current_user
    from api.sets import router as sets_router
    from database import get_db
    DEPS = True
except Exception:  # pragma: no cover
    DEPS = False


@unittest.skipUnless(DEPS, "FastAPI/httpx are not installed")
class ImageCoverageTests(unittest.TestCase):
    def test_reports_missing_artwork_per_language_and_set(self):
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from sqlalchemy.pool import StaticPool
        from database import Base
        from models import Card, Set, Setting, User

        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(engine)
        db = sessionmaker(bind=engine)()
        user = User(username="u", hashed_password="x")
        db.add_all([
            user,
            Setting(key="tcgdex_sync_languages", value="en,ko"),
            Set(id="a_en", tcg_set_id="a", name="A", lang="en"),
            Set(id="b_ko", tcg_set_id="b", name="B", lang="ko"),
            Card(id="a-1_en", tcg_card_id="a-1", name="x", set_id="a", lang="en", images_small="http://i/1.png"),
            Card(id="b-1_ko", tcg_card_id="b-1", name="y", set_id="b", lang="ko"),
            Card(id="b-2_ko", tcg_card_id="b-2", name="z", set_id="b", lang="ko", custom_image_url="http://i/c.png"),
        ])
        db.commit()
        app = FastAPI()
        app.include_router(sets_router, prefix="/api/sets")
        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db] = lambda: db
        body = TestClient(app).get("/api/sets/image-coverage").json()
        by_lang = {row["lang"]: row for row in body["languages"]}
        self.assertEqual(by_lang["en"]["missing"], 0)
        self.assertEqual(by_lang["ko"]["total"], 2)
        self.assertEqual(by_lang["ko"]["missing"], 1)
        self.assertEqual(by_lang["ko"]["missing_pct"], 50.0)
        self.assertEqual(body["sets"], [{"lang": "ko", "set_id": "b", "total": 2, "missing": 1}])
        db.close()



@unittest.skipUnless(DEPS, "FastAPI/httpx are not installed")
class ImageRepairTests(unittest.TestCase):
    def test_copies_artwork_from_a_sibling_language(self):
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from sqlalchemy.pool import StaticPool
        from database import Base
        from models import Card
        from services.image_repair import repair_missing_images

        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(engine)
        db = sessionmaker(bind=engine)()
        db.add_all([
            Card(id="x-1_en", tcg_card_id="x-1", name="n", set_id="x", lang="en", images_small="http://i/en.png"),
            Card(id="x-1_ko", tcg_card_id="x-1", name="n", set_id="x", lang="ko"),
            Card(id="y-1_ko", tcg_card_id="y-1", name="m", set_id="y", lang="ko"),
        ])
        db.commit()
        result = repair_missing_images(db)
        self.assertEqual(result, {"checked": 2, "repaired": 1, "still_missing": 1})
        ko = db.query(Card).filter(Card.id == "x-1_ko").one()
        self.assertEqual(ko.images_small, "http://i/en.png")
        self.assertEqual(ko.image_source_lang, "en")
        db.close()


if __name__ == "__main__":
    unittest.main()
