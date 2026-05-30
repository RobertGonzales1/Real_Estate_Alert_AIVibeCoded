import requests
import json
import math
import time

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.redfin.com/",
}

# Redfin property type codes
PROPERTY_TYPES = {
    "condo": "2",
    "house": "1",
    "townhouse": "3",
    "any": "1,2,3,4,6",
}


def _parse_response(text):
    if text.startswith("{}&&"):
        text = text[4:]
    return json.loads(text)


def get_region(city, state):
    url = "https://www.redfin.com/stingray/do/location-autocomplete"
    params = {"location": f"{city}, {state}", "v": 2}
    resp = requests.get(url, params=params, headers=HEADERS, timeout=10)
    resp.raise_for_status()
    data = _parse_response(resp.text)

    for section in data.get("payload", {}).get("sections", []):
        for row in section.get("rows", []):
            # type "2" = city in Redfin's autocomplete
            if row.get("type") in ("2", 2):
                table_id = row.get("id", {}).get("tableId")
                if table_id:
                    return {"region_id": str(table_id), "region_type": "6"}

    # Fallback: hardcoded known IDs
    fallback = {
        "dallas_tx": {"region_id": "19673", "region_type": "6"},
        "las_vegas_nv": {"region_id": "30172", "region_type": "6"},
    }
    key = f"{city.lower().replace(' ', '_')}_{state.lower()}"
    return fallback.get(key)


def search(city, state, lat, lng, radius_miles, filters):
    region = get_region(city, state)
    if not region:
        raise ValueError(f"Could not resolve Redfin region for {city}, {state}")

    uipt = PROPERTY_TYPES.get(filters.get("property_type", "condo"), "2")

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
        "status": 9,  # for-sale only
    }
    if filters.get("min_sqft"):
        params["min_sqft"] = filters["min_sqft"]

    time.sleep(1)  # polite delay
    resp = requests.get(
        "https://www.redfin.com/stingray/api/gis",
        params=params,
        headers=HEADERS,
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

        listings.append({
            "id": f"redfin_{uid}",
            "price": price,
            "beds": home.get("beds", 0),
            "baths": home.get("baths", 0),
            "sqft": sqft,
            "address": f"{address}, {home_city}, {home_state} {home_zip}".strip(", "),
            "url": f"https://www.redfin.com{url_path}",
            "source": "Redfin",
        })
    return listings
