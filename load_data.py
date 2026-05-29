# load_data.py — Load and prepare claims and roster data (Python port of load_data.R)
# All outputs are clean, typed DataFrames ready for geography and the MIP solver.

import random
import pandas as pd


# ---------------------------------------------------------------------------
# State name → 2-letter abbreviation
# ---------------------------------------------------------------------------

_STATE_ABBR = {
    "Alabama": "AL", "Alaska": "AK", "Arizona": "AZ", "Arkansas": "AR",
    "California": "CA", "Colorado": "CO", "Connecticut": "CT", "Delaware": "DE",
    "Florida": "FL", "Georgia": "GA", "Hawaii": "HI", "Idaho": "ID",
    "Illinois": "IL", "Indiana": "IN", "Iowa": "IA", "Kansas": "KS",
    "Kentucky": "KY", "Louisiana": "LA", "Maine": "ME", "Maryland": "MD",
    "Massachusetts": "MA", "Michigan": "MI", "Minnesota": "MN", "Mississippi": "MS",
    "Missouri": "MO", "Montana": "MT", "Nebraska": "NE", "Nevada": "NV",
    "New Hampshire": "NH", "New Jersey": "NJ", "New Mexico": "NM", "New York": "NY",
    "North Carolina": "NC", "North Dakota": "ND", "Ohio": "OH", "Oklahoma": "OK",
    "Oregon": "OR", "Pennsylvania": "PA", "Rhode Island": "RI", "South Carolina": "SC",
    "South Dakota": "SD", "Tennessee": "TN", "Texas": "TX", "Utah": "UT",
    "Vermont": "VT", "Virginia": "VA", "Washington": "WA", "West Virginia": "WV",
    "Wisconsin": "WI", "Wyoming": "WY",
    "District of Columbia": "DC", "Washington DC": "DC", "Washington, DC": "DC",
}


def _state_name_to_abbr(name: str) -> str:
    """Return 2-letter abbreviation; pass through if already 2 chars."""
    if pd.isna(name):
        return None
    name = str(name).strip()
    if len(name) == 2:
        return name.upper()
    return _STATE_ABBR.get(name, None)


# ---------------------------------------------------------------------------
# Location → state (CAT 82 built-in lookup)
# ---------------------------------------------------------------------------

_LOCATION_STATE = {
    "Charlotte-Carmel Commons":               "NC",
    "Raleigh":                                "NC",
    "South Carolina - Virtual":               "SC",
    "Durham - Emperor Blvd":                  "NC",
    "Alpharetta-Atlanta":                     "GA",
    "Birmingham-Hoover":                      "AL",
    "Wyomissing-Reading":                     "PA",
    "Blue Bell-Phil-Lakeview Dr":             "PA",
    "Philadelphia-Market St":                 "PA",
    "Pittsburgh-Washington Pl":               "PA",
    "Exton-Philadelphia-Eagleview":           "PA",
    "Morristown":                             "NJ",
    "Edison-343 Thornall":                    "NJ",
    "Marlton-Camden Law":                     "NJ",
    "New York City - Lexington Ave":          "NY",
    "Melville NY Corp Center Dr":             "NY",
    "Buffalo":                                "NY",
    "Rochester - Linden Oaks":               "NY",
    "Syracuse-Plainfield Rd":                 "NY",
    "Albany - Park Pl":                       "NY",
    "White Plains-Law1-Liability":            "NY",
    "Glens Falls - Queensbury":               "NY",
    "Franklin-Nashville":                     "TN",
    "Knoxville":                              "TN",
    "Memphis-6750 Poplar":                    "TN",
    "Louisville-Hurstbourne Pkwy":            "KY",
    "Hunt Valley-Baltimore-Schilling":        "MD",
    "Rosedale-Baltimore":                     "MD",
    "Chantilly-WashingtnDC-PkMeadow":        "VA",
    "Richmond-Mayland Dr":                   "VA",
    "Washington, DC - 13th Street":          "DC",
    "Delaware - Virtual":                     "DE",
    "Flowood-Jackson-Canebrake":              "MS",
    "Metairie-New Orleans-3900 Cswy":        "LA",
    "Hartford-Field":                         "CT",
    "Windsor-Htfd-99 Lambrtn-ClaimU":        "CT",
    "Hamden Law":                             "CT",
    "Hartford - Tower":                       "CT",
    "West Bridgewater":                       "MA",
    "Massachusetts - Virtual":               "MA",
    "Hudson - Boston":                        "MA",
    "Boston-Financial Center":               "MA",
    "Bedford - Commerce":                    "NH",
    "South Portland":                        "ME",
    "Vermont - Virtual":                     "VT",
    "Providence Law":                        "RI",
    "Naperville-Chicago":                    "IL",
    "Maryland Heights-St. Louis":           "MO",
    "Centennial-Denver-Geddes":             "CO",
    "Overland Pk-Kansas City-132 St":       "KS",
    "Phoenix-Tatum Blvd":                   "AZ",
    "Richardson-Dallas":                    "TX",
    "Houston - Westway":                    "TX",
    "San Antonio-McAllister Fwy":           "TX",
    "Austin-901 Mo-Pac":                    "TX",
    "Farmers Brnch-Dallas":                 "TX",
    "St. Paul":                             "MN",
    "Las Vegas-Arroyo Crossing":            "NV",
    "Walnut Creek-San Francisco-401":       "CA",
    "RanchoCordova-Sacramento-11090":       "CA",
    "Diamond Bar-Los Angeles":              "CA",
    "Glendale-LosAngeles-655NCentrl":       "CA",
    "Irvine-Los Angeles-Michelson":         "CA",
    "Fresno":                               "CA",
    "Walnut Creek-Pleasant Hill":           "CA",
    "San Diego":                            "CA",
    "Orange-Los Angeles-Law":               "CA",
    "Indianapolis - 96th St":               "IN",
    "Albuquerque-Lang Avenue":              "NM",
    "Omaha-Dodge Rd":                       "NE",
    "Brookfield-Milwaukee":                 "WI",
    "Oklahoma City Law":                    "OK",
    "Tulsa-5100 Skelly":                    "OK",
    "Independence-Cleveland":               "OH",
    "Columbus-Easton Oval":                 "OH",
    "Cincinnati-Elsinore":                  "OH",
    "Salt Lake City-1100 E 6600":           "UT",
    "West Des Moines-Jordan Creek":         "IA",
    "Troy-Detroit":                         "MI",
    "Portland":                             "OR",
    "Federal Way-Seattle-6th Ave":          "WA",
    "Spokane":                              "WA",
    "Orlando":                              "FL",
    "Lake Mary-Orlando":                    "FL",
    "Tampa - Dale Mabry":                   "FL",
    "Jacksonville Law":                     "FL",
    "Boise-Meridian":                       "ID",
    "North Dakota - Virtual":              "ND",
    "Little Rock":                          "AR",
    "Honolulu":                             "HI",
}


def _location_to_state(location: str) -> str:
    """Return state abbreviation for a roster location string."""
    if pd.isna(location):
        return None
    return _LOCATION_STATE.get(str(location).strip(), None)


# ---------------------------------------------------------------------------
# load_claims
# ---------------------------------------------------------------------------

def load_claims(claims_file: str, cfg: dict) -> pd.DataFrame:
    """
    Load and clean the claims CSV.

    Parameters
    ----------
    claims_file : path to the claims CSV
    cfg         : config dict (from config.default_config or custom)

    Returns
    -------
    pd.DataFrame with columns: claim_id, loss_date, nol_date, state, city,
        zip, peril, weather_text, cluster, distance_km, severity_raw, severity,
        severity_source, handle_type, status, assigned_to, day_arrived,
        day_assigned, day_completed, sla_deadline, sla_met
    """
    raw = pd.read_csv(claims_file, low_memory=False)
    cc  = cfg["claims_cols"]

    # Verify required columns
    required = [cc["claim_id"], cc["nol_date"], cc["state"],
                cc["cluster_id"], cc["distance_km"], cc["severity"]]
    missing = [c for c in required if c not in raw.columns]
    if missing:
        raise ValueError(
            f"Claims file missing required columns: {', '.join(missing)}\n"
            "Update cfg['claims_cols'] to match your file's column names."
        )

    def _opt(col_key):
        """Return column values if present, else a None series."""
        col = cc.get(col_key)
        if col and col in raw.columns:
            return raw[col]
        return pd.Series([None] * len(raw))

    claims = pd.DataFrame({
        "claim_id":       pd.to_numeric(raw[cc["claim_id"]], errors="coerce").astype("Int64"),
        "loss_date":      pd.to_datetime(_opt("loss_date"), errors="coerce"),
        "nol_date":       pd.to_datetime(raw[cc["nol_date"]], errors="coerce"),
        "state":          raw[cc["state"]].astype(str).str.strip().map(_state_name_to_abbr),
        "city":           _opt("city").astype(str).str.strip().replace("None", None),
        "zip":            _opt("zip").astype(str).replace("None", None),
        "peril":          _opt("peril").astype(str).str.strip().replace("None", None),
        "weather_text":   _opt("weather_text").astype(str).str.strip().replace("None", None),
        "cluster":        pd.to_numeric(raw[cc["cluster_id"]], errors="coerce").astype("Int64"),
        "distance_km":    pd.to_numeric(raw[cc["distance_km"]], errors="coerce"),
        "severity_raw":   pd.to_numeric(raw[cc["severity"]], errors="coerce"),
        "severity_source":_opt("severity_source").astype(str).str.strip().replace("None", None),
    })

    # Round 3.5 → 4 per spec; standard rounding for everything else
    def _round_severity(x):
        if pd.isna(x):
            return pd.NA
        if x == 3.5:
            return 4
        return int(round(x))

    claims["severity"] = claims["severity_raw"].map(_round_severity).astype("Int64")

    # Drop rows with NA or out-of-range severity
    claims = claims[claims["severity"].notna() & claims["severity"].isin([1, 2, 3, 4, 5])].copy()
    claims["severity"] = claims["severity"].astype(int)

    # Compute day_arrived as integer day offset from earliest NOL date (1-indexed)
    min_nol = claims["nol_date"].min()
    claims["day_arrived"] = ((claims["nol_date"] - min_nol).dt.days + 1).astype(int)

    # Assign handle types: randomized per severity group, reproducibly
    # Each group gets a unique seed: cfg['seed'] + severity
    handle_type = pd.Series(index=claims.index, dtype=str)
    onsite_prob = cfg["onsite_prob"]
    seed_base   = cfg["seed"]

    for sev, grp in claims.groupby("severity"):
        n         = len(grp)
        n_onsite  = round(onsite_prob[sev] * n)
        pool      = ["On-site"] * n_onsite + ["Virtual"] * (n - n_onsite)
        rng = random.Random(seed_base + sev)
        rng.shuffle(pool)
        handle_type.loc[grp.index] = pool

    claims["handle_type"] = handle_type

    # Simulation columns — initialized here, updated during simulation
    claims["status"]        = "Unassigned"
    claims["assigned_to"]   = pd.NA
    claims["day_assigned"]  = pd.NA
    claims["day_completed"] = pd.NA
    claims["sla_deadline"]  = pd.NA
    claims["sla_met"]       = pd.NA

    claims = claims.sort_values(["nol_date", "claim_id"]).reset_index(drop=True)

    print(f"Claims loaded: {len(claims)} rows (after removing NA severity)")
    print(f"  Sev5: {(claims.severity==5).sum()} | "
          f"Sev4: {(claims.severity==4).sum()} | "
          f"Sev3: {(claims.severity==3).sum()} | "
          f"Sev2: {(claims.severity==2).sum()} | "
          f"Sev1: {(claims.severity==1).sum()}")
    print(f"  On-site: {(claims.handle_type=='On-site').sum()} | "
          f"Virtual: {(claims.handle_type=='Virtual').sum()}")

    return claims


# ---------------------------------------------------------------------------
# load_roster
# ---------------------------------------------------------------------------

def load_roster(roster_file: str, cfg: dict,
                location_lookup_file: str = None) -> pd.DataFrame:
    """
    Load and clean the adjuster roster XLSX.

    Parameters
    ----------
    roster_file          : path to the roster .xlsx
    cfg                  : config dict
    location_lookup_file : optional CSV with columns [location, state]
                           for events other than CAT 82

    Returns
    -------
    pd.DataFrame with columns: adj_id, location, skill, will_travel,
        tour_length, resource_type, org_group, event_id, qtr_rank, state,
        home_cluster, current_cluster, status, active_claim_id,
        day_available, has_pl0_boost, pl0_pair_id
    """
    raw = pd.read_excel(roster_file)
    rc  = cfg["roster_cols"]

    # Verify required columns
    required = [rc["adj_id"], rc["location"], rc["skill"]]
    missing = [c for c in required if c not in raw.columns]
    if missing:
        raise ValueError(
            f"Roster file missing required columns: {', '.join(missing)}\n"
            "Update cfg['roster_cols'] to match your file's column names."
        )

    def _pull(col_key, cast=str):
        """Safely pull optional column; return NA series if absent."""
        col = rc.get(col_key)
        if col and col in raw.columns:
            return raw[col]
        return pd.Series([None] * len(raw))

    roster = pd.DataFrame({
        "adj_id":        pd.to_numeric(raw[rc["adj_id"]], errors="coerce").astype("Int64"),
        "location":      raw[rc["location"]].astype(str).str.strip(),
        "skill":         pd.to_numeric(raw[rc["skill"]], errors="coerce").astype("Int64"),
        "will_travel":   _pull("will_travel").astype(str).str.strip().str.upper() == "Y",
        "tour_length":   pd.to_numeric(_pull("tour_length"), errors="coerce").astype("Int64"),
        "resource_type": _pull("resource_type").astype(str).str.strip(),
        "org_group":     _pull("org_group").astype(str).str.strip(),
        "event_id":      pd.to_numeric(_pull("event_id"), errors="coerce").astype("Int64"),
        "qtr_rank":      pd.to_numeric(_pull("qtr_rank"), errors="coerce").astype("Int64"),
    })

    # Fix NA tour lengths → 21
    roster["tour_length"] = roster["tour_length"].fillna(21).astype(int)
    # Fix NA qtr_rank → 0
    roster["qtr_rank"] = roster["qtr_rank"].fillna(0).astype(int)
    # skill to int
    roster["skill"] = roster["skill"].astype(int)

    # Map location → state
    if location_lookup_file:
        lookup = pd.read_csv(location_lookup_file)
        roster = roster.merge(lookup[["location", "state"]], on="location", how="left")
    else:
        roster["state"] = roster["location"].map(_location_to_state)

    # Simulation columns
    roster["home_cluster"]    = None
    roster["current_cluster"] = None
    roster["status"]          = "Available"
    roster["active_claim_id"] = pd.NA
    roster["day_available"]   = 1
    roster["has_pl0_boost"]   = False
    roster["pl0_pair_id"]     = pd.NA

    roster = roster.sort_values(["skill", "adj_id"], ascending=[False, True]).reset_index(drop=True)

    print(f"Roster loaded: {len(roster)} adjusters")
    print(f"  PL5: {(roster.skill==5).sum()} | "
          f"PL4: {(roster.skill==4).sum()} | "
          f"PL3: {(roster.skill==3).sum()} | "
          f"PL2: {(roster.skill==2).sum()} | "
          f"PL1: {(roster.skill==1).sum()} | "
          f"PL0: {(roster.skill==0).sum()}")
    print(f"  Will Travel: {roster.will_travel.sum()} | "
          f"Won't Travel: {(~roster.will_travel).sum()}")

    return roster
