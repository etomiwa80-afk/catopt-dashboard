# main.py — CATOPT Python: load data, run simulation (Run 1 + Run 2), print results.
# Geocodes adjusters and claims; builds distance lookup (adj_id, claim_id) -> miles.
# Distance used as tiebreaker in solver only — never overrides SLA priority.
# Exports: catopt_run{1,2}_daily.csv, catopt_run{1,2}_assignments.csv
#   assignments include: distance_miles, drive_hours (1.3x detour / 105 km/h)

import os, sys

# Windows: register ortools DLLs before any C-extension import
if sys.platform == "win32":
    for _sp in sys.path:
        _d = os.path.normpath(os.path.join(_sp, "ortools", ".libs"))
        if os.path.isdir(_d):
            os.add_dll_directory(_d)
            break

import numpy as np
from config    import default_config, validate_config
from load_data import load_claims, load_roster
from simulator import simulate
from geocode   import geocode_claims, geocode_adjusters

DATA_DIR    = os.getenv("DATA_DIR", "data")
CLAIMS_FILE = os.path.join(DATA_DIR, "claims.csv")
ROSTER_FILE = os.path.join(DATA_DIR, "roster.xlsx")

if __name__ == "__main__":
    cfg = default_config
    validate_config(cfg)

    claims = load_claims(CLAIMS_FILE, cfg)
    roster = load_roster(ROSTER_FILE, cfg)

    # ------------------------------------------------------------------
    # Geocode and build distance lookup (adj_id, claim_id) -> miles
    # Used as a tiebreaker in the solver — never overrides SLA priority.
    # ------------------------------------------------------------------
    print("\nGeocoding adjusters and claims...")
    claims_geo = geocode_claims(claims)
    roster_geo = geocode_adjusters(roster)

    _R_MI = 3958.8  # Earth radius in miles
    adj_coords   = roster_geo[["adj_id", "lat", "lng"]].dropna(subset=["lat", "lng"])
    claim_coords = claims_geo[["claim_id", "lat", "lng"]].dropna(subset=["lat", "lng"])

    adj_lat_r = np.radians(adj_coords["lat"].values)[:, np.newaxis]   # (A,1)
    adj_lng_r = np.radians(adj_coords["lng"].values)[:, np.newaxis]
    clm_lat_r = np.radians(claim_coords["lat"].values)[np.newaxis, :] # (1,C)
    clm_lng_r = np.radians(claim_coords["lng"].values)[np.newaxis, :]
    dlat  = clm_lat_r - adj_lat_r
    dlon  = clm_lng_r - adj_lng_r
    a_h   = (np.sin(dlat / 2) ** 2
             + np.cos(adj_lat_r) * np.cos(clm_lat_r) * np.sin(dlon / 2) ** 2)
    mi_matrix = 2 * _R_MI * np.arcsin(np.sqrt(np.clip(a_h, 0, 1)))   # (A,C)

    adj_ids  = adj_coords["adj_id"].values
    clm_ids  = claim_coords["claim_id"].values
    ai_flat  = np.repeat(adj_ids, len(clm_ids))
    ci_flat  = np.tile(clm_ids, len(adj_ids))
    mi_flat  = mi_matrix.ravel()
    distance_lookup = {(int(a), int(c)): float(m)
                       for a, c, m in zip(ai_flat, ci_flat, mi_flat)}
    print(f"Distance lookup built: {len(distance_lookup):,} adj-claim pairs")

    # distance.py constants: detour factor 1.3, speed 105 km/h, 1 mi = 1.60934 km
    # drive_hours = miles * 1.60934 * 1.3 / 105
    _MI_TO_DRIVE_H = 1.60934 * 1.3 / 105.0   # ≈ 0.01993 h/mi

    # Helper to attach distance_miles and drive_hours columns to an assignments DataFrame
    def _add_distance_col(df):
        if df.empty:
            return df
        df = df.copy()
        df["distance_miles"] = df.apply(
            lambda r: round(distance_lookup.get((int(r["adj_id"]), int(r["claim_id"])), 500), 1),
            axis=1,
        )
        df["drive_hours"] = (df["distance_miles"] * _MI_TO_DRIVE_H).round(2)
        return df

    print()
    print("=== Summary ===")
    print(f"Claims: {len(claims)} rows, "
          f"Sev5: {(claims.severity==5).sum()}, "
          f"Sev4: {(claims.severity==4).sum()}, "
          f"Sev3: {(claims.severity==3).sum()}, "
          f"Sev2: {(claims.severity==2).sum()}, "
          f"Sev1: {(claims.severity==1).sum()}")
    print(f"Roster: {len(roster)} adjusters, "
          f"PL5: {(roster.skill==5).sum()}, "
          f"PL4: {(roster.skill==4).sum()}, "
          f"PL3: {(roster.skill==3).sum()}, "
          f"PL2: {(roster.skill==2).sum()}, "
          f"PL1: {(roster.skill==1).sum()}, "
          f"PL0: {(roster.skill==0).sum()}")

    # =======================================================================
    # RUN 1 — No PL0 boost
    # =======================================================================
    print()
    print("=" * 60)
    print("RUN 1 — No PL0 boost")
    print("=" * 60)
    run1 = simulate(claims, roster, cfg, pl0_boost=False, distance_lookup=distance_lookup)

    # =======================================================================
    # RUN 2 — PL0 boost
    # =======================================================================
    print()
    print("=" * 60)
    print("RUN 2 — PL0 boost")
    print("=" * 60)
    run2 = simulate(claims, roster, cfg, pl0_boost=True, distance_lookup=distance_lookup)

    # =======================================================================
    # RUN 3 — PL3->PL4 upgrade scenario (top 30 PL3 by qtr_rank, then boosted)
    # Approved scenario: upgrade 30 best PL3s to PL4.
    # PL0 supply (158) covers 104 existing + 30 upgraded = 134 mentor pairs.
    # Boosted PL4 on Sev-5: 0.125 * 1.2 = 0.15/day -> 7 days = exactly SLA.
    # =======================================================================
    print()
    print("=" * 60)
    print("RUN 3 — PL3->PL4 upgrade (top 30 PL3 by qtr_rank) + PL0 boost")
    print("=" * 60)

    import pandas as pd
    roster_run3 = roster.copy()
    pl3_idx = (roster_run3[roster_run3["skill"] == 3]
               .sort_values(["qtr_rank", "adj_id"], ascending=[False, True])
               .head(30)
               .index)
    roster_run3.loc[pl3_idx, "skill"] = 4
    n_pl4_new = (roster_run3["skill"] == 4).sum()
    n_pl5     = (roster_run3["skill"] == 5).sum()
    print(f"  Upgraded 30 PL3 -> PL4  |  New PL4 total: {n_pl4_new}  "
          f"(PL5: {n_pl5}, mentors available: {n_pl4_new + n_pl5})")

    run3 = simulate(claims, roster_run3, cfg, pl0_boost=True, distance_lookup=distance_lookup)

    # =======================================================================
    # RESULTS
    # =======================================================================
    print()
    print("=" * 60)
    print("RESULTS")
    print("=" * 60)
    for name, run in [("Run 1 (no boost)", run1), ("Run 2 (PL0 boost)", run2), ("Run 3 (PL3->PL4 upgrade + boost)", run3)]:
        s = run["summary"]
        print(f"\n{name}:")
        print(f"  Overall SLA:  {s['sla_met']}/{s['total_claims']}  ({s['overall_compliance']:.1f}%)")
        for sev in [5, 4, 3, 2, 1]:
            sv = s["by_severity"][f"sev{sev}"]
            print(f"  Sev-{sev}: {sv['met']:3d}/{sv['total']:3d}  ({sv['pct']:.1f}%)")
        print(f"  Days to complete: {s['days_to_complete']}")
        print(f"  ERT activated:    Day {s['ert_activated_day']}")

        # Sev-5 breakdown by adjuster skill (sla_met now on assignments directly)
        if not run["assignments"].empty:
            import pandas as pd
            s5 = run["assignments"][run["assignments"]["severity"] == 5]
            print(f"  Sev-5 by adjuster skill:")
            for sk in [5, 4]:
                rows = s5[s5["skill"] == sk]
                if len(rows) == 0:
                    continue
                met = rows["sla_met"].sum()
                print(f"    PL{sk}: {len(rows):3d} assigned, {int(met):3d} SLA-met")

    # =======================================================================
    # DAILY LOG
    # =======================================================================
    print()
    print("=" * 60)
    print("DAILY LOG — Run 1 (no boost)")
    print("=" * 60)
    print(run1["daily_log"].to_string(index=False))

    print()
    print("=" * 60)
    print("DAILY LOG — Run 2 (PL0 boost)")
    print("=" * 60)
    print(run2["daily_log"].to_string(index=False))

    print()
    print("=" * 60)
    print("DAILY LOG — Run 3 (PL3->PL4 upgrade + boost)")
    print("=" * 60)
    print(run3["daily_log"].to_string(index=False))

    # Save CSVs — daily logs
    run1["daily_log"].to_csv(os.path.join(DATA_DIR, "catopt_run1_daily.csv"), index=False)
    run2["daily_log"].to_csv(os.path.join(DATA_DIR, "catopt_run2_daily.csv"), index=False)
    run3["daily_log"].to_csv(os.path.join(DATA_DIR, "catopt_run3_daily.csv"), index=False)
    print(f"\nDaily logs saved to {DATA_DIR}\\catopt_run1/2/3_daily.csv")

    # Save CSVs — adjuster assignment detail (who worked what, which day)
    # Attach distance_miles column before export.
    r1_asgn = _add_distance_col(run1["assignments"])
    r2_asgn = _add_distance_col(run2["assignments"])
    r3_asgn = _add_distance_col(run3["assignments"])

    if not r1_asgn.empty:
        r1_asgn.to_csv(os.path.join(DATA_DIR, "catopt_run1_assignments.csv"), index=False)
    if not r2_asgn.empty:
        r2_asgn.to_csv(os.path.join(DATA_DIR, "catopt_run2_assignments.csv"), index=False)
    if not r3_asgn.empty:
        r3_asgn.to_csv(os.path.join(DATA_DIR, "catopt_run3_assignments.csv"), index=False)
    print(f"Assignments saved to {DATA_DIR}\\catopt_run1/2/3_assignments.csv")

    # Average deployment distance summary
    for name, df in [("Run 1", r1_asgn), ("Run 2", r2_asgn), ("Run 3", r3_asgn)]:
        if not df.empty and "distance_miles" in df.columns:
            avg = df["distance_miles"].mean()
            med = df["distance_miles"].median()
            print(f"  {name} avg deployment distance: {avg:.0f} miles  (median {med:.0f} miles)")

    # =======================================================================
    # VALIDATION CHECKS
    # =======================================================================
    print()
    print("=" * 60)
    print("VALIDATION")
    print("=" * 60)

    def _check(label, condition, note=""):
        print(f"  [{'PASS' if condition else 'FAIL'}] {label}" + (f"  ({note})" if note else ""))

    if not run1["assignments"].empty and not run2["assignments"].empty:
        a1 = run1["assignments"]
        a2 = run2["assignments"]

        _check("PL0 assigned to claims = 0 (Run 1)",
               (a1["skill"] == 0).sum() == 0,
               f"got {(a1['skill']==0).sum()}")

        _check("PL3 assigned to Sev-5 = 0 (Run 1)",
               ((a1["skill"] == 3) & (a1["severity"] == 5)).sum() == 0,
               f"got {((a1['skill']==3)&(a1['severity']==5)).sum()}")

        unboosted_pl4_sev5 = ((a1["skill"] == 4) & (a1["severity"] == 5) & (~a1["boosted"])).sum()
        _check("Unboosted PL4 on Sev-5 = 0 (Run 1)",
               unboosted_pl4_sev5 == 0,
               f"got {unboosted_pl4_sev5}")

        r1_sev5 = run1["summary"]["by_severity"]["sev5"]["pct"]
        r2_sev5 = run2["summary"]["by_severity"]["sev5"]["pct"]
        r3_sev5 = run3["summary"]["by_severity"]["sev5"]["pct"]
        _check("Run 2 Sev-5 >= Run 1 Sev-5",
               r2_sev5 >= r1_sev5,
               f"Run1={r1_sev5:.1f}%  Run2={r2_sev5:.1f}%")
        _check("Run 3 Sev-5 >= Run 2 Sev-5 (upgrade benefit)",
               r3_sev5 >= r2_sev5,
               f"Run2={r2_sev5:.1f}%  Run3={r3_sev5:.1f}%")

        a3 = run3["assignments"]
        upgraded_ids = set(roster_run3.loc[pl3_idx, "adj_id"])
        upgraded_on_sev5 = ((a3["adj_id"].isin(upgraded_ids)) & (a3["severity"] == 5)).sum()
        _check("Upgraded PL3->PL4 working Sev-5 in Run 3",
               upgraded_on_sev5 > 0,
               f"got {upgraded_on_sev5} assignments")

        r1_sev1 = run1["summary"]["by_severity"]["sev1"]["pct"]
        _check("All Sev-1 met SLA (Run 1)",
               r1_sev1 == 100.0,
               f"got {r1_sev1:.1f}%")

    day3 = (claims["day_arrived"] == 3).sum()
    _check("Day 3 arrivals ~359", 350 <= day3 <= 370, f"got {day3}")
    _check("Total claims = 1054", len(claims) == 1054, f"got {len(claims)}")
