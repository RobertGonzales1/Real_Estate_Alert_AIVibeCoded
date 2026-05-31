"""
HUD Homestore scraper — FHA-insured foreclosures sold by the government.
Uses HUD's public ArcGIS REST API (no auth required).
Browse listings at: https://hudhomestore.gov
"""

import requests
import time

# HUD publishes property data via ArcGIS REST API
HUD_ARCGIS_URL = (
    "https://services.arcgis.com/VTyQ9soqVukalItT/arcgis/rest/services/"
    "HUD_Homestore_Listings/FeatureServer/0/query"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Referer": "https://hudhomestore.gov/",
}

# HUD property type field values
PROP_TYPE_MAP = {
    "condo":     "CO",
    "house":     "SFR",
    "townhouse": "TO",
    "any":       None,
}

# State FIPS abbreviations for filtering
STATE_FILTER = {
    "TX": "TX",
    "NV": "NV",
}


def search(city, state, lat, lng, radius_miles, filters):
    state_code = STATE_FILTER.get(state.upper(), state.upper())
    prop_code = PROP_TYPE_MAP.get(filters.get("property_type", "condo"))
    max_price = filters.get("max_price", 999999)
    min_beds = filters.get("min_beds", 0)
    min_sqft = filters.get("min_sqft", 0)

    # Build WHERE clause
    where_parts = [
        f"STATEFP = '{state_code}'",
        f"LP <= {max_price}",
        "STATUS = 'A'",  # Active listings only
    ]
    if prop_code:
        where_parts.append(f"PROP_TYPE = '{prop_code}'")
    if min_beds:
        where_parts.append(f"BEDROOMS >= {min_beds}")
    if min_sqft:
        where_parts.append(f"SQFT >= {min_sqft}")

    where = " AND ".join(where_parts)

    params = {
        "where":         where,
        "outFields":     "CASENO,STREETADDR,CITY,STATE,ZIP,LP,BEDROOMS,BATHS,SQFT,PROP_TYPE",
        "returnGeometry": "false",
        "resultRecordCount": 200,
        "f":             "json",
    }

    time.sleep(1)
    resp = requests.get(HUD_ARCGIS_URL, params=params, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    data = resp.json()

    return _parse_listings(data)


def _parse_listings(data):
    listings = []
    features = data.get("features", [])

    for feature in features:
        attrs = feature.get("attributes", {})
        case_num = attrs.get("CASENO", "")
        if not case_num:
            continue

        price = attrs.get("LP", 0) or 0
        address = attrs.get("STREETADDR", "")
        city_val = attrs.get("CITY", "")
        state_val = attrs.get("STATE", "")
        zip_val = attrs.get("ZIP", "")
        beds = attrs.get("BEDROOMS", 0)
        baths = attrs.get("BATHS", 0)
        sqft = attrs.get("SQFT", 0)

        listings.append({
            "id":           f"hud_{case_num}",
            "price":        price,
            "beds":         beds,
            "baths":        baths,
            "sqft":         sqft,
            "address":      f"{address}, {city_val}, {state_val} {zip_val}".strip(", "),
            "url":          f"https://hudhomestore.gov/Listing/PropertyDetail.aspx?caseNumber={case_num}",
            "source":       "HUD Homestore",
            "listing_type": "Gov't Foreclosure (FHA)",
        })
    return listings
