import cloudscraper
import json
import math
import time
import urllib.parse

# Zillow filter state keys for property types
# con=condo, sf=single-family, tow=townhouse, mf=multi-family
PROPERTY_TYPE_FILTERS = {
    "condo":     {"con": True,  "sf": False, "tow": False, "mf": False, "land": False, "apa": False},
    "house":     {"con": False, "sf": True,  "tow": False, "mf": False, "land": False, "apa": False},
    "townhouse": {"con": False, "sf": False, "tow": True,  "mf": False, "land": False, "apa": False},
    "any":       {"con": True,  "sf": True,  "tow": True,  "mf": False, "land": False, "apa": False},
}


def _bounding_box(lat, lng, radius_miles):
    lat_delta = radius_miles / 69.0
    lng_delta = radius_miles / (69.0 * math.cos(math.radians(lat)))
    return {
        "west": round(lng - lng_delta, 6),
        "east": round(lng + lng_delta, 6),
        "south": round(lat - lat_delta, 6),
        "north": round(lat + lat_delta, 6),
    }


def search(city, state, lat, lng, radius_miles, filters):
    bounds = _bounding_box(lat, lng, radius_miles)
    prop_type = filters.get("property_type", "condo")
    type_flags = PROPERTY_TYPE_FILTERS.get(prop_type, PROPERTY_TYPE_FILTERS["condo"])

    include_foreclosures = filters.get("include_foreclosures", False)

    filter_state = {
        "price": {"max": filters["max_price"]},
        "beds":  {"min": filters["min_beds"]},
        "baths": {"min": filters["min_baths"]},
        "sqft":  {"min": filters.get("min_sqft", 0)},
        "sort":  {"value": "days"},
        "fsbo":  {"value": False},
        "cmsn":  {"value": False},
        "fore":  {"value": include_foreclosures},  # bank-owned / foreclosures
        "auc":   {"value": include_foreclosures},  # auction listings
        "pmf":   {"value": False},
        "pf":    {"value": False},
        "nc":    {"value": False},
    }
    for k, v in type_flags.items():
        filter_state[k] = {"value": v}

    search_query = {
        "pagination": {},
        "isMapVisible": True,
        "mapBounds": bounds,
        "filterState": filter_state,
        "isListVisible": True,
        "mapZoom": 9,
    }

    url = "https://www.zillow.com/search/GetSearchPageState.htm"
    params = {
        "searchQueryState": json.dumps(search_query, separators=(",", ":")),
        "wants": json.dumps({"cat1": ["listResults", "mapResults"]}),
        "requestId": 1,
    }

    scraper = cloudscraper.create_scraper(browser={"browser": "chrome", "platform": "windows"})
    time.sleep(2)  # polite delay
    resp = scraper.get(url, params=params, timeout=20)
    resp.raise_for_status()
    data = resp.json()

    return _parse_listings(data)


def _parse_listings(data):
    listings = []
    results = (
        data.get("cat1", {})
            .get("searchResults", {})
            .get("listResults", [])
    )
    for home in results:
        zpid = home.get("zpid")
        if not zpid:
            continue

        price_raw = home.get("unformattedPrice") or home.get("price", "0")
        try:
            price = int(str(price_raw).replace(",", "").replace("$", "").strip())
        except (ValueError, TypeError):
            price = 0

        beds = home.get("beds", 0)
        baths = home.get("baths", 0)
        area = home.get("area", 0)
        address = home.get("address", "")
        detail_url = home.get("detailUrl", "")
        if detail_url and not detail_url.startswith("http"):
            detail_url = f"https://www.zillow.com{detail_url}"

        listings.append({
            "id": f"zillow_{zpid}",
            "price": price,
            "beds": beds,
            "baths": baths,
            "sqft": area,
            "address": address,
            "url": detail_url,
            "source": "Zillow",
        })
    return listings
