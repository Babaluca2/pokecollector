"""Keep one automatic collection binder per owned set up to date.

Every time a card is added to the collection, the matching set binder is created
on demand and the owned copy is placed in it. This is best-effort: a failure
here must never break the collection add that triggered it.
"""

from __future__ import annotations

import datetime
import logging

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from models import Binder, BinderCard, Card, CollectionItem, Set, User

logger = logging.getLogger(__name__)


def _set_for_card(db: Session, card: Card) -> Set | None:
    if not card or not card.set_id:
        return None
    lang = card.lang or "en"
    return (
        db.query(Set)
        .filter(or_(Set.tcg_set_id == card.set_id, Set.id == card.set_id), Set.lang == lang)
        .order_by(Set.id.asc())
        .first()
    )


def _used_elsewhere(db: Session, item_id: int, binder_id: int) -> int:
    used = (
        db.query(func.coalesce(func.sum(BinderCard.required_quantity), 0))
        .filter(BinderCard.collection_item_id == item_id, BinderCard.binder_id != binder_id)
        .scalar()
    )
    return int(used or 0)


def sync_auto_binder(db: Session, user: User, item: CollectionItem) -> None:
    """Create or update the set binder entry for one collection item."""
    try:
        card = item.card or db.query(Card).filter(Card.id == item.card_id).first()
        set_obj = _set_for_card(db, card)
        if set_obj is None or int(item.quantity or 0) < 1:
            return
        binder = (
            db.query(Binder)
            .filter(
                Binder.user_id == user.id,
                Binder.auto_owned_set_id == set_obj.id,
                or_(Binder.binder_type == "collection", Binder.binder_type.is_(None)),
            )
            .order_by(Binder.id.asc())
            .first()
        )
        if binder is None:
            binder = Binder(
                name=f"{set_obj.name or set_obj.id} ({(set_obj.lang or 'en').upper()})",
                user_id=user.id,
                binder_type="collection",
                color="#B79B63",
                auto_owned_set_id=set_obj.id,
                created_at=datetime.datetime.utcnow(),
            )
            db.add(binder)
            db.flush()
        available = max(int(item.quantity or 0) - _used_elsewhere(db, item.id, binder.id), 0)
        if available < 1:
            db.rollback()
            return
        entry = (
            db.query(BinderCard)
            .filter(BinderCard.binder_id == binder.id, BinderCard.collection_item_id == item.id)
            .first()
        )
        if entry is None:
            db.add(BinderCard(
                binder_id=binder.id,
                card_id=item.card_id,
                collection_item_id=item.id,
                required_quantity=min(available, 99),
                added_at=datetime.datetime.utcnow(),
            ))
        else:
            entry.required_quantity = min(available, 99)
        db.commit()
    except Exception:  # best-effort, never break the add
        db.rollback()
        logger.exception("Automatic set binder update failed")
