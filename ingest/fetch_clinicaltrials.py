#!/usr/bin/env python3
"""
Forged By Freedom — ClinicalTrials.gov Fetcher
-----------------------------------------------
Fetches clinical trial data for fitness/performance topics.
Uses ClinicalTrials.gov API (free, no key required).

Usage:
    python fetch_clinicaltrials.py                    # Fetch all topics
    python fetch_clinicaltrials.py --topic "creatine" # Fetch specific topic
    python fetch_clinicaltrials.py --max 100          # Limit per topic
"""

import os
import re
import time
import json
import argparse
import urllib.request
import urllib.parse
from pathlib import Path

# ─── Config ───────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
OUTPUT_DIR = BASE_DIR / "channels" / "@ClinicalTrials"
CACHE_FILE = OUTPUT_DIR / ".fetched_ids.json"

API_BASE = "https://clinicaltrials.gov/api/v2/studies"
MAX_PER_TOPIC = 200
SLEEP_BETWEEN = 0.3

# ─── Topics to search ─────────────────────────────────────────
TOPICS = [
    # Exercise interventions
    "resistance training",
    "strength training",
    "high intensity interval training",
    "aerobic exercise",
    "exercise intervention obesity",
    "exercise intervention diabetes",
    "exercise muscle mass",
    "physical activity intervention",

    # Supplements
    "creatine supplementation",
    "protein supplementation",
    "beta alanine",
    "caffeine exercise",
    "vitamin D muscle",
    "omega 3 exercise",
    "HMB supplementation",

    # Hormones
    "testosterone replacement",
    "growth hormone treatment",
    "DHEA supplementation",

    # Body composition
    "body composition exercise",
    "weight loss exercise",
    "fat loss muscle",
    "sarcopenia intervention",

    # Performance
    "athletic performance",
    "sports nutrition",
    "recovery exercise",
    "sleep athletes",

    # Rehab
    "muscle rehabilitation",
    "tendon injury",
    "low back pain exercise",
    "knee osteoarthritis exercise",
]

# ─── Helpers ──────────────────────────────────────────────────
def load_cache():
    if CACHE_FILE.exists():
        return set(json.loads(CACHE_FILE.read_text()))
    return set()

def save_cache(ids):
    CACHE_FILE.write_text(json.dumps(list(ids)))

def fetch_trials(query, max_results=100):
    """Search ClinicalTrials.gov API."""
    params = urllib.parse.urlencode({
        "query.term": query,
        "pageSize": min(max_results, 100),
        "format": "json"
    })
    url = f"{API_BASE}?{params}"

    time.sleep(SLEEP_BETWEEN)
    req = urllib.request.Request(url, headers={"User-Agent": "ForgedByFreedom/1.0"})

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("studies", [])
    except Exception as e:
        print(f"  Error fetching: {e}")
        return []

def extract_trial_info(study):
    """Extract relevant info from study JSON."""
    proto = study.get("protocolSection", {})
    ident = proto.get("identificationModule", {})
    desc = proto.get("descriptionModule", {})
    status = proto.get("statusModule", {})
    design = proto.get("designModule", {})
    outcomes = proto.get("outcomesModule", {})
    eligibility = proto.get("eligibilityModule", {})

    # Get primary outcomes
    primary_outcomes = []
    for outcome in outcomes.get("primaryOutcomes", [])[:5]:
        primary_outcomes.append(outcome.get("measure", ""))

    # Get interventions
    interventions = []
    for arm in proto.get("armsInterventionsModule", {}).get("interventions", [])[:5]:
        interventions.append(f"{arm.get('type', '')}: {arm.get('name', '')}")

    return {
        "nct_id": ident.get("nctId", ""),
        "title": ident.get("briefTitle", ""),
        "official_title": ident.get("officialTitle", ""),
        "status": status.get("overallStatus", ""),
        "phase": ", ".join(design.get("phases", [])),
        "study_type": design.get("studyType", ""),
        "enrollment": design.get("enrollmentInfo", {}).get("count", ""),
        "brief_summary": desc.get("briefSummary", ""),
        "detailed_description": desc.get("detailedDescription", ""),
        "primary_outcomes": primary_outcomes,
        "interventions": interventions,
        "eligibility_criteria": eligibility.get("eligibilityCriteria", ""),
        "min_age": eligibility.get("minimumAge", ""),
        "max_age": eligibility.get("maximumAge", ""),
        "sex": eligibility.get("sex", ""),
    }

def save_trial(trial, topic):
    """Save trial as text file."""
    if not trial["nct_id"]:
        return None

    filename = f"{trial['nct_id']} - {trial['title'][:70]}.txt"
    filename = re.sub(r'[<>:"/\\|?*]', '', filename)
    filepath = OUTPUT_DIR / filename

    outcomes_str = "\n".join(f"  - {o}" for o in trial["primary_outcomes"]) or "  Not specified"
    interventions_str = "\n".join(f"  - {i}" for i in trial["interventions"]) or "  Not specified"

    content = f"""CLINICAL TRIAL
==============
NCT ID: {trial['nct_id']}
Title: {trial['title']}
Official Title: {trial['official_title']}
Status: {trial['status']}
Phase: {trial['phase'] or 'N/A'}
Study Type: {trial['study_type']}
Enrollment: {trial['enrollment']}
Topic: {topic}

SUMMARY:
{trial['brief_summary']}

DETAILED DESCRIPTION:
{trial['detailed_description'][:3000] if trial['detailed_description'] else 'Not provided'}

PRIMARY OUTCOMES:
{outcomes_str}

INTERVENTIONS:
{interventions_str}

ELIGIBILITY:
Age: {trial['min_age']} to {trial['max_age']}
Sex: {trial['sex']}

---
Source: https://clinicaltrials.gov/study/{trial['nct_id']}
"""

    filepath.write_text(content, encoding="utf-8")
    return filepath

# ─── Main ─────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Fetch ClinicalTrials.gov data")
    parser.add_argument("--topic", help="Fetch specific topic only")
    parser.add_argument("--max", type=int, default=MAX_PER_TOPIC, help="Max per topic")
    parser.add_argument("--dry-run", action="store_true", help="Preview only")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Add channel.url
    channel_url = OUTPUT_DIR / "channel.url"
    if not channel_url.exists():
        channel_url.write_text("https://clinicaltrials.gov/")

    fetched_ids = load_cache()
    topics = [args.topic] if args.topic else TOPICS

    print(f"\n{'='*60}")
    print("CLINICALTRIALS.GOV FETCHER")
    print(f"{'='*60}")
    print(f"Topics: {len(topics)}")
    print(f"Max per topic: {args.max}")
    print(f"Already fetched: {len(fetched_ids)}")
    print(f"Output: {OUTPUT_DIR}")
    print(f"{'='*60}\n")

    total_new = 0

    for i, topic in enumerate(topics, 1):
        print(f"[{i}/{len(topics)}] {topic}")

        try:
            studies = fetch_trials(topic, args.max)
            new_count = 0

            for study in studies:
                trial = extract_trial_info(study)
                if not trial["nct_id"] or trial["nct_id"] in fetched_ids:
                    continue

                if args.dry_run:
                    continue

                if save_trial(trial, topic):
                    fetched_ids.add(trial["nct_id"])
                    new_count += 1
                    total_new += 1

            if args.dry_run:
                new_ids = [extract_trial_info(s)["nct_id"] for s in studies]
                new_ids = [i for i in new_ids if i and i not in fetched_ids]
                print(f"  Would fetch {len(new_ids)} new trials")
            else:
                print(f"  ✓ Fetched {new_count} new trials")

        except Exception as e:
            print(f"  ✗ Error: {e}")

        if i % 10 == 0:
            save_cache(fetched_ids)

    save_cache(fetched_ids)

    print(f"\n{'='*60}")
    print(f"COMPLETE: {total_new} new trials fetched")
    print(f"Total cached: {len(fetched_ids)}")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    main()
