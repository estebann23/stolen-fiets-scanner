"""Drop parts, locks, accessories, kids' bikes, and wanted (gezocht) ads."""

from __future__ import annotations

import re
from typing import Any

TITLE_DROP = (
    "gezocht",
    "gevraagd",
    "kinderfiets",
    "jongensfiets",
    "meisjesfiets",
    "loopfiets",
    "onderdeel",
    "onderdelen",
    "accessoire",
    "accessoires",
    "kettingslot",
    "fietsslot",
    "hangslot",
    "voorwiel",
    "achterwiel",
    "binnenband",
    "buitenband",
    "fietstas",
    "fietstassen",
    "helm",
    "trappers",
    "voorvork",
)

WANTED = re.compile(
    r"\b(gezocht|gevraagd|wil kopen|zoek)\b",
    re.IGNORECASE,
)

KIDS_SIZE = re.compile(
    r"\b(12|14|16|18)\s*(inch|\"|duim)\b",
    re.IGNORECASE,
)


def is_relevant(listing: dict[str, Any]) -> bool:
    title = str(listing.get("title", "")).lower()
    description = str(listing.get("description", "")).lower()
    blob = f"{title} {description}"
    if any(phrase in title for phrase in TITLE_DROP):
        return False
    if WANTED.search(blob):
        return False
    if KIDS_SIZE.search(blob):
        return False
    return True


def filter_listings(listings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [item for item in listings if is_relevant(item)]


def main() -> None:
    sample_keep = {
        "title": "Gazelle Orange C7 damesfiets",
        "description": "Nette stadsfiets met rek.",
    }
    sample_drop = {
        "title": "Gezocht: Gazelle",
        "description": "Wil kopen kinderfiets 16 inch",
    }
    print("keep", is_relevant(sample_keep))
    print("drop", is_relevant(sample_drop))


if __name__ == "__main__":
    main()
