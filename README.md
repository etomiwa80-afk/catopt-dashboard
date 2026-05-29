# CATOPT — CAT Claims Optimization Dashboard

Python Dash dashboard and simulation engine for catastrophic insurance
claims management. Built as a DS 7900 capstone project at Kennesaw State
University. Winning team project.

## What it does

Three-run optimization simulation matching 1,054 claims to 774 adjusters
across 7 geographic clusters during a catastrophic weather event. Uses
Google OR-Tools min-cost flow solver for daily bipartite assignment, with
a PL0 mentor-boost mechanism that improved Sev-5 SLA compliance from 34.9%
to 48.9% across runs.

## Results

| Run | Description | Overall SLA | Sev-5 SLA |
|---|---|---|---|
| Run 1 | Baseline (no boost) | 82.8% | 34.9% |
| Run 2 | PL0 mentor boost | 86.5% | 48.9% |
| Run 3 | PL3 to PL4 upgrade + boost | 89.2% | 61.8% |

## Note on results

Original results produced from proprietary event data provided by a real
insurance client. Synthetic data is included for demonstration purposes
and matches the exact schema and statistical distributions of the original.

## Architecture

| File | Role |
|---|---|
| `app.py` | Dash dashboard — CYBORG theme, KPI cards, choropleth map, donut charts |
| `main.py` | Entry point — runs 3 simulation scenarios, exports CSVs |
| `simulator.py` | Day-by-day simulation loop with wave trigger and PL0 boost |
| `assignment.py` | OR-Tools min-cost flow solver for daily bipartite assignment |
| `config.py` | All parameters — throughput rates, SLA windows, cost rates |
| `load_data.py` | Claims and roster data loading and cleaning |
| `geocode.py` | ZIP-level geocoding via pgeocode (offline, no API calls) |
| `distance.py` | Haversine distance matrix and drive-time calculations |
| `generate_synthetic_data.py` | Generates synthetic demo data matching real output schema |

## Setup

1. Clone the repo
2. Install dependencies: `pip install -r requirements.txt`
3. Generate synthetic demo data: `python generate_synthetic_data.py`
4. Run dashboard: `python app.py` then open http://localhost:8050

To run the full simulation on your own data:
- Add claims CSV and roster XLSX to a `data/` folder
- Set environment variable: `DATA_DIR=path/to/data`
- Run: `python main.py`

## Tools

Python, Dash, Plotly, OR-Tools, pandas, NumPy, pgeocode, openpyxl,
dash-bootstrap-components
