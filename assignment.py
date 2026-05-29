# assignment.py — Daily assignment solver for CATOPT.
# Uses ortools min-cost flow for bipartite matching — orders of magnitude faster
# than CP-SAT for pure assignment problems at this scale (600+ adj x 1000+ claims).

import os
import math
import sys

# Windows: register ortools bundled DLLs before the package loads.
if os.name == "nt":
    for _sp in sys.path:
        _d = os.path.normpath(os.path.join(_sp, "ortools", ".libs"))
        if os.path.isdir(_d):
            os.add_dll_directory(_d)
            break

from ortools.graph.python import min_cost_flow


def solve_daily_assignment(free_adjusters, open_claims, config, day, distance_lookup=None):
    """
    Assign adjusters to claims for the given simulation day.

    Uses min-cost flow (equivalent to optimal bipartite matching):
      - Source → each free adjuster (capacity 1, cost 0)
      - Each adjuster → each feasible claim (capacity 1, cost = -priority)
      - Each claim → sink (capacity 1, cost 0)

    Parameters
    ----------
    free_adjusters : list of adjuster dicts
    open_claims    : list of claim dicts
    config         : default_config dict
    day            : current simulation day (int)

    Returns
    -------
    list of (adj_id, claim_id) tuples
    """
    if not free_adjusters or not open_claims:
        return []

    throughput     = config["throughput"]
    sev_weight     = config["severity_weight"]
    qtr_rank_bonus = config["qtr_rank_bonus"]
    boost_factor   = config["pl0_boost_factor"]

    # ------------------------------------------------------------------
    # Node layout:
    #   0          = source
    #   1..A       = adjuster nodes
    #   A+1..A+C   = claim nodes
    #   A+C+1      = sink
    # ------------------------------------------------------------------
    A      = len(free_adjusters)
    C      = len(open_claims)
    SOURCE = 0
    SINK   = A + C + 1

    tail_nodes = []
    head_nodes = []
    capacities = []
    unit_costs = []

    # Source → adjuster edges
    for i in range(A):
        tail_nodes.append(SOURCE)
        head_nodes.append(i + 1)
        capacities.append(1)
        unit_costs.append(0)

    # Claim → sink edges
    for j in range(C):
        tail_nodes.append(A + 1 + j)
        head_nodes.append(SINK)
        capacities.append(1)
        unit_costs.append(0)

    # Adjuster → claim edges (feasible pairs only)
    feasible_edges = []  # (edge_index, i, j)

    for i, adj in enumerate(free_adjusters):
        skill   = adj["skill"]
        boosted = adj["boosted"]
        rt      = adj.get("resource_type", "")
        a_state = adj.get("current_state") or adj.get("home_state")

        if skill == 0:
            continue

        for j, claim in enumerate(open_claims):
            sev      = claim["severity"]
            c_state  = claim.get("state", "")
            deadline = claim["sla_deadline"]
            h_type   = claim.get("handle_type", "On-site")

            # CAT event: all adjusters go on-site regardless of resource type.
            # Non-Field classification is a normal-ops preference, not a CAT rule.

            base_rate = throughput.get(skill, {}).get(sev)
            if base_rate is None:
                continue

            effective_rate = base_rate * boost_factor if boosted else base_rate
            days_needed    = math.ceil(1.0 / effective_rate)
            finish_day     = day + days_needed - 1

            already_missed = day > deadline
            will_miss      = (not already_missed) and (finish_day > deadline)

            urgency    = 1000 // max(1, deadline - day)
            rank_bonus = int(qtr_rank_bonus.get(adj.get("qtr_rank", 0), 1.0) * 100)
            priority   = sev_weight[sev] * urgency * rank_bonus

            # PL5 hard ban from Sev < 5 — reserved entirely for Sev-5 work.
            if skill == 5 and sev < 5:
                continue

            # Priority tiers:
            #   feasible (on time)  → full priority
            #   will-miss (late finish but work gets done) → 1/3 priority
            #     PL4 on Sev-5 in Run 1 lands here (8d > 7d SLA) — acceptable
            #   past-SLA (claim already expired) → 0.01x cleanup priority
            if already_missed:
                priority = max(1, priority // 100)
            elif will_miss:
                priority = max(1, priority // 3)

            # Sev-5 skill tiebreaker — feasible claims only.
            # Apply BEFORE will_miss/past-SLA tiers would invert the ordering.
            # will_miss claims with deadline==today get urgency=1000 (max), and
            # with 1/3 discount + skill multiplier they narrowly beat feasible
            # claims. Fix: only multiply by skill for pairs that can actually meet SLA.
            if sev == 5 and not already_missed and not will_miss:
                priority = priority * skill

            # Distance tiebreaker — closer adjuster slightly preferred.
            # Scaled so it NEVER overrides skill, urgency, tier, or rank ordering:
            # we multiply priority by 1000 (preserving all ordering) then add a
            # 0-1000 bonus for proximity. Two adjusters with equal priority will
            # be resolved by distance; a PL3 next door never beats a PL5 far away.
            if distance_lookup is not None:
                dist_mi    = distance_lookup.get((adj["adj_id"], claim["claim_id"]), 500)
                dist_bonus = max(0, 1000 - int(dist_mi))
                priority   = priority * 1000 + dist_bonus

            edge_idx = len(tail_nodes)
            tail_nodes.append(i + 1)
            head_nodes.append(A + 1 + j)
            capacities.append(1)
            unit_costs.append(-priority)  # negate: min cost = max priority

            feasible_edges.append((edge_idx, i, j))

    if not feasible_edges:
        return []

    # ------------------------------------------------------------------
    # Solve
    # ------------------------------------------------------------------
    smcf = min_cost_flow.SimpleMinCostFlow()
    for t, h, cap, cost in zip(tail_nodes, head_nodes, capacities, unit_costs):
        smcf.add_arc_with_capacity_and_unit_cost(t, h, cap, cost)

    # Flow must not exceed the maximum bipartite matching size.
    # When Hall's condition fails (e.g. more Sev5 claims than PL4+PL5 adjusters),
    # flow = min(A, C) is infeasible and forces a greedy fallback.
    adj_in_feasible   = len({i for _, i, _ in feasible_edges})
    claim_in_feasible = len({j for _, _, j in feasible_edges})
    flow = min(adj_in_feasible, claim_in_feasible)
    smcf.set_node_supply(SOURCE, flow)
    smcf.set_node_supply(SINK, -flow)

    status = smcf.solve()

    if status != smcf.OPTIMAL:
        return _greedy_fallback(free_adjusters, open_claims, feasible_edges, config, day, distance_lookup)

    # ------------------------------------------------------------------
    # Extract assignments
    # ------------------------------------------------------------------
    result = []
    for edge_idx, i, j in feasible_edges:
        if smcf.flow(edge_idx) == 1:
            result.append((free_adjusters[i]["adj_id"], open_claims[j]["claim_id"]))

    return result


def _greedy_fallback(free_adjusters, open_claims, feasible_edges, config, day, distance_lookup=None):
    """Greedy by priority — fallback if flow solver fails.
    Uses identical priority logic as the main loop (will_miss tiers + skill tiebreaker).
    """
    throughput     = config["throughput"]
    sev_weight     = config["severity_weight"]
    qtr_rank_bonus = config["qtr_rank_bonus"]
    boost_factor   = config["pl0_boost_factor"]

    scored = []
    for edge_idx, i, j in feasible_edges:
        adj      = free_adjusters[i]
        claim    = open_claims[j]
        skill    = adj["skill"]
        sev      = claim["severity"]
        deadline = claim["sla_deadline"]

        base_rate = throughput.get(skill, {}).get(sev)
        if base_rate is None:
            continue
        effective_rate = base_rate * boost_factor if adj["boosted"] else base_rate
        days_needed    = math.ceil(1.0 / effective_rate)
        finish_day     = day + days_needed - 1

        already_missed = day > deadline
        will_miss      = (not already_missed) and (finish_day > deadline)

        urgency    = 1000 // max(1, deadline - day)
        rank_bonus = int(qtr_rank_bonus.get(adj.get("qtr_rank", 0), 1.0) * 100)
        priority   = sev_weight[sev] * urgency * rank_bonus

        if already_missed:
            priority = max(1, priority // 100)
        elif will_miss:
            priority = max(1, priority // 3)

        if sev == 5 and not already_missed and not will_miss:
            priority = priority * skill

        if distance_lookup is not None:
            dist_mi    = distance_lookup.get((adj["adj_id"], claim["claim_id"]), 500)
            dist_bonus = max(0, 1000 - int(dist_mi))
            priority   = priority * 1000 + dist_bonus

        scored.append((priority, i, j))

    scored.sort(key=lambda x: -x[0])
    used_adj, used_claim, result = set(), set(), []
    for _, i, j in scored:
        if i not in used_adj and j not in used_claim:
            result.append((free_adjusters[i]["adj_id"], open_claims[j]["claim_id"]))
            used_adj.add(i)
            used_claim.add(j)
    return result
