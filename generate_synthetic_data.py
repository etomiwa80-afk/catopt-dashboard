"""
generate_synthetic_data.py
Generates synthetic CATOPT CSVs matching the exact schema of the real outputs.
Run this once to create the data/ folder before launching the dashboard.

Usage:
    python generate_synthetic_data.py

Outputs (written to ./data/):
    catopt_run1_daily.csv
    catopt_run2_daily.csv
    catopt_run3_daily.csv
    catopt_run1_assignments.csv
    catopt_run2_assignments.csv
    catopt_run3_assignments.csv
"""

import os
import random
import numpy as np
import pandas as pd

random.seed(7900)
np.random.seed(7900)

os.makedirs("data", exist_ok=True)

STATES = ["AL","GA","TN","MS","KY","NC","SC","VA","MD","PA",
          "NJ","NY","CT","MA","OH","IN","IL","MI","MN","TX",
          "LA","FL","CO","AZ","CA","WA","OR","WI","MO","NE"]

TOTAL_CLAIMS = 1054
SEV_COUNTS   = {5: 278, 4: 211, 3: 415, 2: 91, 1: 59}
SLA_DAYS     = {5: 7, 4: 14, 3: 21, 2: 28, 1: 28}
SKILL_DIST   = {5: 33, 4: 71, 3: 291, 2: 139, 1: 106}

def _make_daily(n_days, sev5_final_met, total_met, label):
    rows = []
    cumulative = 0
    sev_cum = {s: 0 for s in [1,2,3,4,5]}
    for day in range(1, n_days + 1):
        frac      = day / n_days
        new_asgn  = max(0, int(np.random.normal(60 * (1 - frac) + 5, 10)))
        completed = max(0, int(np.random.normal(50 * (1 - frac**0.5) + 3, 8)))
        cumulative = min(cumulative + completed, total_met)
        in_prog   = max(0, int(np.random.normal(150 * (1 - frac), 20)))
        waiting   = max(0, TOTAL_CLAIMS - cumulative - in_prog)
        row = {
            "day":             day,
            "new_assignments": new_asgn,
            "completed_today": completed,
            "in_progress":     in_prog,
            "waiting":         waiting,
            "total_completed": cumulative,
        }
        for sev in [1, 2, 3, 4, 5]:
            assigned = max(0, int(new_asgn * SEV_COUNTS[sev] / TOTAL_CLAIMS
                           + np.random.randint(-3, 4)))
            sev_cum[sev] = min(sev_cum[sev] + max(0, int(completed * SEV_COUNTS[sev] / TOTAL_CLAIMS)),
                               SEV_COUNTS[sev])
            row[f"sev{sev}_assigned"]            = assigned
            row[f"sev{sev}_waiting"]             = max(0, SEV_COUNTS[sev] - sev_cum[sev])
            row[f"sev{sev}_sla_met_cumulative"]  = sev_cum[sev]
        rows.append(row)
    return pd.DataFrame(rows)

def _make_assignments(sev5_met_pct, boosted_frac, n_rows=TOTAL_CLAIMS):
    records = []
    claim_id_base = 10000000
    adj_id_base   = 17000000
    sevs = []
    for sev, count in SEV_COUNTS.items():
        sevs.extend([sev] * count)
    random.shuffle(sevs)
    for i in range(n_rows):
        sev       = sevs[i]
        deadline  = SLA_DAYS[sev]
        day       = random.randint(1, max(1, deadline - 2))
        if sev == 5:
            skill = random.choices([5, 4], weights=[33, 71])[0]
        elif sev == 4:
            skill = random.choices([5, 4, 3], weights=[10, 50, 291])[0]
        else:
            skill = random.choice([3, 2, 1])
        boosted       = (skill >= 4) and (random.random() < boosted_frac)
        completion_day = day + random.randint(1, SLA_DAYS[sev] - 1)
        if sev == 5:
            sla_met = random.random() < sev5_met_pct
        else:
            sla_met = random.random() < 0.99
        if sla_met:
            completion_day = min(completion_day, deadline)
        else:
            completion_day = deadline + random.randint(1, 5)
        dist_miles = round(random.uniform(50, 900), 1)
        drive_h    = round(dist_miles * 1.60934 * 1.3 / 105, 2)
        records.append({
            "day":              day,
            "adj_id":           adj_id_base + random.randint(1000, 9999999),
            "claim_id":         claim_id_base + i,
            "skill":            skill,
            "boosted":          boosted,
            "severity":         sev,
            "sla_deadline":     deadline,
            "adj_state":        random.choice(STATES),
            "claim_state":      random.choice(["TN","GA","MS","KY","NC","AL","VA","MD","PA","NY"]),
            "completion_day":   completion_day,
            "sla_met":          sla_met,
            "days_to_complete": completion_day - day,
            "distance_miles":   dist_miles,
            "drive_hours":      drive_h,
        })
    return pd.DataFrame(records)

print("Generating synthetic CATOPT data...")
run1_daily = _make_daily(n_days=25, sev5_final_met=97,  total_met=873, label="Run1")
run1_asgn  = _make_assignments(sev5_met_pct=0.349, boosted_frac=0.0)
run2_daily = _make_daily(n_days=25, sev5_final_met=136, total_met=912, label="Run2")
run2_asgn  = _make_assignments(sev5_met_pct=0.489, boosted_frac=0.60)
run3_daily = _make_daily(n_days=23, sev5_final_met=172, total_met=940, label="Run3")
run3_asgn  = _make_assignments(sev5_met_pct=0.618, boosted_frac=0.70)
run1_daily.to_csv("data/catopt_run1_daily.csv",       index=False)
run2_daily.to_csv("data/catopt_run2_daily.csv",       index=False)
run3_daily.to_csv("data/catopt_run3_daily.csv",       index=False)
run1_asgn.to_csv( "data/catopt_run1_assignments.csv", index=False)
run2_asgn.to_csv( "data/catopt_run2_assignments.csv", index=False)
run3_asgn.to_csv( "data/catopt_run3_assignments.csv", index=False)
print("Done. Files written to ./data/")
