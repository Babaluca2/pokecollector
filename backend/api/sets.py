from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import case, text, func
from api.auth import get_current_user
from database import get_db
from models import Set, Card, CollectionItem, User
from services.card_state import card_state_summaries
from schemas import SetBase
from services import pokemon_api
from services.card_fallbacks import (
    apply_cross_language_fallbacks,
    build_missing_language_cards_for_set,
    missing_language_fallback_enabled,
)
from services.card_numbers import natural_card_number_key
from services.card_upsert import upsert_card
from services.card_visibility import get_configured_sync_languages, visible_any_card_filter, visible_set_filter
from services.digital_sets import digital_sets_enabled
from services.display_language import get_display_language, get_tcgdex_display_language
from services.tcgdex_languages import DEFAULT_TCGDEX_SYNC_LANGUAGES, has_lang_suffix, is_supported_tcgdex_language, normalize_tcgdex_language

router = APIRouter()


class MarkSetsSeenRequest(BaseModel):
    set_ids: Optional[List[str]] = None


def _refresh_sets(db: Session, display_lang: str):
    """Refresh sets from TCGdex API and store in DB.

    Each language version is stored as a separate row with a composite primary key
    (e.g. "sv1_de" and "sv1_en"). lang field is a supported TCGdex language code.
    """
    normalized_display_lang = normalize_tcgdex_language(display_lang)
    languages = [normalized_display_lang] if is_supported_tcgdex_language(normalized_display_lang) else list(DEFAULT_TCGDEX_SYNC_LANGUAGES)
    include_digital = digital_sets_enabled(db)
    sets_data = pokemon_api.get_all_sets(languages=languages, include_digital=include_digital)

    for set_data in sets_data:
        parsed = pokemon_api.parse_set_for_db(set_data)
        set_lang = set_data.get("_lang", "en")
        parsed["lang"] = set_lang

        existing = db.query(Set).filter(Set.id == parsed["id"]).first()
        if existing:
            for k, v in parsed.items():
                if k != "id" and v is not None:
                    setattr(existing, k, v)
        else:
            db.add(Set(**parsed))
    db.commit()


@router.get("/", response_model=List[SetBase])
def get_sets(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    refresh: bool = False,
    name_lang: Optional[str] = None,
    lang: Optional[str] = Query(None, description="Language filter: supported TCGdex language code or 'all'"),
):
    """Get all sets, optionally refresh from TCGdex API.

    lang: filter by set language code or 'all'.
    Sets are stored separately per language, with no 'both' entries.
    """
    if lang is None:
        lang_filter = get_tcgdex_display_language(db, current_user.id)
    else:
        requested_lang = normalize_tcgdex_language(lang or "all")
        lang_filter = requested_lang if is_supported_tcgdex_language(requested_lang) else "all"

    # Determine display language for API calls
    display_lang = lang_filter if lang_filter != "all" else get_tcgdex_display_language(db, current_user.id)

    # Always refresh if empty DB or explicitly requested
    if refresh or db.query(Set).count() == 0:
        try:
            _refresh_sets(db, display_lang)
        except Exception as e:
            if db.query(Set).count() == 0:
                raise HTTPException(status_code=500, detail=str(e))

    # Build query with optional lang filter. Globally disabled languages are
    # hidden unless this user has a collection/wishlist/binder card pinning that
    # localized set.
    query = db.query(Set).filter(visible_set_filter(db, current_user.id, lang_filter))
    sets = query.order_by(text("release_date DESC NULLS LAST")).all()

    # If an enabled language has no local rows yet, force a refresh. Disabled
    # languages should not be repopulated just because their filter was opened.
    if not sets and lang_filter != "all" and lang_filter in set(get_configured_sync_languages(db)):
        try:
            _refresh_sets(db, display_lang)
            query = db.query(Set).filter(visible_set_filter(db, current_user.id, lang_filter))
            sets = query.order_by(text("release_date DESC NULLS LAST")).all()
        except Exception:
            pass

    # Compute owned_count per set, grouped by (set_id, lang) so localized sets are counted separately
    owned_counts = (
        db.query(
            Card.set_id,
            CollectionItem.lang,
            func.count(func.distinct(CollectionItem.card_id)).label('cnt')
        )
        .join(CollectionItem, CollectionItem.card_id == Card.id)
        .filter(CollectionItem.user_id == current_user.id)
        .group_by(Card.set_id, CollectionItem.lang)
        .all()
    )
    owned_map = {(set_id, item_lang): cnt for set_id, item_lang, cnt in owned_counts}
    for set_obj in sets:
        tcg_id = set_obj.tcg_set_id or set_obj.id
        set_lang = set_obj.lang or 'en'
        set_obj.owned_count = owned_map.get((tcg_id, set_lang), 0)

    # Only a matching catalogue identity is a translation. Regional expansions
    # with different IDs must not be guessed from names, dates or abbreviations.
    name_language = normalize_tcgdex_language(
        name_lang if name_lang is not None else get_display_language(db, current_user.id)
    )
    identities = {item.tcg_set_id for item in sets if item.tcg_set_id}
    translations = {}
    if identities and is_supported_tcgdex_language(name_language):
        for item in db.query(Set).filter(Set.lang == name_language, Set.tcg_set_id.in_(identities)).all():
            translations.setdefault(item.tcg_set_id, []).append(item)
    result = []
    for item in sets:
        matches = translations.get(item.tcg_set_id, [])
        translated = matches[0] if len(matches) == 1 and matches[0].name.strip() else None
        result.append(SetBase.model_validate(item).model_copy(update={
            "translated_name": translated.name if translated else None,
            "translated_name_lang": name_language if translated else None,
        }))
    return result


@router.get("/new")
def get_new_sets(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get newly detected sets."""
    new_sets = db.query(Set).filter(Set.is_new == True, visible_set_filter(db, current_user.id, "all")).all()
    return new_sets


@router.post("/mark-seen")
def mark_sets_seen(
    body: Optional[MarkSetsSeenRequest] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mark all new sets as seen."""
    query = db.query(Set).filter(Set.is_new == True)
    if body and body.set_ids is not None:
        query = query.filter(Set.id.in_(body.set_ids))
    query.update({"is_new": False}, synchronize_session=False)
    db.commit()
    return {"message": "All new sets marked as seen"}


@router.post("/import-chs")
def import_chs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Admin: import Simplified Chinese sets and cards from PTCG-CHS-Datasets."""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    from services.chs_import import import_chs_cards

    try:
        return import_chs_cards(db)
    except Exception as exc:  # network or format problem
        raise HTTPException(status_code=502, detail=f"Import failed: {exc}") from exc


@router.post("/image-repair")
def repair_images(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Admin: fill missing artwork from the same card in another language."""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    from services.image_repair import repair_missing_images

    return repair_missing_images(db)


@router.get("/image-coverage")
def get_image_coverage(
    only_missing: bool = Query(default=True, description="List only sets that have missing images"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Audit artwork coverage per language and per set (cards without any image)."""
    has_image = (Card.images_small.isnot(None)) & (Card.images_small != "")
    has_custom = (Card.custom_image_url.isnot(None)) & (Card.custom_image_url != "")
    rows = (
        db.query(
            Card.lang,
            Card.set_id,
            func.count(Card.id),
            func.sum(case((has_image | has_custom, 0), else_=1)),
        )
        .filter(visible_any_card_filter(db, current_user.id, "all"))
        .group_by(Card.lang, Card.set_id)
        .all()
    )
    languages: dict[str, dict] = {}
    sets = []
    for lang, set_id, total, missing in rows:
        lang = lang or "en"
        missing = int(missing or 0)
        entry = languages.setdefault(lang, {"lang": lang, "total": 0, "missing": 0})
        entry["total"] += int(total or 0)
        entry["missing"] += missing
        if missing or not only_missing:
            sets.append({"lang": lang, "set_id": set_id, "total": int(total or 0), "missing": missing})
    for entry in languages.values():
        entry["missing_pct"] = round(100 * entry["missing"] / entry["total"], 1) if entry["total"] else 0
    sets.sort(key=lambda row: (-row["missing"], row["lang"], row["set_id"] or ""))
    return {"languages": sorted(languages.values(), key=lambda row: row["lang"]), "sets": sets[:200]}


@router.get("/{set_id}", response_model=SetBase)
def get_set(
    set_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a single set by composite DB key, such as 'sv1_en' or 'sv1_zh-tw'."""
    set_obj = db.query(Set).filter(Set.id == set_id, visible_set_filter(db, current_user.id, "all")).first()
    if not set_obj:
        raise HTTPException(status_code=404, detail="Set not found")
    return set_obj


@router.get("/{set_id}/checklist")
def get_set_checklist(
    set_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get set checklist - cards with ownership status.

    set_id is the composite DB key (e.g. 'sv1_de').
    Missing local cards are fetched from TCGdex and may use sibling-language
    fallback rows until native language data exists.
    """
    set_obj = db.query(Set).filter(Set.id == set_id, visible_set_filter(db, current_user.id, "all")).first()
    if not set_obj:
        raise HTTPException(status_code=404, detail="Set not found")

    # Use the original TCGdex set ID for card lookups
    tcg_id = set_obj.tcg_set_id or set_obj.id
    set_lang = set_obj.lang or "en"
    fallback_enabled = missing_language_fallback_enabled(db)

    def query_set_cards():
        query = db.query(Card).filter(
            Card.set_id == tcg_id,
            Card.lang == set_lang,
            Card.is_custom == False,
        )
        if not fallback_enabled:
            query = query.filter(Card.data_source_lang.is_(None))
        return query.all()

    # Query DB for cards matching both set_id and lang
    cards = query_set_cards()

    # If no lang-filtered cards are found, only repair legacy cards that do not
    # already have an explicit language in their DB id. Do not relabel sibling
    # rows like me04-001_en as German cards.
    if not cards:
        legacy_cards = db.query(Card).filter(
            Card.set_id == tcg_id,
            Card.is_custom == False,
        ).all()
        repairable_cards = [
            card for card in legacy_cards
            if not has_lang_suffix(card.id)
        ]
        if repairable_cards:
            for card in repairable_cards:
                card.lang = set_lang
            db.commit()
            cards = repairable_cards

    # If still no cards, fetch native cards from TCGdex and cache them.
    if not cards:
        try:
            set_data = pokemon_api.get_set_cards(tcg_id, lang=set_lang)
            for card_data in set_data.get("cards", []):
                parsed = pokemon_api.parse_card_for_db(card_data, default_set_id=tcg_id, lang=set_lang)
                parsed = apply_cross_language_fallbacks(db, parsed)
                upsert_card(db, parsed, partial=True)
            db.commit()
            cards = query_set_cards()
        except Exception:
            db.rollback()

    # Some new sets exist as localized set metadata before localized card data
    # exists. When cross-language fallback is enabled, fill any missing target
    # rows from the sibling language. Do this even if one fallback row already
    # exists, otherwise adding a single card prevents the rest of the set from
    # appearing after fallback is turned on.
    set_total = set_obj.total or 0
    if fallback_enabled and (not cards or (set_total and len(cards) < set_total)):
        try:
            for parsed in build_missing_language_cards_for_set(db, tcg_id, set_lang, expected_total=set_total):
                upsert_card(db, parsed, partial=True)
            db.commit()
        except Exception:
            db.rollback()
        cards = query_set_cards()

    cards.sort(key=lambda card: natural_card_number_key(card.number))

    # Get exact owned collection rows so the UI can safely remove/decrement the
    # right variant/condition instead of treating ownership as a single boolean.
    collection_items = db.query(CollectionItem).filter(
        CollectionItem.user_id == current_user.id,
        CollectionItem.card_id.in_([c.id for c in cards])
    ).all()
    owned_by_card: dict[str, list[CollectionItem]] = {}
    for item in collection_items:
        owned_by_card.setdefault(item.card_id, []).append(item)
    summaries = card_state_summaries(
        db,
        current_user.id,
        [card.id for card in cards],
        collection_items=collection_items,
    )
    owned_count = sum(1 for summary in summaries.values() if summary["owned"])
    total_count = len(cards)

    checklist = []
    for card in cards:
        owned_items = owned_by_card.get(card.id, [])
        summary = summaries[card.id]
        qty = summary["owned_quantity"]

        checklist.append({
            "id": card.id,
            "name": card.name,
            "tcg_card_id": card.tcg_card_id,
            "set_id": card.set_id,
            "set_ref": {
                "id": set_obj.id,
                "tcg_set_id": set_obj.tcg_set_id,
                "name": set_obj.name,
                "abbreviation": set_obj.abbreviation,
                "lang": set_obj.lang,
            },
            "number": card.number,
            "rarity": card.rarity,
            "images_small": card.images_small,
            "images_large": card.images_large,
            "image_source_lang": getattr(card, "image_source_lang", None),
            "data_source_lang": getattr(card, "data_source_lang", None),
            "price_source_lang": getattr(card, "price_source_lang", None),
            "owned": summary["owned"],
            "owned_quantity": qty,
            "owned_variants": summary["owned_variants"],
            "wishlisted": summary["wishlisted"],
            "quantity": qty,
            "owned_items": [
                {
                    "id": item.id,
                    "quantity": item.quantity,
                    "condition": item.condition,
                    "variant": item.variant,
                    "printing_details": [tag.name for tag in item.printing_detail_tags],
                    "lang": item.lang,
                    "purchase_price": item.purchase_price,
                }
                for item in owned_items
            ],
            "price_market": card.price_market,
            "price_low": card.price_low,
            "price_trend": card.price_trend,
            "price_avg1": card.price_avg1,
            "price_avg7": card.price_avg7,
            "price_avg30": card.price_avg30,
            "price_market_holo": card.price_market_holo,
            "price_low_holo": card.price_low_holo,
            "price_trend_holo": card.price_trend_holo,
            "price_avg1_holo": card.price_avg1_holo,
            "price_avg7_holo": card.price_avg7_holo,
            "price_avg30_holo": card.price_avg30_holo,
            "dex_ids": getattr(card, "dex_ids", None),
            "pokedex_entry_ids": getattr(card, "pokedex_entry_ids", None),
            "cardmarket_products": getattr(card, "cardmarket_products", None),
            "variants_normal": card.variants_normal,
            "variants_reverse": card.variants_reverse,
            "variants_holo": card.variants_holo,
            "variants_first_edition": card.variants_first_edition,
            "lang": card.lang or "en",
        })

    return {
        "set": {
            "id": set_obj.id,
            "name": set_obj.name,
            "series": set_obj.series,
            "total": set_obj.total,
            "images_symbol": set_obj.images_symbol,
            "images_logo": set_obj.images_logo,
            "lang": set_obj.lang or "en",
        },
        "cards": checklist,
        "owned_count": owned_count,
        "total_count": total_count,
        "progress": round((owned_count / total_count * 100) if total_count > 0 else 0, 1),
    }
