# geocode.py — Geocode claims (by ZIP) and adjuster offices (by location name)
# Uses pgeocode (offline GeoNames data — no network calls for US ZIPs).

import pgeocode
import numpy as np
import pandas as pd

_NOM = pgeocode.Nominatim("us")

# ---------------------------------------------------------------------------
# Fallback ZIP codes for claims rows that have no ZIP (city+state key)
# Keys are (CITY_UPPER, STATE_ABBR) to match raw data values.
# ---------------------------------------------------------------------------
_CITY_STATE_FALLBACK_ZIP = {
    ("TUSCALOOSA",     "AL"): "35401",
    ("HENDERSONVILL",  "TN"): "37075",   # truncated in source data
    ("HENDERSONVILLE", "TN"): "37075",
    ("MADISON",        "TN"): "37115",
}

# ---------------------------------------------------------------------------
# Representative ZIP for each of the 87 adjuster office locations.
# Chosen to place the office in the correct city; used for pgeocode lookup.
# ---------------------------------------------------------------------------
_LOCATION_ZIP = {
    "Albany - Park Pl":                       "12207",
    "Albuquerque-Lang Avenue":               "87109",
    "Alpharetta-Atlanta":                    "30009",
    "Austin-901 Mo-Pac":                     "78759",
    "Bedford - Commerce":                    "03110",
    "Birmingham-Hoover":                     "35209",
    "Blue Bell-Phil-Lakeview Dr":            "19422",
    "Boise-Meridian":                        "83642",
    "Boston-Financial Center":              "02110",
    "Brookfield-Milwaukee":                 "53045",
    "Buffalo":                               "14202",
    "Centennial-Denver-Geddes":             "80112",
    "Chantilly-WashingtnDC-PkMeadow":       "20151",
    "Charlotte-Carmel Commons":             "28269",
    "Cincinnati-Elsinore":                  "45202",
    "Columbus-Easton Oval":                 "43219",
    "Delaware - Virtual":                    "19801",
    "Diamond Bar-Los Angeles":              "91765",
    "Durham - Emperor Blvd":                "27703",
    "Edison-343 Thornall":                  "08837",
    "Exton-Philadelphia-Eagleview":         "19341",
    "Federal Way-Seattle-6th Ave":          "98003",
    "Flowood-Jackson-Canebrake":            "39232",
    "Franklin-Nashville":                   "37064",
    "Fresno":                               "93721",
    "Glendale-LosAngeles-655NCentrl":       "91203",
    "Glens Falls - Queensbury":             "12804",
    "Hamden Law":                           "06514",
    "Hartford - Tower":                     "06103",
    "Hartford-Field":                       "06103",
    "Honolulu":                             "96813",
    "Houston - Westway":                    "77042",
    "Hudson - Boston":                      "01749",
    "Hunt Valley-Baltimore-Schilling":      "21031",
    "Independence-Cleveland":               "44131",
    "Indianapolis - 96th St":               "46240",
    "Irvine-Los Angeles-Michelson":         "92618",
    "Jacksonville Law":                     "32256",
    "Knoxville":                            "37902",
    "Las Vegas-Arroyo Crossing":            "89130",
    "Little Rock":                          "72201",
    "Louisville-Hurstbourne Pkwy":          "40222",
    "Marlton-Camden Law":                   "08053",
    "Maryland Heights-St. Louis":           "63043",
    "Massachusetts - Virtual":              "02109",
    "Melville NY Corp Center Dr":           "11747",
    "Memphis-6750 Poplar":                  "38119",
    "Metairie-New Orleans-3900 Cswy":       "70001",
    "Morristown":                           "07960",
    "Naperville-Chicago":                   "60563",
    "New York City - Lexington Ave":        "10022",
    "North Dakota - Virtual":              "58501",
    "Oklahoma City Law":                    "73118",
    "Omaha-Dodge Rd":                       "68154",
    "Orange-Los Angeles-Law":               "92868",
    "Orlando":                              "32801",
    "Overland Pk-Kansas City-132 St":       "66213",
    "Philadelphia-Market St":              "19103",
    "Phoenix-Tatum Blvd":                   "85050",
    "Pittsburgh-Washington Pl":             "15222",
    "Portland":                             "97201",
    "Providence Law":                       "02903",
    "Raleigh":                              "27601",
    "RanchoCordova-Sacramento-11090":       "95670",
    "Richardson-Dallas":                    "75080",
    "Richmond-Mayland Dr":                  "23233",
    "Rochester - Linden Oaks":              "14625",
    "Rosedale-Baltimore":                   "21237",
    "Salt Lake City-1100 E 6600":           "84121",
    "San Antonio-McAllister Fwy":           "78216",
    "San Diego":                            "92101",
    "South Carolina - Virtual":             "29201",
    "South Portland":                       "04106",
    "Spokane":                              "99201",
    "St. Paul":                             "55101",
    "Syracuse-Plainfield Rd":               "13212",
    "Tampa - Dale Mabry":                   "33609",
    "Troy-Detroit":                         "48084",
    "Tulsa-5100 Skelly":                    "74135",
    "Vermont - Virtual":                    "05401",
    "Walnut Creek-San Francisco-401":       "94596",
    "Washington, DC - 13th Street":         "20005",
    "West Bridgewater":                     "02379",
    "West Des Moines-Jordan Creek":         "50266",
    "White Plains-Law1-Liability":          "10601",
    "Windsor-Htfd-99 Lambrtn-ClaimU":       "06095",
    "Wyomissing-Reading":                   "19610",
}


def _pgeocode_batch(zips: list[str]) -> pd.DataFrame:
    """Query pgeocode for a list of ZIP strings. Returns DataFrame with
    columns [zip, lat, lng]; rows with no result are NaN."""
    result = _NOM.query_postal_code(zips)
    result = result.rename(columns={"postal_code": "zip",
                                    "latitude": "lat",
                                    "longitude": "lng"})
    result["zip"] = [str(z).strip() for z in zips]   # keep original key
    return result[["zip", "lat", "lng"]].reset_index(drop=True)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def geocode_claims(claims_df: pd.DataFrame) -> pd.DataFrame:
    """
    Add lat / lng columns to claims_df by looking up each ZIP via pgeocode.
    For rows missing a ZIP, fall back to city+state lookup.

    Returns a copy of claims_df with new columns: lat, lng.
    Missing coordinates are left as NaN.
    """
    df = claims_df.copy()

    # ---- normalise ZIP strings (remove ".0" suffixes, zero-pad to 5) ----
    def _fmt_zip(z):
        if pd.isna(z):
            return None
        s = str(z).strip()
        if s.lower() in ("nan", "none", ""):
            return None
        if s.endswith(".0"):
            s = s[:-2]
        return s.zfill(5)

    df["_zip_str"] = df["zip"].map(_fmt_zip)

    # ---- for rows missing ZIP, substitute via city+state fallback --------
    missing_mask = df["_zip_str"].isna()
    if missing_mask.any():
        def _fallback(row):
            city  = str(row["city"]).upper().strip() if pd.notna(row["city"]) else ""
            state = str(row["state"]).upper().strip() if pd.notna(row["state"]) else ""
            return _CITY_STATE_FALLBACK_ZIP.get((city, state), None)
        df.loc[missing_mask, "_zip_str"] = df[missing_mask].apply(_fallback, axis=1)

    # ---- batch pgeocode query on unique ZIPs ----------------------------
    unique_zips = [z for z in df["_zip_str"].dropna().unique()]
    geo = _pgeocode_batch(unique_zips).set_index("zip")

    df["lat"] = df["_zip_str"].map(geo["lat"])
    df["lng"] = df["_zip_str"].map(geo["lng"])
    df.drop(columns=["_zip_str"], inplace=True)

    geocoded    = df["lat"].notna().sum()
    not_geocoded = df["lat"].isna().sum()
    print(f"geocode_claims: {geocoded}/{len(df)} claims geocoded "
          f"({not_geocoded} missing coordinates)")

    return df


def geocode_adjusters(roster_df: pd.DataFrame) -> pd.DataFrame:
    """
    Add lat / lng columns to roster_df using the office location name.
    Each unique location is looked up once via a representative ZIP in
    _LOCATION_ZIP, then pgeocode-resolved.

    Returns a copy of roster_df with new columns: lat, lng.
    Locations not in _LOCATION_ZIP are left as NaN.
    """
    df = roster_df.copy()

    # Unique locations present in this roster
    unique_locs = df["location"].unique()
    missing_def = [l for l in unique_locs if l not in _LOCATION_ZIP]
    if missing_def:
        print(f"  WARNING: {len(missing_def)} locations have no ZIP in "
              f"_LOCATION_ZIP: {missing_def}")

    loc_zips = {loc: _LOCATION_ZIP.get(loc) for loc in unique_locs
                if _LOCATION_ZIP.get(loc)}
    unique_zip_list = list(set(loc_zips.values()))

    geo = _pgeocode_batch(unique_zip_list).set_index("zip")

    # Build location → (lat, lng) map
    loc_coords = {}
    for loc, z in loc_zips.items():
        if z in geo.index:
            loc_coords[loc] = (geo.at[z, "lat"], geo.at[z, "lng"])

    df["lat"] = df["location"].map(lambda l: loc_coords.get(l, (np.nan, np.nan))[0])
    df["lng"] = df["location"].map(lambda l: loc_coords.get(l, (np.nan, np.nan))[1])

    geocoded = df["lat"].notna().sum()
    print(f"geocode_adjusters: {geocoded}/{len(df)} adjusters geocoded "
          f"({len(unique_locs)} unique locations -> "
          f"{len(loc_coords)} resolved)")

    return df


def adjuster_location_coords(roster_df: pd.DataFrame) -> pd.DataFrame:
    """
    Return a deduplicated DataFrame of adjuster office coordinates,
    indexed by location name. Used by distance.build_distance_matrix().

    Expects roster_df to already have lat/lng columns (call geocode_adjusters first).
    """
    return (roster_df[["location", "lat", "lng"]]
            .drop_duplicates("location")
            .dropna(subset=["lat", "lng"])
            .set_index("location"))


def claim_zip_coords(claims_df: pd.DataFrame) -> pd.DataFrame:
    """
    Return a deduplicated DataFrame of claim ZIP coordinates,
    indexed by ZIP string. Used by distance.build_distance_matrix().

    Expects claims_df to already have lat/lng columns (call geocode_claims first).
    """
    df = claims_df.copy()

    def _fmt(z):
        if pd.isna(z):
            return None
        s = str(z).strip()
        if s.endswith(".0"):
            s = s[:-2]
        return s.zfill(5)

    df["_zip_str"] = df["zip"].map(_fmt)
    return (df[["_zip_str", "lat", "lng"]]
            .rename(columns={"_zip_str": "zip"})
            .drop_duplicates("zip")
            .dropna(subset=["lat", "lng"])
            .set_index("zip"))
