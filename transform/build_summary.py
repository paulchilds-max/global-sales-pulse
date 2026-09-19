"""
build_summary.py

Step 2 of the Global Sales Pulse pipeline (Mediation Pipeline only, for now).

What this does:
  1. Reads raw_deals.json (produced by fetch_hubspot.py).
  2. Keeps only deals that belong to the Mediation Pipeline.
  3. Replaces HubSpot's numeric stage IDs with readable stage names.
  4. Produces a clean daily summary: deal counts by stage, and (once we
     confirm won/lost logic) closed-won totals.

OPEN QUESTIONS FLAGGED FOR PAUL (defaults chosen below — override if wrong):
  1. "Sales Qualified Out" is currently treated as a distinct
     "disqualified" bucket, NOT counted as closed-lost, since it sits
     before "Closed Lost" in the stage list and may just mean
     "not ready" rather than "we lost the deal."
  2. "Paused" and "Churned" are counted as having been won at some
     point (they're past Signed), but are broken out separately as
     "at_risk_or_churned" rather than folded into a flat closed-won
     number, since lumping them in would overstate current healthy
     revenue.
  Search for "TODO: WON/LOST LOGIC" below to change either behavior.

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
    "1403129092": "Waiting to Start Integration",
    "1403129093": "Integrating",
    "1403129094": "Live & Testing",
    "1403129095": "Fully Scaled",
    "1403129096": "Paused",
    "1403129097": "Churned",
    "1403129099": "Sales Qualified Out",
    "1403129100": "Closed Lost",
}

# TODO: WON/LOST LOGIC — stages counted as "won" (post-signature).
WON_STAGE_NAMES = {
    "Signed", "Waiting to Start Integration", "Integrating",
    "Live & Testing", "Fully Scaled",
}

# TODO: WON/LOST LOGIC — won deals that have since gone inactive.
AT_RISK_STAGE_NAMES = {"Paused", "Churned"}

# TODO: WON/LOST LOGIC — explicitly lost. "Sales Qualified Out" is
# deliberately excluded here — see open question #1 above.
LOST_STAGE_NAMES = {"Closed Lost"}

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
    deal_names_by_stage = defaultdict(list)

    closed_won_count = 0
    closed_won_value = 0.0
    at_risk_count = 0
    at_risk_value = 0.0
    closed_lost_count = 0
    closed_lost_value = 0.0
    disqualified_count = 0
    disqualified_value = 0.0

    for deal in deals:
        stage = deal["stage_name"]

        # amount can be missing/blank on early-stage deals
        try:
            amount = float(deal["amount"]) if deal["amount"] else 0.0
        except (TypeError, ValueError):
            amount = 0.0

        # "Sales Qualified Out" isn't a real opportunity — excluded
        # entirely from totals and stage breakdown, tracked separately.
        if stage == "Sales Qualified Out":
            disqualified_count += 1
            disqualified_value += amount
            continue

        deals_by_stage[stage] += 1
        value_by_stage[stage] += amount
        deal_names_by_stage[stage].append(deal["name"])

        if stage in WON_STAGE_NAMES:
            closed_won_count += 1
            closed_won_value += amount
        elif stage in AT_RISK_STAGE_NAMES:
            at_risk_count += 1
            at_risk_value += amount
        elif stage in LOST_STAGE_NAMES:
            closed_lost_count += 1
            closed_lost_value += amount

    return {
        # total_mediation_deals deliberately excludes "Sales Qualified Out"
        "total_mediation_deals": sum(deals_by_stage.values()),
        "deals_by_stage": dict(deals_by_stage),
        "value_by_stage": dict(value_by_stage),
        "deal_names_by_stage": dict(deal_names_by_stage),
        "closed_won_count": closed_won_count,
        "closed_won_value": closed_won_value,
        "at_risk_or_churned_count": at_risk_count,
        "at_risk_or_churned_value": at_risk_value,
        "closed_lost_count": closed_lost_count,
        "closed_lost_value": closed_lost_value,
        "disqualified_count": disqualified_count,
        "disqualified_value": disqualified_value,
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

    print("\n--- Deals that moved, by stage ---")
    for stage, names in summary["deal_names_by_stage"].items():
        print(f"\n{stage} ({len(names)}):")
        for name in names:
            print(f"  - {name}")