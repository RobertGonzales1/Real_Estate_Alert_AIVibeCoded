"""
Zillow scraper via RapidAPI (zillow-com1.p.rapidapi.com).
Requires RAPIDAPI_KEY environment variable.
Sign up free at: https://rapidapi.com/apimaker/api/zillow-com1
"""

import requests
import os
import time

RAPIDAPI_HOST = "zillow-com1.p.rapidapi.com"

# Zillow home_type values
PROPERTY_TYPE_MAP = {
    "condo":     "Condo",
    "house":     "Houses",
    "townhouse": "Townhomes",
    "any":       "Condo,Houses,Townhomes,MultiFamily",
}


def search(city, state, lat, lng, radius_miles, filters):
    api_key = os.environ.get("RAPIDAPI_KEY", "")
    if not api_key:
        raise ValueError("RAPIDAPI_KEY environment variable not set")

    prop_type = PROPERTY_TYPE_MAP.get(filters.get("property_type", "condo"), "Condo")
    location = f"{city}, {state}"

    headers = {
        "X-RapidAPI-Key": api_key,
        "X-RapidAPI-Host": RAPIDAPI_HOST,
    }

    params = {
        "location":    location,
        "status_type": "ForSale",
        "home_type":   prop_type,
        "maxPrice":    filters["max_price"],
        "bedsMin":     filters["min_beds"],
        "bathsMin":    filters["min_baths"],
        "sqftMin":     filters.get("min_sqft", 0),
        "sort":        "Newest",
    }

    time.sleep(1)
    resp = requests.get(
        f"https://{RAPIDAPI_HOST}/propertyExtendedSearch",
        headers=headers,
        params=params,
        timeout=20,
    )
    resp.raise_for_status()
    data = resp.json()

    listings = _parse_listings(data)

    # Also search foreclosures separately if requested
    if filters.get("include_foreclosures"):
        time.sleep(1)
        params_fore = dict(params)
        params_fore["status_type"] = "ForSale"
        params_fore["isForeclosure"] = "true"
        try:
            resp2 = requests.get(
                f"https://{RAPIDAPI_HOST}/propertyExtendedSearch",
                headers=headers,
                params=params_fore,
                timeout=20,
            )
            resp2.raise_for_status()
            fore_listings = _parse_listings(resp2.json(), listing_type="Foreclosure")
            # merge, avoiding duplicates
            seen_ids = {L["id"] for L in listings}
            for L in fore_listings:
                if L["id"] not in seen_ids:
                    listings.append(L)
        except Exception as e:
            print(f"  [Zillow] Foreclosure search error: {e}")

    return listings


def _parse_listings(data, listing_type=None):
    listings = []
    props = data.get("props", [])
    if not props:
        props = data.get("results", [])

    for home in props:
        zpid = home.get("zpid")
        if not zpid:
            continue

        price = home.get("price", 0)
        if isinstance(price, str):
            try:
                price = int(price.replace(",", "").replace("$", "").strip())
            except ValueError:
                price = 0

        detail_url = home.get("detailUrl", "")
        if detail_url and not detail_url.startswith("http"):
            detail_url = f"https://www.zillow.com{detail_url}"

        entry = {
            "id":      f"zillow_{zpid}",
            "price":   price,
            "beds":    home.get("bedrooms", 0),
            "baths":   home.get("bathrooms", 0),
            "sqft":    home.get("livingArea", 0),
            "address": home.get("address", ""),
            "url":     detail_url,
            "source":  "Zillow",
        }
        if listing_type:
            entry["listing_type"] = listing_type
        listings.append(entry)

    return listings
