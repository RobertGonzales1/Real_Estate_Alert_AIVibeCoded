"""
US Real Estate API via RapidAPI (us-real-estate.p.rapidapi.com).
Requires RAPIDAPI_KEY environment variable.
Sign up free at: https://rapidapi.com/datascraper/api/us-real-estate
"""

import requests
import os
import time

RAPIDAPI_HOST = "us-real-estate.p.rapidapi.com"

PROPERTY_TYPE_MAP = {
    "condo":     "condos",
    "house":     "single_family",
    "townhouse": "townhomes",
    "any":       "",
}


def search(city, state, lat, lng, radius_miles, filters):
    api_key = os.environ.get("RAPIDAPI_KEY", "")
    if not api_key:
        raise ValueError("RAPIDAPI_KEY environment variable not set")

    headers = {
        "x-rapidapi-key":  api_key,
        "x-rapidapi-host": RAPIDAPI_HOST,
        "Content-Type":    "application/json",
    }

    prop_type = PROPERTY_TYPE_MAP.get(filters.get("property_type", "condo"), "condos")

    params = {
        "state_code": state,
        "city":       city,
        "sort":       "newest",
        "offset":     0,
        "limit":      200,
        "price_max":  filters["max_price"],
        "beds_min":   filters["min_beds"],
        "baths_min":  filters["min_baths"],
    }
    if filters.get("min_sqft"):
        params["sqft_min"] = filters["min_sqft"]
    if prop_type:
        params["home_type"] = prop_type

    time.sleep(1)
    resp = requests.get(
        f"https://{RAPIDAPI_HOST}/v3/for-sale",
        headers=headers,
        params=params,
        timeout=20,
    )
    resp.raise_for_status()
    data = resp.json()
    listings = _parse_listings(data)

    # Foreclosure pass
    if filters.get("include_foreclosures"):
        time.sleep(1)
        fore_params = dict(params)
        fore_params["foreclosure"] = "true"
        try:
            resp2 = requests.get(
                f"https://{RAPIDAPI_HOST}/v3/for-sale",
                headers=headers,
                params=fore_params,
                timeout=20,
            )
            resp2.raise_for_status()
            fore_listings = _parse_listings(resp2.json(), listing_type="Foreclosure")
            seen_ids = {L["id"] for L in listings}
            for L in fore_listings:
                if L["id"] not in seen_ids:
                    listings.append(L)
        except Exception as e:
            print(f"  [US Real Estate API] Foreclosure search error: {e}")

    return listings


def _parse_listings(data, listing_type=None):
    listings = []

    # Response structure: data -> home_search -> results
    results = data.get("data", {}).get("home_search", {}).get("results", [])
    if not results:
        # fallback paths
        results = (
            data.get("data", {}).get("results", [])
            or data.get("results", [])
        )

    for home in results:
        prop_id = home.get("property_id") or home.get("zpid")
        if not prop_id:
            continue

        listing = home.get("listing", home)
        price = (
            listing.get("list_price")
            or listing.get("price")
            or home.get("list_price", 0)
        )
        if isinstance(price, str):
            try:
                price = int(price.replace(",", "").replace("$", "").strip())
            except ValueError:
                price = 0

        desc  = home.get("description") or {}
        beds  = desc.get("beds")  or home.get("beds",  0)
        baths = desc.get("baths") or home.get("baths", 0)
        sqft  = desc.get("sqft")  or home.get("sqft",  0)
        prop_type = (desc.get("type") or home.get("prop_type") or "").lower()

        loc = (home.get("location") or {}).get("address") or {}
        line  = loc.get("line",        home.get("address", ""))
        city  = loc.get("city",        "")
        state = loc.get("state_code",  "")
        zip_  = loc.get("postal_code", "")
        address = f"{line}, {city}, {state} {zip_}".strip(", ")

        permalink = home.get("permalink") or home.get("slug_id", "")
        url = (
            f"https://www.realtor.com/realestateandhomes-detail/{permalink}"
            if permalink else "#"
        )

        entry = {
            "id":        f"usrealestate_{prop_id}",
            "price":     price,
            "beds":      beds,
            "baths":     baths,
            "sqft":      sqft,
            "address":   address,
            "url":       url,
            "source":    "Realtor.com",
            "prop_type": prop_type,
        }
        if listing_type:
            entry["listing_type"] = listing_type
        listings.append(entry)

    return listings
