"""
fetch_hubspot.py

Step 1 of the Global Sales Pulse pipeline.

What this does:

1. Reads the HubSpot Service Key from your .env file.
2. Uses the Service Key directly to authenticate with HubSpot.
3. Calls the HubSpot Deals API for deals updated in the last N hours.
4. Handles pagination if HubSpot returns more than 100 deals.
5. Saves the raw response to raw_deals.json so you can inspect it.

No OAuth flow or refresh token is required.
"""

import os
import json
from datetime import datetime, timedelta, timezone

import requests
from dotenv import load_dotenv


# -----------------------------------------------------------------------
# Load environment variables
# -----------------------------------------------------------------------

load_dotenv()


# -----------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------

HOURS_TO_LOOK_BACK = 48

HUBSPOT_SERVICE_KEY = os.getenv("HUBSPOT_SERVICE_KEY")

DEALS_SEARCH_URL = "https://api.hubapi.com/crm/v3/objects/deals/search"

OUTPUT_FILE = "raw_deals.json"


# -----------------------------------------------------------------------
# Check that the Service Key exists
# -----------------------------------------------------------------------

if not HUBSPOT_SERVICE_KEY:
    raise ValueError(
        "HUBSPOT_SERVICE_KEY was not found.\n"
        "Add it to your .env file like this:\n\n"
        "HUBSPOT_SERVICE_KEY=your_actual_service_key"
    )


# -----------------------------------------------------------------------
# Build HubSpot authentication headers
# -----------------------------------------------------------------------

def get_headers():
    """
    HubSpot Service Keys are used directly as Bearer credentials.
    No OAuth token exchange is required.
    """

    return {
        "Authorization": f"Bearer {HUBSPOT_SERVICE_KEY}",
        "Content-Type": "application/json",
    }


# -----------------------------------------------------------------------
# Pull deals updated in the last N hours
# -----------------------------------------------------------------------

def fetch_recent_deals(hours_back):
    """
    Fetch all HubSpot deals modified within the requested lookback window.

    Automatically follows HubSpot pagination until all matching deals
    have been retrieved.
    """

    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours_back)

    # HubSpot search filters expect the timestamp in milliseconds.
    cutoff_ms = int(cutoff.timestamp() * 1000)

    headers = get_headers()

    body = {
        "filterGroups": [
            {
                "filters": [
                    {
                        "propertyName": "hs_lastmodifieddate",
                        "operator": "GTE",
                        "value": str(cutoff_ms),
                    }
                ]
            }
        ],
        "properties": [
            "dealname",
            "amount",
            "dealstage",
            "pipeline",
            "hubspot_owner_id",
            "createdate",
            "hs_lastmodifieddate",
            "closedate",
        ],
        "limit": 100,
    }

    all_results = []
    after_cursor = None

    while True:

        if after_cursor:
            body["after"] = after_cursor
        else:
            body.pop("after", None)

        response = requests.post(
            DEALS_SEARCH_URL,
            headers=headers,
            json=body,
            timeout=30,
        )

        # Give a more useful error than requests' default message.
        if not response.ok:
            print("\nHubSpot API request failed.")
            print(f"Status code: {response.status_code}")
            print(f"Response: {response.text}\n")

            response.raise_for_status()

        data = response.json()

        results = data.get("results", [])
        all_results.extend(results)

        print(
            f"Fetched {len(results)} deals "
            f"({len(all_results)} total so far)..."
        )

        paging = data.get("paging", {}).get("next")

        if paging and paging.get("after"):
            after_cursor = paging["after"]
        else:
            break

    return all_results


# -----------------------------------------------------------------------
# Save raw HubSpot data
# -----------------------------------------------------------------------

def save_to_file(deals, filename):
    """
    Save the HubSpot deal records as formatted JSON.
    """

    with open(filename, "w", encoding="utf-8") as f:
        json.dump(deals, f, indent=2)

    print(f"\nSaved {len(deals)} deals to {filename}")


# -----------------------------------------------------------------------
# Run
# -----------------------------------------------------------------------

if __name__ == "__main__":

    print("HubSpot Service Key found.")
    print("No OAuth token refresh required.")

    print(
        f"\nFetching deals updated in the last "
        f"{HOURS_TO_LOOK_BACK} hours..."
    )

    deals = fetch_recent_deals(HOURS_TO_LOOK_BACK)

    save_to_file(deals, OUTPUT_FILE)

    print("\nDone.")