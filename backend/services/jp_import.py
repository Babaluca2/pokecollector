"""Fill Japanese card artwork (and missing sets) from the community PKMNDB dataset.

TCGdex Japanese cards often lack images. For every PKMNDB Japanese set that
matches an existing Japanese set (same set code), missing images are filled by
card number. Sets TCGdex does not know are created from the dataset. Nothing is
bundled: data is downloaded at the admin's request and images are fetched on
demand into the local image cache.
"""

from __future__ import annotations

import json
import re
from urllib.parse import urlparse

import httpx
from sqlalchemy import func
from sqlalchemy.orm import Session

from models import Card, Set
from services.card_upsert import upsert_card

LANG = "ja"
TRUSTED_IMAGE_HOSTS = {"pub-54a82c9e988c459da62f95d0bd9c78d9.r2.dev", "raw.githubusercontent.com"}
BASE = "https://raw.githubusercontent.com/ImLogueybear/PKMNDB/main/dist/"


def fetch_dataset() -> tuple[list[dict], list[dict]]:
    sets = httpx.get(BASE + "sets.json", timeout=120, follow_redirects=True)
    sets.raise_for_status()
    cards = httpx.get(BASE + "cards.jsonl", timeout=300, follow_redirects=True)
    cards.raise_for_status()
    rows = [json.loads(line) for line in cards.text.splitlines() if line.strip()]
    return sets.json(), rows


def _trusted(url) -> str | None:
    """Only keep image URLs on the dataset's own hosts (the server fetches them)."""
    parsed = urlparse(url) if isinstance(url, str) else None
    if parsed and parsed.scheme == "https" and parsed.hostname in TRUSTED_IMAGE_HOSTS and not parsed.port:
        return url
    return None


def _num(value) -> int | None:
    match = re.search(r"\d+", str(value or ""))
    return int(match.group()) if match else None


def import_jp_cards(db: Session, dataset: tuple[list[dict], list[dict]] | None = None) -> dict:
    sets, cards = dataset if dataset is not None else fetch_dataset()
    by_set: dict[int, list[dict]] = {}
    for card in cards:
        if card.get("language") != LANG or not _trusted(card.get("image_url")):
            continue
        by_set.setdefault(card["set_id"], []).append(card)

    filled = created_sets = created_cards = 0
    for source in sets:
        if source.get("language") != LANG or not source.get("released"):
            continue
        rows = by_set.get(source["id"]) or []
        if not rows:
            continue
        code = (source.get("code") or "").lower()
        existing = None
        if code:
            existing = (
                db.query(Set)
                .filter(Set.lang == LANG, func.lower(Set.tcg_set_id) == code)
                .first()
            )
        if existing is not None:
            by_number = {_num(r["number"]): r for r in rows if _num(r["number"]) is not None}
            for card in db.query(Card).filter(Card.set_id == existing.tcg_set_id, Card.lang == LANG):
                if card.images_small or card.custom_image_url:
                    continue
                match = by_number.get(_num(card.number))
                if match:
                    card.images_small = card.images_large = match["image_url"]
                    card.image_source_lang = LANG
                    filled += 1
            db.commit()
            continue

        set_id = f"pkmndb-{source['id']}"
        db_id = f"{set_id}_{LANG}"
        row = db.query(Set).filter(Set.id == db_id).first()
        if row is None:
            row = Set(id=db_id, tcg_set_id=set_id, lang=LANG, name=source["name"])
            db.add(row)
        row.name = source["name"]
        row.series = source.get("series")
        row.release_date = source.get("release_date")
        row.total = row.printed_total = len(rows)
        row.abbreviation = source.get("code")
        row.images_logo = _trusted(source.get("logo_url") or source.get("logo_fallback_url"))
        row.images_symbol = _trusted(source.get("symbol_url") or source.get("symbol_fallback_url"))
        created_sets += 1
        for card in rows:
            card_id = f"pkmndb-{card['id']}"
            upsert_card(db, {
                "id": f"{card_id}_{LANG}",
                "tcg_card_id": card_id,
                "name": card["name"],
                "set_id": set_id,
                "number": card.get("number"),
                "rarity": card.get("rarity"),
                "images_small": card["image_url"],
                "images_large": card["image_url"],
                "lang": LANG,
            })
            created_cards += 1
        db.commit()
    return {"filled": filled, "sets": created_sets, "cards": created_cards}
