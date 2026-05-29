# distance.py — Haversine distances and adjuster-to-claim drive-time matrix

import numpy as np
import pandas as pd

# Earth radius (km)
_R_KM = 6371.0

# Road-distance multiplier over straight-line (great-circle) distance
_DETOUR = 1.3

# Assumed average driving speed from config (km/h)
_SPEED_KMH = 105.0


# ---------------------------------------------------------------------------
# Core geometry
# ---------------------------------------------------------------------------

def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Return great-circle distance in km between two (lat, lon) points.
    Inputs may be scalars or numpy arrays (broadcasting applies).
    """
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    return 2 * _R_KM * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


def drive_hours(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Estimated one-way drive time in hours.
    Formula: haversine_km × 1.3 (detour factor) / 105 km/h (assumed speed).
    """
    return haversine(lat1, lon1, lat2, lon2) * _DETOUR / _SPEED_KMH


# ---------------------------------------------------------------------------
# Matrix builder
# ---------------------------------------------------------------------------

def build_distance_matrix(adjuster_coords: pd.DataFrame,
                           claim_coords:    pd.DataFrame) -> pd.DataFrame:
    """
    Compute a drive-time matrix between all adjuster offices and all claim ZIPs.

    Parameters
    ----------
    adjuster_coords : DataFrame indexed by location name, columns [lat, lng]
                      (output of geocode.adjuster_location_coords)
    claim_coords    : DataFrame indexed by ZIP string, columns [lat, lng]
                      (output of geocode.claim_zip_coords)

    Returns
    -------
    DataFrame shape (n_locations × n_zips) — values are drive hours.
    Index = adjuster location names; columns = ZIP strings.
    """
    # Extract numpy arrays: shapes (n_adj,) and (n_zip,)
    adj_lat = adjuster_coords["lat"].values   # (n_adj,)
    adj_lng = adjuster_coords["lng"].values
    clm_lat = claim_coords["lat"].values      # (n_zip,)
    clm_lng = claim_coords["lng"].values

    # Vectorised haversine via broadcasting: (n_adj, 1) op (1, n_zip) → (n_adj, n_zip)
    adj_lat_r = np.radians(adj_lat[:, np.newaxis])
    adj_lng_r = np.radians(adj_lng[:, np.newaxis])
    clm_lat_r = np.radians(clm_lat[np.newaxis, :])
    clm_lng_r = np.radians(clm_lng[np.newaxis, :])

    dlat = clm_lat_r - adj_lat_r
    dlon = clm_lng_r - adj_lng_r
    a = (np.sin(dlat / 2) ** 2
         + np.cos(adj_lat_r) * np.cos(clm_lat_r) * np.sin(dlon / 2) ** 2)
    km_matrix = 2 * _R_KM * np.arcsin(np.sqrt(np.clip(a, 0, 1)))

    hours_matrix = km_matrix * _DETOUR / _SPEED_KMH

    return pd.DataFrame(
        hours_matrix,
        index=adjuster_coords.index,
        columns=claim_coords.index,
    )


# ---------------------------------------------------------------------------
# Eligible pair filter
# ---------------------------------------------------------------------------

def get_eligible_pairs(distance_matrix: pd.DataFrame,
                        max_hours: float = 4.0) -> pd.DataFrame:
    """
    Return a long-format DataFrame of (location, zip, drive_hours) pairs
    where drive_hours <= max_hours, sorted by drive_hours ascending.

    Parameters
    ----------
    distance_matrix : output of build_distance_matrix
    max_hours       : drive-time threshold (default 4 hours)

    Returns
    -------
    DataFrame with columns [location, zip, drive_hours]
    """
    # Stack matrix to long format, filter, sort
    stacked = (distance_matrix
               .stack()
               .reset_index()
               .rename(columns={"level_0": "location",
                                "level_1": "zip",
                                0:         "drive_hours"}))
    eligible = stacked[stacked["drive_hours"] <= max_hours].copy()
    eligible.sort_values("drive_hours", inplace=True)
    eligible.reset_index(drop=True, inplace=True)
    return eligible
