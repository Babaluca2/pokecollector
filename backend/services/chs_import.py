"""Import Simplified Chinese cards from the community PTCG-CHS-Datasets repo.

TCGdex has no card-level data for Simplified Chinese, so this adds the sets and
cards ourselves. The dataset's README allows non-commercial use and forbids
redistribution, so nothing is bundled: the JSON is downloaded at the admin's
request and card images are fetched on demand into the local image cache.
"""

from __future__ import annotations

import httpx
from sqlalchemy.orm import Session

from models import Set
from services.card_upsert import upsert_card
from services.set_names import english_set_name

LANG = "zh-cn"
DATASET_BASE = "https://raw.githubusercontent.com/duanxr/PTCG-CHS-Datasets/main/"
INFOS_URL = DATASET_BASE + "ptcg_chs_infos.json"


def fetch_infos() -> dict:
    resp = httpx.get(INFOS_URL, timeout=120, follow_redirects=True)
    resp.raise_for_status()
    return resp.json()


def _image_url(path: str | None) -> str | None:
    return DATASET_BASE + path.lstrip("/") if path else None


def _card_row(collection: dict, card: dict, set_id: str) -> dict:
    details = card.get("details") or {}
    artists = details.get("illustratorName") or []
    if isinstance(artists, str):
        artists = [artists]
    url = _image_url(card.get("image"))
    card_id = f"chs-{card['id']}"
    return {
        "id": f"{card_id}_{LANG}",
        "tcg_card_id": card_id,
        "name": card.get("name") or details.get("cardName") or card_id,
        "set_id": set_id,
        "number": details.get("collectionNumber"),
        "rarity": details.get("rarityText"),
        "supertype": details.get("cardTypeText"),
        "hp": str(details["hp"]) if details.get("hp") else None,
        "artist": ", ".join(artists) or None,
        "stage": details.get("evolveText"),
        "regulation_mark": details.get("regulationMarkText"),
        "card_effect": details.get("ruleText"),
        "images_small": url,
        "images_large": url,
        "lang": LANG,
    }


def import_chs_cards(db: Session, infos: dict | None = None) -> dict:
    infos = infos if infos is not None else fetch_infos()
    sets = cards = 0
    for collection in infos.get("collections", []):
        rows = collection.get("cards") or []
        code = collection.get("commodityCode")
        if not rows or not code:
            continue
        set_id = f"chs-{code}"
        db_id = f"{set_id}_{LANG}"
        row = db.query(Set).filter(Set.id == db_id).first()
        if row is None:
            row = Set(id=db_id, tcg_set_id=set_id, lang=LANG, name=collection.get("name") or code)
            db.add(row)
        native = collection.get("name") or code
        row.name = english_set_name(code, LANG, native)
        row.native_name = native if row.name != native else None
        row.series = collection.get("seriesText")
        row.release_date = collection.get("salesDate")
        row.total = row.printed_total = len(rows)
        row.abbreviation = code
        row.images_logo = _image_url(collection.get("image"))
        sets += 1
        for card in rows:
            upsert_card(db, _card_row(collection, card, set_id))
            cards += 1
        db.commit()
    return {"sets": sets, "cards": cards}
