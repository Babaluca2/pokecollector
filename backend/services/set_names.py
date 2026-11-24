"""English display names for sets that are not in English or French.

The table in data/set_names_en.json maps set codes to official English names
(set names only, no artwork). Lookup order for a set in language L:
the English set with the same TCGdex id, then the table for L, then the
Japanese table (TCGdex Traditional Chinese and Korean sets reuse Japanese
codes). When nothing matches, the native name is kept.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from models import Set

KEEP_NATIVE = {"en", "fr"}
_TABLE = Path(__file__).resolve().parents[1] / "data" / "set_names_en.json"


@lru_cache(maxsize=1)
def _table() -> dict[str, dict[str, str]]:
    try:
        return json.loads(_TABLE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def english_set_name(tcg_set_id: Optional[str], lang: Optional[str], native: str, *, english_by_id: Optional[dict] = None) -> str:
    lang = (lang or "en").lower()
    if lang in KEEP_NATIVE or not tcg_set_id:
        return native
    key = tcg_set_id.lower()
    if key.startswith("chs-"):  # sets created by the Chinese import
        key = key[4:]
    if english_by_id and english_by_id.get(tcg_set_id):
        return english_by_id[tcg_set_id]
    table = _table()
    for source in (lang, "ja"):
        name = table.get(source, {}).get(key)
        if name:
            return name
    return native


def localize_set_names(db: Session) -> dict:
    """Rewrite names of all non-EN/FR sets to English, keeping the original in native_name."""
    english = {
        row[0]: row[1]
        for row in db.query(Set.tcg_set_id, Set.name).filter(Set.lang == "en").all()
        if row[0] and row[1]
    }
    changed = 0
    for row in db.query(Set).filter(Set.lang.notin_(KEEP_NATIVE)).all():
        native = row.native_name or row.name
        name = english_set_name(row.tcg_set_id, row.lang, native, english_by_id=english)
        if name != native:
            row.native_name = native
            row.name = name
            changed += 1
    db.commit()
    return {"renamed": changed}
