"""
Redfin scraper using a persistent session with cookies to reduce bot detection.
Hardcoded region IDs are used as fallback to avoid the autocomplete call
which is most likely to get blocked.
"""

import requests
import json
import time

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

API_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.redfin.com/",
    "X-Requested-With": "XMLHttpRequest",
}

# Hardcoded region IDs — avoids the autocomplete call that gets blocked
KNOWN_REGIONS = {
    "dallas_tx":     {"region_id": "19673", "region_type": "6"},
    "las_vegas_nv":  {"region_id": "30172", "region_type": "6"},
}

PROPERTY_TYPES = {
    "condo":     "2",
    "house":     "1",
    "townhouse": "3",
    "any":       "1,2,3,4,6",
}


def _parse_response(text):
    if text.startswith("{}&&"):
        text = text[4:]
    return json.loads(text)


def _make_session(city, state):
    """Warm up a session with real browser cookies by visiting the city page first."""
    session = requests.Session()
    city_slug = city.replace(" ", "-")
    try:
        session.get(
            f"https://www.redfin.com/{state}/{city_slug}",
            headers=BROWSER_HEADERS,
            timeout=10,
        )
        time.sleep(1.5)
    except Exception:
        pass  # best-effort warm-up
    return session


def search(city, state, lat, lng, radius_miles, filters):
    key = f"{city.lower().replace(' ', '_')}_{state.lower()}"
    region = KNOWN_REGIONS.get(key)
    if not region:
        raise ValueError(
            f"No hardcoded Redfin region for {city}, {state}. "
            "Add it to KNOWN_REGIONS in scrapers/redfin.py"
        )

    uipt = PROPERTY_TYPES.get(filters.get("property_type", "condo"), "2")
    listing_types = "1,4,8" if filters.get("include_foreclosures") else "1"

    params = {
        "al": 1,
        "min_beds": filters["min_beds"],
        "min_baths": filters["min_baths"],
        "max_price": filters["max_price"],
        "uipt": uipt,
        "v": 8,
        "region_id": region["region_id"],
        "region_type": region["region_type"],
        "sf": "1,2,3,5,6,7",
        "start": 0,
        "count": 350,
        "status": 9,
        "listing_type": listing_types,
    }
    if filters.get("min_sqft"):
        params["min_sqft"] = filters["min_sqft"]

    session = _make_session(city, state)
    resp = session.get(
        "https://www.redfin.com/stingray/api/gis",
        params=params,
        headers=API_HEADERS,
        timeout=15,
    )
    resp.raise_for_status()
    data = _parse_response(resp.text)
    return _parse_listings(data, city, state)


def _parse_listings(data, city, state):
    listings = []
    homes = data.get("payload", {}).get("homes", [])
    for home in homes:
        mls_id = (home.get("mlsId") or {}).get("value")
        listing_id = (home.get("listingId") or {}).get("value")
        uid = mls_id or listing_id or home.get("propertyId")
        if not uid:
            continue

        price = (home.get("price") or {}).get("value", 0)
        sqft = (home.get("sqFt") or {}).get("value", 0)
        address = (home.get("streetLine") or {}).get("value", "")
        home_city = home.get("city", city)
        home_state = home.get("state", state)
        home_zip = home.get("zip", "")
        url_path = home.get("url", "")

        listing_type_code = home.get("listingType", 1)
        badge = None
        if listing_type_code == 4:
            badge = "Foreclosure"
        elif listing_type_code == 8:
            badge = "Auction"

        entry = {
            "id":      f"redfin_{uid}",
            "price":   price,
            "beds":    home.get("beds", 0),
            "baths":   home.get("baths", 0),
            "sqft":    sqft,
            "address": f"{address}, {home_city}, {home_state} {home_zip}".strip(", "),
            "url":     f"https://www.redfin.com{url_path}",
            "source":  "Redfin",
        }
        if badge:
            entry["listing_type"] = badge
        listings.append(entry)
    return listings
