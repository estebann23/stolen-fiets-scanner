"""Synthetic second-hand bike ads for local demo (not scraped from Marktplaats)."""

from __future__ import annotations

import hashlib
import random
from datetime import datetime, timedelta, timezone
from typing import Any

# Public city coordinates (approx. centroids), used for distance filters later.
CITIES: list[tuple[str, float, float]] = [
    ("Amsterdam", 52.3676, 4.9041),
    ("Haarlem", 52.3874, 4.6462),
    ("Almere", 52.3508, 5.2647),
    ("Utrecht", 52.0907, 5.1214),
    ("Amersfoort", 52.1561, 5.3878),
    ("Leiden", 52.1601, 4.4970),
    ("Den Haag", 52.0705, 4.3007),
    ("Delft", 52.0116, 4.3571),
    ("Rotterdam", 51.9244, 4.4777),
    ("Zaandam", 52.4389, 4.8250),
    ("Hilversum", 52.2292, 5.1669),
    ("Purmerend", 52.5050, 4.9597),
]

BRAND_MODELS: dict[str, list[str]] = {
    "Gazelle": ["Orange C7", "Paris C7", "Chamonix C7", "Medeo T9", "Ultimate C8"],
    "Batavus": ["Mambo", "Finez", "Dinsdag Exclusive", "Packd E-go", "Quip Extra"],
    "Cortina": ["U1", "Foss", "E-U4", "Common", "Speed"],
    "VanMoof": ["S3", "X3", "S5", "A5"],
    "Sparta": ["a-Lane Energy", "Regular", "d-Burst", "Mojo"],
    "Cube": ["Nature", "Touring", "Kathmandu Hybrid", "Aim Race", "Stereo"],
    "Trek": ["FX 2", "District 4", "Domane AL 2", "Marlin 5", "Checkpoint ALR"],
    "Giant": ["Escape 3", "ToughRoad", "Explore E+", "Talon 2", "Contend AR 3"],
}

COLORS = ["black", "grey", "blue", "green", "white", "red", "silver", "anthracite"]
COLOR_NL = {
    "black": "zwart",
    "grey": "grijs",
    "blue": "blauw",
    "green": "groen",
    "white": "wit",
    "red": "rood",
    "silver": "zilver",
    "anthracite": "antraciet",
}
FRAMES = ["low-step", "diamond", "mixte"]
ACCESSORIES = [
    "front basket",
    "rear rack",
    "frame lock",
    "lights",
    "mudguards",
    "double kickstand",
    "child seat mount",
]
MARKS = [
    "white sticker on down tube",
    "scratch on top tube",
    "faded decal on chainstay",
    "dent above rear dropout",
    "blue grip tape remainder",
    "engraved initials on seat tube",
]

TYPE_META = {
    "e-bike": {"bike_type": "e-bike", "electric": True, "price": (1400, 3800), "wheel": "28"},
    "racefiets": {"bike_type": "race", "electric": False, "price": (450, 2200), "wheel": "28"},
    "moederfiets": {"bike_type": "city", "electric": False, "price": (180, 750), "wheel": "28"},
    "bakfiets": {"bike_type": "cargo", "electric": True, "price": (1800, 5200), "wheel": "26"},
    "stadsfiets": {"bike_type": "city", "electric": False, "price": (120, 650), "wheel": "28"},
    "mountainbike": {"bike_type": "mtb", "electric": False, "price": (280, 1900), "wheel": "29"},
}


def _seller_id(seed: str) -> str:
    digest = hashlib.sha256(seed.encode()).hexdigest()[:8]
    return f"s_{digest}"


def build_demo_listings(
    brands: list[str],
    types: list[str],
    rng: random.Random,
    n_keep: int = 250,
    n_junk: int = 40,
) -> list[dict[str, Any]]:
    listings: list[dict[str, Any]] = []
    now = datetime.now(timezone.utc).replace(microsecond=0)
    combo = 0
    while len(listings) < n_keep:
        brand = brands[combo % len(brands)]
        bike_type_query = types[combo % len(types)]
        combo += 1
        meta = TYPE_META[bike_type_query]
        model = rng.choice(BRAND_MODELS[brand])
        color = rng.choice(COLORS)
        city, lat, lon = rng.choice(CITIES)
        lat += rng.uniform(-0.04, 0.04)
        lon += rng.uniform(-0.04, 0.04)
        price = round(rng.uniform(*meta["price"]), 2)
        days_ago = rng.randint(0, 55)
        posted = now - timedelta(days=days_ago, hours=rng.randint(0, 23))
        frame = rng.choice(FRAMES)
        acc = rng.sample(ACCESSORIES, k=rng.randint(2, 4))
        marks = rng.sample(MARKS, k=rng.randint(0, 2))
        serial = None
        if rng.random() < 0.18:
            serial = f"GZ{rng.randint(10_000_000, 99_999_999)}"
        idx = len(listings) + 1
        listing_id = f"m_{idx:04d}"
        color_nl = COLOR_NL[color]
        title = f"{brand} {model} {bike_type_query}"
        desc_parts = [
            f"Nette {bike_type_query} van {brand}, model {model}.",
            f"Kleur {color_nl}, frametype {frame}, wielmaat {meta['wheel']} inch.",
            "Komt uit privébezit, rookvrij gestald.",
            f"Accessoires: {', '.join(acc)}.",
        ]
        if marks:
            desc_parts.append("Bijzonderheden: " + "; ".join(marks) + ".")
        if serial:
            desc_parts.append(f"Framenummer {serial}.")
        if rng.random() < 0.12:
            desc_parts.append("Met bon en fietssleutel.")
        listings.append(
            {
                "id": listing_id,
                "title": title,
                "description": " ".join(desc_parts),
                "price": price,
                "location": city,
                "lat": round(lat, 6),
                "lon": round(lon, 6),
                "posted_at": posted.isoformat(),
                "seller_id": _seller_id(listing_id),
                "url": f"https://example.invalid/listing/{listing_id}",
                "brand": brand,
                "model": model,
                "query_type": bike_type_query,
                "color": color,
                "frame_shape": frame,
                "wheel_size": meta["wheel"],
                "is_electric": meta["electric"],
                "accessories": acc,
                "marks": marks,
                "serial": serial,
            }
        )

    junk_titles = [
        ("AXA Defender kettingslot nieuw", "Fietsslot met 2 sleutels, nooit gebruikt."),
        ("Gezocht: Gazelle Orange dames", "Wil kopen stadsfiets, budget 300 euro."),
        ("Kinderfiets 16 inch meisjes", "Roze kinderfiets met zijwieltjes."),
        ("Voorwiel 28 inch met band", "Los voorwiel, geen fiets."),
        ("Fietstassen set dubbel", "Accessoires voor bakfiets, tassen only."),
        ("Batavus onderdelen partij", "Voorvork en zadel, geen complete fiets."),
        ("Loopfiets hout 2 jaar", "Peuter loopfiets, geen stadsfiets."),
        ("Helm ABUS maat M", "Fietshelm, geen fiets."),
        ("Gevraagd VanMoof S3", "Zoek elektrische fiets, graag PM."),
        ("Binnenband 28 inch 4 stuks", "Onderdelen, geen complete bike."),
    ]
    for i in range(n_junk):
        title, desc = junk_titles[i % len(junk_titles)]
        city, lat, lon = rng.choice(CITIES)
        listings.append(
            {
                "id": f"junk_{i:03d}",
                "title": title,
                "description": desc,
                "price": round(rng.uniform(5, 80), 2),
                "location": city,
                "lat": lat,
                "lon": lon,
                "posted_at": now.isoformat(),
                "seller_id": _seller_id(f"junk_{i}"),
                "url": f"https://example.invalid/listing/junk_{i:03d}",
            }
        )
    rng.shuffle(listings)
    return listings
