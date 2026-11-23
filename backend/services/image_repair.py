"""Fill missing card artwork from the same card in another language."""

from __future__ import annotations

from sqlalchemy import or_
from sqlalchemy.orm import Session

from models import Card

LANG_PREFERENCE = ("en", "fr", "ja", "ko", "zh-tw", "zh-cn", "de")


def _has_image(card: Card) -> bool:
    return bool(card.images_small or card.images_large or card.custom_image_url)


def repair_missing_images(db: Session, *, limit: int = 5000) -> dict:
    """Copy artwork from a sibling-language card (same TCGdex card id).

    The copied image is tagged with ``image_source_lang`` so the UI can show
    that it comes from another language, and a native sync replaces it later.
    """
    missing = (
        db.query(Card)
        .filter(
            Card.is_custom == False,  # noqa: E712
            or_(Card.images_small.is_(None), Card.images_small == ""),
            or_(Card.custom_image_url.is_(None), Card.custom_image_url == ""),
            Card.tcg_card_id.isnot(None),
        )
        .limit(limit)
        .all()
    )
    repaired = 0
    for card in missing:
        siblings = (
            db.query(Card)
            .filter(
                Card.tcg_card_id == card.tcg_card_id,
                Card.id != card.id,
                Card.images_small.isnot(None),
                Card.images_small != "",
            )
            .all()
        )
        if not siblings:
            continue
        siblings.sort(key=lambda c: LANG_PREFERENCE.index(c.lang) if c.lang in LANG_PREFERENCE else len(LANG_PREFERENCE))
        source = siblings[0]
        card.images_small = source.images_small
        card.images_large = source.images_large or source.images_small
        card.image_source_lang = source.lang
        repaired += 1
    db.commit()
    return {"checked": len(missing), "repaired": repaired, "still_missing": len(missing) - repaired}
