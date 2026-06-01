"""
Real Estate Alert System
Scrapes Redfin and Zillow for new condo listings matching your criteria,
then emails you any listings not seen before.
"""

import json
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

from scrapers import redfin, zillow, hud, usmarshals
from notifier import send_alert_email

load_dotenv()

CONFIG_FILE = Path(__file__).parent / "config.json"
SEEN_FILE = Path(__file__).parent / "seen_listings.json"


def load_seen():
    if SEEN_FILE.exists():
        return set(json.loads(SEEN_FILE.read_text()))
    return set()


def save_seen(seen):
    SEEN_FILE.write_text(json.dumps(sorted(seen), indent=2))


def matches_filters(listing, filters, search_city, search_state):
    """Hard client-side check — rejects anything the API let through that doesn't match."""
    price  = listing.get("price", 0) or 0
    beds   = listing.get("beds",  0) or 0
    baths  = listing.get("baths", 0) or 0
    sqft   = listing.get("sqft",  0) or 0
    addr   = (listing.get("address") or "").upper()

    # Price must be > 0 and within budget
    if price <= 0 or price > filters["max_price"]:
        return False
    # Beds and baths (only reject if the listing reports a non-zero value that's too low)
    if beds  > 0 and beds  < filters["min_beds"]:
        return False
    if baths > 0 and baths < filters["min_baths"]:
        return False
    # Sqft (only reject if reported and too small)
    if sqft > 0 and filters.get("min_sqft") and sqft < filters["min_sqft"]:
        return False
    # Address must contain the correct state abbreviation
    state_upper = search_state.upper()
    if state_upper not in addr:
        return False

    return True


def run_search(search_config, filters):
    city = search_config["city"]
    state = search_config["state"]
    lat = search_config["lat"]
    lng = search_config["lng"]
    radius = search_config["radius_miles"]
    area_label = f"{city}, {state}"

    found = []

    # Redfin disabled — GitHub Actions servers are in Oregon and Redfin ignores
    # the region_id parameter from datacenter IPs, returning local (wrong) results.
    print(f"  [Redfin] Skipped — not reliable from cloud runners.")

    print(f"  [Zillow] Searching {area_label}...")
    try:
        listings = zillow.search(city, state, lat, lng, radius, filters)
        print(f"  [Zillow] {len(listings)} listings returned.")
        for L in listings:
            L["search_area"] = area_label
        found.extend(listings)
    except Exception as e:
        print(f"  [Zillow] ERROR: {e}")

    if filters.get("include_asset_forfeitures"):
        print(f"  [HUD] Searching {area_label}...")
        try:
            listings = hud.search(city, state, lat, lng, radius, filters)
            print(f"  [HUD] {len(listings)} listings returned.")
            for L in listings:
                L["search_area"] = area_label
            found.extend(listings)
        except Exception as e:
            print(f"  [HUD] ERROR: {e}")

        print(f"  [US Marshals] Searching {state}...")
        try:
            listings = usmarshals.search(city, state, lat, lng, radius, filters)
            print(f"  [US Marshals] {len(listings)} listings returned.")
            for L in listings:
                L["search_area"] = area_label
            found.extend(listings)
        except Exception as e:
            print(f"  [US Marshals] ERROR: {e}")

    return found


def main():
    gmail_user = os.getenv("GMAIL_USER")
    gmail_pass = os.getenv("GMAIL_APP_PASSWORD")
    if not gmail_user or not gmail_pass:
        print("ERROR: GMAIL_USER and GMAIL_APP_PASSWORD must be set in .env")
        sys.exit(1)

    config = json.loads(CONFIG_FILE.read_text())
    filters = config["filters"]
    seen = load_seen()
    new_listings = []

    for search_cfg in config["searches"]:
        print(f"\nSearching {search_cfg['city']}, {search_cfg['state']}...")
        all_found = run_search(search_cfg, filters)

        city  = search_cfg["city"]
        state = search_cfg["state"]
        for listing in all_found:
            if listing["id"] not in seen:
                seen.add(listing["id"])
                if matches_filters(listing, filters, city, state):
                    new_listings.append(listing)
                else:
                    print(f"  [Filter] Skipped: {listing.get('address')} | ${listing.get('price')} | {listing.get('beds')}bd {listing.get('baths')}ba {listing.get('sqft')}sqft")

    print(f"\n{len(new_listings)} new listing(s) found across all sources.")

    if new_listings:
        print(f"Sending alert email to {config['alert_email']}...")
        send_alert_email(
            to_email=config["alert_email"],
            listings=new_listings,
            gmail_user=gmail_user,
            gmail_app_password=gmail_pass,
        )
        print("Email sent.")
    else:
        print("No email sent (no new listings).")

    save_seen(seen)
    print("Done.")


if __name__ == "__main__":
    main()
