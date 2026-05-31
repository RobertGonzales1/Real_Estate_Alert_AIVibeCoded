"""
US Marshals Service asset forfeiture scraper.
Searches the USMS property sales listing for real estate in target states.
Source: https://www.usmarshals.gov/what-we-do/asset-forfeiture/real-property
"""

import requests
from bs4 import BeautifulSoup
import re
import time

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,*/*",
    "Referer": "https://www.usmarshals.gov/",
}

USMS_URL = "https://www.usmarshals.gov/what-we-do/asset-forfeiture/real-property"


def search(city, state, lat, lng, radius_miles, filters):
    """
    Scrape USMS real property listings and filter by state + price.
    USMS doesn't have a structured search API, so we scrape the listing page
    and filter locally.
    """
    time.sleep(1)
    try:
        resp = requests.get(USMS_URL, headers=HEADERS, timeout=20)
        resp.raise_for_status()
    except Exception as e:
        raise RuntimeError(f"USMS fetch failed: {e}")

    soup = BeautifulSoup(resp.text, "lxml")
    listings = []
    max_price = filters.get("max_price", 999999)
    state_upper = state.upper()

    # USMS lists properties in tables or definition lists — try both layouts
    # Look for any table rows or cards containing state abbreviation
    all_text_blocks = soup.find_all(
        ["tr", "li", "div"],
        string=lambda t: t and state_upper in t
    )

    # Also search for links to individual property pages
    for link in soup.find_all("a", href=True):
        href = link["href"]
        if "property" not in href.lower() and "listing" not in href.lower():
            continue
        text = link.get_text(separator=" ", strip=True)
        if state_upper not in text.upper():
            continue

        # Try to extract a price from surrounding text
        parent_text = ""
        parent = link.parent
        for _ in range(3):
            if parent:
                parent_text = parent.get_text(separator=" ", strip=True)
                parent = parent.parent

        price = _extract_price(parent_text)
        if price and price > max_price:
            continue

        full_url = href if href.startswith("http") else f"https://www.usmarshals.gov{href}"
        uid = re.sub(r"[^a-z0-9]", "_", full_url.lower())[-60:]

        listings.append({
            "id": f"usms_{uid}",
            "price": price or 0,
            "beds": 0,
            "baths": 0,
            "sqft": 0,
            "address": text[:120],
            "url": full_url,
            "source": "US Marshals",
            "listing_type": "Asset Forfeiture",
        })

    # De-duplicate by URL
    seen_urls = set()
    unique = []
    for L in listings:
        if L["url"] not in seen_urls:
            seen_urls.add(L["url"])
            unique.append(L)

    return unique


def _extract_price(text):
    """Pull the first dollar amount out of a text string."""
    match = re.search(r"\$[\d,]+", text)
    if match:
        try:
            return int(match.group().replace("$", "").replace(",", ""))
        except ValueError:
            pass
    return None
