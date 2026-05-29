# simulator.py — Day-by-day simulation loop for CATOPT.
# Implements the wave trigger, PL0 boost pairing, and MIP assignment each day.
#
# assignment must be imported FIRST — it registers ortools' bundled DLLs on
# Windows before pandas loads its own C extensions (which can otherwise cause
# a DLL version conflict that breaks the ortools WinDLL load).

from assignment import solve_daily_assignment  # noqa: E402 — must be first
import math
import copy
import pandas as pd


# ---------------------------------------------------------------------------
# Wave classification helpers
# ---------------------------------------------------------------------------

_WAVE1_TYPES = {"FRT (Property)", "CAT"}
_ERT_NONFIELD = "ERT (Non Field)"

def _classify_wave(resource_type: str) -> int:
    rt = str(resource_type).strip()
    if rt in _WAVE1_TYPES:
        return 1
    return 2  # ERT Field and ERT Non Field


# ---------------------------------------------------------------------------
# Main simulation
# ---------------------------------------------------------------------------

def simulate(claims_df: pd.DataFrame,
             roster_df: pd.DataFrame,
             config: dict,
             pl0_boost: bool = False,
             distance_lookup: dict = None) -> dict:
    """
    Run a full day-by-day simulation.

    Parameters
    ----------
    claims_df  : DataFrame from load_claims()
    roster_df  : DataFrame from load_roster()
    config     : default_config dict
    pl0_boost  : if True, pair PL0s with PL4/PL5 mentors (+20% throughput)

    Returns
    -------
    dict with keys: summary, assignments, daily_log
    """
    throughput  = config["throughput"]
    sla_days    = config["sla_days"]
    boost_factor = config["pl0_boost_factor"]

    # ------------------------------------------------------------------
    # Build adjuster state list (deep copy so we don't mutate the DataFrame)
    # ------------------------------------------------------------------
    adjusters = []
    for _, row in roster_df.iterrows():
        wave = _classify_wave(row.get("resource_type", ""))
        adj = {
            "adj_id":        int(row["adj_id"]),
            "skill":         int(row["skill"]),
            "boosted":       False,
            "resource_type": str(row.get("resource_type", "")),
            "wave":          wave,
            "wave_available_day": 1 if wave == 1 else 999,
            "qtr_rank":      int(row.get("qtr_rank", 0)),
            "home_state":    row.get("state") or "Unknown",
            "current_state": row.get("state") or "Unknown",
            "status":        "free",
            "current_claim": None,
            "day_free":      1,
        }
        adjusters.append(adj)

    adj_by_id = {a["adj_id"]: a for a in adjusters}

    # ------------------------------------------------------------------
    # PL0 Boost pairing (Run 2 only)
    # Pair PL0 adjusters with PL4/PL5 mentors; mentor throughput *= 1.2
    # ------------------------------------------------------------------
    if pl0_boost:
        mentors = sorted(
            [a for a in adjusters if a["skill"] >= 4],
            key=lambda a: (-a["skill"], a["adj_id"])
        )
        pl0s = [a for a in adjusters if a["skill"] == 0]
        for pl0, mentor in zip(pl0s, mentors):
            mentor["boosted"] = True
        print(f"  PL0 boost: {min(len(pl0s), len(mentors))} mentors boosted "
              f"({len(mentors)} available, {len(pl0s)} PL0s)")

    # ------------------------------------------------------------------
    # Build claim state list
    # ------------------------------------------------------------------
    claims = []
    for _, row in claims_df.iterrows():
        day_arr  = int(row["day_arrived"])
        sev      = int(row["severity"])
        deadline = day_arr + sla_days[sev] - 1
        claim = {
            "claim_id":    int(row["claim_id"]),
            "severity":    sev,
            "state":       str(row.get("state", "")) if pd.notna(row.get("state")) else "",
            "handle_type": str(row.get("handle_type", "On-site")),
            "day_arrived": day_arr,
            "sla_deadline": deadline,
            "status":       "not_arrived",
            "assigned_adj": None,
            "adj_skill":    None,
            "day_assigned": None,
            "day_completed": None,
            "sla_met":      None,
            "progress":     0.0,
        }
        claims.append(claim)

    claim_by_id = {c["claim_id"]: c for c in claims}

    # ------------------------------------------------------------------
    # Simulation state
    # ------------------------------------------------------------------
    ert_activated      = False
    ert_activated_day  = None
    daily_log          = []
    assignment_records = []

    MAX_DAY = 60  # hard ceiling — shouldn't be reached

    for day in range(1, MAX_DAY + 1):

        # ---- 1. CLAIMS ARRIVE ----------------------------------------
        for c in claims:
            if c["status"] == "not_arrived" and c["day_arrived"] == day:
                c["status"] = "waiting"

        # ---- 2. WAVE CHECK -------------------------------------------
        sev5_waiting  = sum(1 for c in claims
                            if c["status"] == "waiting" and c["severity"] == 5)
        total_waiting = sum(1 for c in claims if c["status"] == "waiting")

        if not ert_activated and (sev5_waiting > 10 or total_waiting > 100):
            ert_activated     = True
            ert_activated_day = day
            for a in adjusters:
                if a["wave"] == 2:
                    a["wave_available_day"] = day + 1
            print(f"  Day {day}: ERT wave triggered "
                  f"(Sev5 waiting={sev5_waiting}, total waiting={total_waiting})")

        # ---- 3. PROGRESS (working adjusters) -------------------------
        newly_freed = []
        for a in adjusters:
            if a["status"] != "working":
                continue
            c = claim_by_id[a["current_claim"]]
            rate = throughput[a["skill"]][c["severity"]]
            if rate is None:
                continue
            if a["boosted"]:
                rate *= boost_factor

            c["progress"] += rate

            if c["progress"] >= 1.0:
                # Claim complete
                c["status"]        = "completed"
                c["day_completed"] = day
                c["sla_met"]       = (day <= c["sla_deadline"])

                a["status"]        = "free"
                a["current_state"] = c["state"]
                a["current_claim"] = None
                a["day_free"]      = day + 1  # one transition day
                newly_freed.append(a["adj_id"])

        # ---- 4. SLA CHECK (mark missed, keep in queue) ---------------
        for c in claims:
            if c["status"] == "waiting" and day > c["sla_deadline"]:
                if c["sla_met"] is None:
                    c["sla_met"] = False  # pre-mark; still needs work

        # ---- 5. MIP ASSIGNMENT ---------------------------------------
        free_adjs = [
            a for a in adjusters
            if a["status"] == "free"
            and a["skill"] > 0
            and day >= a["wave_available_day"]
            and day >= a["day_free"]
        ]
        open_claims = [c for c in claims if c["status"] == "waiting"]

        assignments = solve_daily_assignment(free_adjs, open_claims, config, day, distance_lookup)

        # ---- 6. PROCESS ASSIGNMENTS (with early-day diagnostics) --------
        if day <= 20:
            sev5_waiting_now = sum(1 for c in claims
                                   if c["status"] == "waiting" and c["severity"] == 5)
            pl5_free_now     = sum(1 for a in free_adjs if a["skill"] == 5)
            adj_map          = {a["adj_id"]: a for a in free_adjs}

            pl5_to_sev5  = sum(1 for aid, cid in assignments
                               if adj_map.get(aid, {}).get("skill") == 5
                               and claim_by_id[cid]["severity"] == 5)
            pl5_to_other = sum(1 for aid, cid in assignments
                               if adj_map.get(aid, {}).get("skill") == 5
                               and claim_by_id[cid]["severity"] != 5)
            pl4_to_sev5  = sum(1 for aid, cid in assignments
                               if adj_map.get(aid, {}).get("skill") == 4
                               and claim_by_id[cid]["severity"] == 5)

            print(f"    [D{day:02d}] Sev5 waiting={sev5_waiting_now:3d}  "
                  f"PL5 free={pl5_free_now:2d}  "
                  f"PL5->Sev5={pl5_to_sev5:2d}  PL5->other={pl5_to_other:2d}  "
                  f"PL4->Sev5={pl4_to_sev5:2d}")

        for adj_id, claim_id in assignments:
            a = adj_by_id[adj_id]
            c = claim_by_id[claim_id]

            a["status"]        = "working"
            a["current_claim"] = claim_id
            c["status"]        = "in_progress"
            c["assigned_adj"]  = adj_id
            c["adj_skill"]     = a["skill"]
            c["day_assigned"]  = day

            # Record for output DataFrame
            assignment_records.append({
                "day":       day,
                "adj_id":    adj_id,
                "claim_id":  claim_id,
                "skill":     a["skill"],
                "boosted":   a["boosted"],
                "severity":  c["severity"],
                "sla_deadline": c["sla_deadline"],
                "adj_state": a["current_state"],
                "claim_state": c["state"],
            })

            # Work starts the day of assignment — no mobilization delay.
            # Throughput rates already account for travel/setup overhead.
            rate = throughput[a["skill"]][c["severity"]]
            if a["boosted"]:
                rate *= boost_factor
            c["progress"] += rate
            if c["progress"] >= 1.0:
                c["status"]        = "completed"
                c["day_completed"] = day
                c["sla_met"]       = (day <= c["sla_deadline"])
                a["status"]        = "free"
                a["current_state"] = c["state"]
                a["current_claim"] = None
                a["day_free"]      = day + 1

        # ---- 7. DAILY LOG --------------------------------------------
        completed_today = sum(1 for c in claims
                              if c["status"] == "completed" and c["day_completed"] == day)
        in_progress     = sum(1 for c in claims if c["status"] == "in_progress")
        waiting_now     = sum(1 for c in claims if c["status"] == "waiting")
        total_done      = sum(1 for c in claims if c["status"] == "completed")

        log_entry = {
            "day":             day,
            "new_assignments": len(assignments),
            "completed_today": completed_today,
            "in_progress":     in_progress,
            "waiting":         waiting_now,
            "total_completed": total_done,
        }

        # Per-severity detail columns
        assigned_cids = {cid for _, cid in assignments}
        for sev in [1, 2, 3, 4, 5]:
            log_entry[f"sev{sev}_assigned"] = sum(
                1 for cid in assigned_cids if claim_by_id[cid]["severity"] == sev)
            log_entry[f"sev{sev}_waiting"] = sum(
                1 for c in claims if c["status"] == "waiting" and c["severity"] == sev)
            log_entry[f"sev{sev}_sla_met_cumulative"] = sum(
                1 for c in claims
                if c["status"] == "completed" and c["sla_met"] is True and c["severity"] == sev)

        daily_log.append(log_entry)

        print(f"  Day {day:2d}: assigned={len(assignments):3d}  "
              f"completed={completed_today:3d}  "
              f"in_progress={in_progress:3d}  "
              f"waiting={waiting_now:3d}  "
              f"done={total_done:4d}/{len(claims)}")

        # ---- STOP CHECK ----------------------------------------------
        remaining = sum(1 for c in claims
                        if c["status"] in ("waiting", "in_progress", "not_arrived"))
        if remaining == 0:
            print(f"  All claims resolved on Day {day}.")
            break

    # ------------------------------------------------------------------
    # Build summary
    # ------------------------------------------------------------------
    days_to_complete = next(
        (log["day"] for log in reversed(daily_log) if log["completed_today"] > 0),
        MAX_DAY
    )

    by_severity = {}
    for sev in [5, 4, 3, 2, 1]:
        sev_claims = [c for c in claims if c["severity"] == sev]
        met    = sum(1 for c in sev_claims if c["sla_met"] is True)
        missed = sum(1 for c in sev_claims if c["sla_met"] is False)
        total  = len(sev_claims)
        pct    = 100.0 * met / total if total > 0 else 0.0
        by_severity[f"sev{sev}"] = {
            "total":  total,
            "met":    met,
            "missed": missed,
            "pct":    round(pct, 1),
        }

    all_met    = sum(1 for c in claims if c["sla_met"] is True)
    all_missed = sum(1 for c in claims if c["sla_met"] is False)
    overall    = 100.0 * all_met / len(claims) if claims else 0.0

    summary = {
        "total_claims":       len(claims),
        "sla_met":            all_met,
        "sla_missed":         all_missed,
        "overall_compliance": round(overall, 1),
        "by_severity":        by_severity,
        "days_to_complete":   days_to_complete,
        "ert_activated_day":  ert_activated_day,
    }

    # Enrich assignment records with completion info (post-loop, claim state is final)
    claim_done = {c["claim_id"]: (c["day_completed"], c["sla_met"]) for c in claims}
    for rec in assignment_records:
        comp_day, met = claim_done.get(rec["claim_id"], (None, None))
        rec["completion_day"]    = comp_day
        rec["sla_met"]           = bool(met) if met is not None else False
        rec["days_to_complete"]  = (comp_day - rec["day"]) if comp_day is not None else None

    assignments_df = pd.DataFrame(assignment_records) if assignment_records else pd.DataFrame()
    daily_log_df   = pd.DataFrame(daily_log)
    claims_detail_df = pd.DataFrame([
        {"claim_id": c["claim_id"], "severity": c["severity"],
         "sla_met": c["sla_met"], "day_completed": c["day_completed"],
         "sla_deadline": c["sla_deadline"]}
        for c in claims
    ])

    return {
        "summary":       summary,
        "assignments":   assignments_df,
        "daily_log":     daily_log_df,
        "claims_detail": claims_detail_df,
    }
