# config.py — Default configuration for CATOPT (Python port of config.R)
# All parameters are read from here. Nothing hardcoded elsewhere.

default_config = {

    # --- Throughput rates: claims per day (adjuster skill x claim severity) ---
    # None = cannot handle (hard constraint)
    # Outer key = adjuster PL skill (5 down to 0)
    # Inner key = claim severity   (5 down to 1)
    "throughput": {
        5: {5: 0.25,  4: 1.00,  3: 2.00, 2: 2.50, 1: 3.00},
        4: {5: 0.125, 4: 0.75,  3: 2.00, 2: 2.50, 1: 3.00},
        3: {5: None,  4: 0.125, 3: 2.00, 2: 2.50, 1: 3.00},
        2: {5: None,  4: None,  3: 1.50, 2: 2.00, 1: 3.00},
        1: {5: None,  4: None,  3: None, 2: 0.50, 1: 3.00},
        0: {5: None,  4: None,  3: None, 2: None, 1: None},
    },

    # --- SLA windows (days from NOL date) ---
    "sla_days": {5: 7, 4: 14, 3: 21, 2: 28, 1: 28},

    # --- Handle type mix (on-site proportion per severity) ---
    # Remainder is virtual. Randomized once during data prep.
    "onsite_prob": {5: 1.00, 4: 1.00, 3: 0.75, 2: 0.50, 1: 0.00},

    # --- Severity weights for MIP objective ---
    "severity_weight": {5: 100, 4: 50, 3: 20, 2: 10, 1: 5},

    # --- Qtr Rank bonus (soft tiebreaker in MIP objective) ---
    "qtr_rank_bonus": {0: 1.00, 1: 1.02, 2: 1.01, 3: 1.00, 4: 0.99},

    # --- Minimum skill level required per severity ---
    "min_skill": {5: 4, 4: 3, 3: 2, 2: 1, 1: 1},

    # --- Cost rates ($/day) — full rates for reference / reporting ---
    "cost_local":      290,   # in-cluster staff (sunk cost, tracked for reference)
    "cost_deployed":   440,   # cross-cluster staff ($290 + $150 per diem)
    "cost_contractor": 500,   # contractor daily rate

    # --- Incremental cost rates (new money only) ---
    # Local staff are salaried — the insurer pays them whether a CAT happens or not.
    # Only per diem for deployed staff and full contractor cost are incremental.
    "cost_local_incremental":      0,    # $0 — already on salary, sunk cost
    "cost_deployed_incremental":   150,  # $150/day per diem only
    "cost_contractor_incremental": 500,  # $500/day — 100% new spend

    # --- SLA failure exposure rates (estimated cost per missed claim) ---
    # NOT contractual penalties. Modeled risk: customer retention, complaint
    # escalation, regulatory exposure, and potential bad-faith litigation.
    "sla_failure_cost": {5: 5000, 4: 2500, 3: 1000, 2: 500, 1: 100},

    # --- Mobilization delays (days before adjuster can start working) ---
    "delay_local":      0,
    "delay_deployed":   0,   # pre-positioned before storm: deployed staff on site Day 1
    "delay_contractor": 2,   # reactive mid-event hires only

    # --- PL0 boost ---
    "pl0_boost_factor":    1.20,  # 20% throughput multiplier for paired mentor
    "pl0_min_mentor_skill": 4,    # only PL4+ can be PL0 mentors

    # --- Drive penalty ---
    # Baseline: up to 2.5 hours drive = no penalty
    # After baseline: -20% per additional 30 min
    # Floor: 10% of base rate (penalty capped at 0.90)
    "drive_speed_kmh":      105,   # assumed average speed (65 mph)
    "drive_baseline_hours": 2.5,   # hours before penalty kicks in
    "drive_penalty_step":   0.20,  # penalty per 30-min increment
    "drive_step_minutes":   30,    # increment size in minutes
    "drive_penalty_floor":  0.10,  # minimum remaining productivity (10%)

    # --- Over-qualification penalty ---
    # Discourages PL5 adjusters from taking Sev-4 and below work.
    # Preserves PL5 capacity for Sev-5 claims (where only PL4+ are eligible).
    "over_qualify_penalty": 0.40,

    # --- Virtual claim soft penalty in MIP objective ---
    # Strongly discourages in-cluster adjusters from taking virtual claims.
    "virtual_incluster_penalty": 0.60,

    # --- Will Travel = N soft penalty ---
    # Applied only when: on-site claim, different cluster, will_travel = False.
    "will_travel_penalty": 0.30,

    # --- Contractor trigger ---
    # Request contractors when unassigned claim is within N days of SLA deadline
    "contractor_trigger_days": 3,

    # --- Supplementary state-to-cluster mapping ---
    # States with no usable claims (zero claims or all NA severity).
    # Claims-derived mapping always takes precedence; this fills gaps only.
    "supplementary_state_cluster": {
        "SC": "0",  # Carolinas cluster (with NC)
        "LA": "5",  # Gulf cluster (with MS) — 7 claims but all NA severity
        "DC": "4",  # Mid-Atlantic cluster (with MD/VA)
        "DE": "4",  # Mid-Atlantic cluster
        "NH": "6",  # New England cluster (with CT/MA)
        "VT": "6",  # New England cluster
        "ME": "6",  # New England cluster
        "RI": "6",  # New England cluster
    },

    # --- Simulation seed (for handle type randomization) ---
    "seed": 7900,

    # --- Claims file column name mapping ---
    # Change these when running a different CAT event with different CSV column names.
    "claims_cols": {
        "claim_id":        "Claim Number",
        "loss_date":       "Loss Date",
        "nol_date":        "NOL Date",
        "state":           "Accident State",
        "city":            "Accident City",
        "zip":             "Accident Zip",
        "peril":           "Peril Group",
        "weather_text":    "Weather Text",
        "cluster_id":      "7_cluster_cluster_id",
        "distance_km":     "7_cluster_distance_to_centroid_km",
        "severity":        "Final_Severity",
        "severity_source": "Severity_Source",
    },

    # --- Roster file column name mapping ---
    "roster_cols": {
        "adj_id":        "TIES Id",
        "location":      "Location",
        "skill":         "PL Skill Level",
        "will_travel":   "Will Travel",
        "tour_length":   "Preferred Tour Length",
        "resource_type": "WFM Resource Type Desc",
        "org_group":     "Org Group",
        "event_id":      "Event Id",
        "qtr_rank":      "Qtr Rank Id",
    },

    # --- MIP solver settings ---
    "mip_gap":              0.02,   # 2% optimality gap
    "mip_time_limit":       60,     # seconds per daily solve
    "decompose_by_cluster": True,   # solve each cluster's MIP independently
}


def validate_config(cfg: dict) -> bool:
    """Validate a config dict. Raises AssertionError on any violation."""
    tp = cfg["throughput"]
    assert isinstance(tp, dict),                       "throughput must be a dict"
    assert len(tp) == 6,                               "throughput must have 6 skill rows (PL0–PL5)"
    assert all(len(v) == 5 for v in tp.values()),      "throughput must have 5 severity cols (Sev1–Sev5)"

    sev_keys = {1, 2, 3, 4, 5}
    assert set(cfg["sla_days"].keys())       == sev_keys, "sla_days must cover severities 1–5"
    assert set(cfg["onsite_prob"].keys())    == sev_keys, "onsite_prob must cover severities 1–5"
    assert set(cfg["severity_weight"].keys())== sev_keys, "severity_weight must cover severities 1–5"
    assert set(cfg["min_skill"].keys())      == sev_keys, "min_skill must cover severities 1–5"

    assert cfg["pl0_boost_factor"] >= 1.0,   "pl0_boost_factor must be >= 1.0"
    assert 0 < cfg["drive_penalty_floor"] <= 1, "drive_penalty_floor must be in (0, 1]"

    cc = cfg["claims_cols"]
    for key in ("claim_id", "nol_date", "state", "cluster_id", "distance_km", "severity"):
        assert cc.get(key), f"claims_cols missing required key: {key}"

    rc = cfg["roster_cols"]
    for key in ("adj_id", "location", "skill"):
        assert rc.get(key), f"roster_cols missing required key: {key}"

    return True
