"""
build_summary.py

Step 2 of the Global Sales Pulse pipeline (Mediation Pipeline only, for now).

What this does:
  1. Reads raw_deals.json (produced by fetch_hubspot.py).
  2. Keeps only deals that belong to the Mediation Pipeline.
  3. Replaces HubSpot's numeric stage IDs with readable stage names.
  4. Produces a clean daily summary: deal counts by stage, and (once we
     confirm won/lost logic) closed-won totals.

NOTE — OPEN QUESTION FLAGGED BY PAUL'S PLAN:
  The Mediation Pipeline stage list has no "Closed Lost" stage. Until
  Paul confirms how lost deals are actually tracked (a separate HubSpot
  property, archiving, or a missing stage), this script only reports
  "Signed" as closed-won and does NOT attempt to calculate closed-lost.
  Search for "TODO: WON/LOST LOGIC" below once that's confirmed.

Run it (after fetch_hubspot.py has produced raw_deals.json):
  python transform/build_summary.py
"""

import json
from collections import defaultdict

# -----------------------------------------------------------------------
# Configuration: Mediation Pipeline stage mapping (from Paul, Sept 2026)
# -----------------------------------------------------------------------

MEDIATION_PIPELINE_ID = "918902413"

STAGE_ID_TO_NAME = {
    "1403129013": "Lead",
    "1403129015": "Marketing Qualified Lead",
    "1422061183": "Started Outreach",
    "1403129016": "Sales prospecting",
    "1403129017": "Sales Qualified Lead",
    "1403129088": "Sales proposal",
    "1403129089": "Internal Review and Approval",
    "1403129090": "MSA Shared with Customer",
    "1403129091": "Signed",
}

# The stage that represents a won deal. Update this if "Signed" isn't
# the right signal, or once real closed-lost logic is confirmed.
WON_STAGE_NAME = "Signed"

INPUT_FILE = "raw_deals.json"
OUTPUT_FILE = "daily_summary.json"

# -----------------------------------------------------------------------
# Step 1: load the raw data
# -----------------------------------------------------------------------

def load_raw_deals(filename):
    with open(filename, "r") as f:
        return json.load(f)

# -----------------------------------------------------------------------
# Step 2: keep only Mediation Pipeline deals, and attach a readable stage
# -----------------------------------------------------------------------

def filter_and_label_mediation_deals(deals):
    mediation_deals = []

    for deal in deals:
        props = deal.get("properties", {})

        if props.get("pipeline") != MEDIATION_PIPELINE_ID:
            continue  # skip deals from any other pipeline

        stage_id = props.get("dealstage")
        stage_name = STAGE_ID_TO_NAME.get(stage_id, f"Unknown stage ({stage_id})")

        mediation_deals.append({
            "deal_id": deal.get("id"),
            "name": props.get("dealname"),
            "amount": props.get("amount"),
            "stage_id": stage_id,
            "stage_name": stage_name,
            "owner_id": props.get("hubspot_owner_id"),
            "createdate": props.get("createdate"),
            "closedate": props.get("closedate"),
        })

    return mediation_deals

# -----------------------------------------------------------------------
# Step 3: build the daily summary
# -----------------------------------------------------------------------

def build_summary(deals):
    deals_by_stage = defaultdict(int)
    value_by_stage = defaultdict(float)

    closed_won_count = 0
    closed_won_value = 0.0

    for deal in deals:
        stage = deal["stage_name"]
        deals_by_stage[stage] += 1

        # amount can be missing/blank on early-stage deals
        try:
            amount = float(deal["amount"]) if deal["amount"] else 0.0
        except (TypeError, ValueError):
            amount = 0.0

        value_by_stage[stage] += amount

        # TODO: WON/LOST LOGIC — replace this once Paul confirms how
        # lost deals are actually tracked in HubSpot.
        if stage == WON_STAGE_NAME:
            closed_won_count += 1
            closed_won_value += amount

    return {
        "total_mediation_deals": len(deals),
        "deals_by_stage": dict(deals_by_stage),
        "value_by_stage": dict(value_by_stage),
        "closed_won_count": closed_won_count,
        "closed_won_value": closed_won_value,
        # closed_lost intentionally omitted until won/lost logic is confirmed
    }

# -----------------------------------------------------------------------
# Run
# -----------------------------------------------------------------------

if __name__ == "__main__":
    print("Loading raw deals...")
    raw_deals = load_raw_deals(INPUT_FILE)

    print("Filtering to Mediation Pipeline and mapping stage names...")
    mediation_deals = filter_and_label_mediation_deals(raw_deals)
    print(f"Found {len(mediation_deals)} Mediation Pipeline deals "
          f"(out of {len(raw_deals)} total deals fetched).")

    print("Building daily summary...")
    summary = build_summary(mediation_deals)

    with open(OUTPUT_FILE, "w") as f:
        json.dump(summary, f, indent=2)

    print(f"Saved summary to {OUTPUT_FILE}")
    print(json.dumps(summary, indent=2))