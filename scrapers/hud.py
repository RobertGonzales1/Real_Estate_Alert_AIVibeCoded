"""
HUD Homestore scraper — FHA-insured foreclosures sold by the government.
These are properties seized after FHA-backed mortgage defaults.
Search: https://hudhomestore.gov
"""

import requests
import json
import time
import math

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/javascript, */*",
    "Content-Type": "application/json",
    "Referer": "https://hudhomestore.gov/",
    "Origin": "https://hudhomestore.gov",
}

# HUD state codes
STATE_CODES = {
    "TX": "TX",
    "NV": "NV",
}

# HUD property type codes: 2=Condo, 1=Single Family, 3=Multi-unit
HUD_PROP_TYPES = {
    "condo": "2",
    "house": "1",
    "any": "",
}


def search(city, state, lat, lng, radius_miles, filters):
    state_code = STATE_CODES.get(state.upper(), state.upper())
    prop_type = HUD_PROP_TYPES.get(filters.get("property_type", "condo"), "2")

    payload = {
        "StateCode": state_code,
        "Zip": "",
        "City": city,
        "County": "",
        "BEDROOMS": str(filters.get("min_beds", 0)),
        "BATHS": "",
        "Accessibility": "",
        "PropertyType": prop_type,
        "ListingType": "",
        "PriceFrom": "0",
        "PriceTo": str(filters.get("max_price", 999999)),
        "SqFtFrom": str(filters.get("min_sqft", 0)),
        "SqFtTo": "",
        "searchRadius": str(radius_miles),
        "startIndex": 0,
        "stopIndex": 200,
        "sortBy": "BidOpenDate",
        "sortOrder": "DESC",
        "Status": "A",  # Active listings only
    }

    time.sleep(1)
    resp = requests.post(
        "https://hudhomestore.gov/HudHomeStore/PropertySearch.aspx/SearchProperties",
        json=payload,
        headers=HEADERS,
        timeout=20,
    )
    resp.raise_for_status()

    # HUD wraps response in {"d": "...json string..."}
    outer = resp.json()
    raw = outer.get("d", "{}")
    if isinstance(raw, str):
        data = json.loads(raw)
    else:
        data = raw

    return _parse_listings(data, city, state)


def _parse_listings(data, city, state):
    listings = []
    homes = data if isinstance(data, list) else data.get("properties", [])

    for home in homes:
        case_num = home.get("CASENO") or home.get("caseNumber", "")
        if not case_num:
            continue

        price = 0
        try:
            price = int(str(home.get("LISTPRICE") or home.get("listPrice", 0)).replace(",", ""))
        except (ValueError, TypeError):
            pass

        address = home.get("STREETADDR") or home.get("streetAddress", "")
        home_city = home.get("CITY") or home.get("city", city)
        home_state = home.get("STATE") or home.get("state", state)
        home_zip = home.get("ZIP") or home.get("zip", "")
        beds = home.get("BEDROOMS") or home.get("bedrooms", 0)
        baths = home.get("BATHS") or home.get("baths", 0)
        sqft = home.get("SQFEET") or home.get("sqFeet", 0)

        listings.append({
            "id": f"hud_{case_num}",
            "price": price,
            "beds": beds,
            "baths": baths,
            "sqft": sqft,
            "address": f"{address}, {home_city}, {home_state} {home_zip}".strip(", "),
            "url": f"https://hudhomestore.gov/Listing/PropertyDetail.aspx?caseNumber={case_num}",
            "source": "HUD Homestore",
            "listing_type": "Government Foreclosure (FHA)",
        })
    return listings
