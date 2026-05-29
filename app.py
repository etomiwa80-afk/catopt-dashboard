# ══════════════════════════════════════════════════════════════
#  app.py — CATOPT Command Center Dashboard (Dark Premium)
#  CAT Code 82 | DS 7900 Capstone
#
#  INSTALL:
#  pip install dash dash-bootstrap-components dash-bootstrap-templates plotly pandas
#
#  RUN:
#  python app.py  →  http://localhost:8050
# ══════════════════════════════════════════════════════════════

import subprocess, sys, os

try:
    subprocess.check_call(
        [sys.executable, "-m", "pip", "install", "--quiet",
         "dash", "dash-bootstrap-components",
         "dash-bootstrap-templates", "plotly", "pandas"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
except Exception:
    pass

import pandas as pd
import plotly.graph_objects as go
import dash
from dash import html, dcc, dash_table, Input, Output
import dash_bootstrap_components as dbc
from dash_bootstrap_templates import load_figure_template

# ──────────────────────────────────────────────────────────────
#  CONSTANTS
# ──────────────────────────────────────────────────────────────
GOLD    = "#FFC52E"
NAVY    = "#002060"
CARD_BG = "#1a1a2e"
DARK2   = "#2a2a3e"
TEXT    = "#E8E8E8"
MUTED   = "#6c757d"
GREEN   = "#00cc66"
RED     = "#ff4444"
FONT    = "Segoe UI, Helvetica Neue, Arial, sans-serif"

PENALTY_MAP  = {5: 5000, 4: 2500, 3: 1000, 2: 500, 1: 100}
DEPLOY_DAILY = 150
DEFAULTS     = {5: 278, 4: 211, 3: 415, 2: 91, 1: 59}

CHART_LAYOUT = dict(
    font=dict(family=FONT, size=11, color=TEXT),
    plot_bgcolor="rgba(0,0,0,0)",
    paper_bgcolor="rgba(0,0,0,0)",
    margin=dict(l=10, r=10, t=10, b=10),
    xaxis=dict(gridcolor="rgba(255,255,255,0.06)",
               zerolinecolor="rgba(255,255,255,0.06)"),
    yaxis=dict(gridcolor="rgba(255,255,255,0.06)",
               zerolinecolor="rgba(255,255,255,0.06)"),
)

RUN_OPTS = [
    {"label": "Run 1 — Baseline",        "value": "run1"},
    {"label": "Run 2 — PL0 Boost",       "value": "run2"},
    {"label": "Run 3 — Upgrade + Boost", "value": "run3"},
]

# ──────────────────────────────────────────────────────────────
#  DATA LOADING
# ──────────────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_data_sub  = os.path.join(SCRIPT_DIR, "data")
_data_dl = os.getenv("DATA_DIR", "data")

def _files_present(folder):
    return all(
        os.path.exists(os.path.join(folder, f"catopt_run{n}_{t}.csv"))
        for n in [1, 2, 3] for t in ["assignments", "daily"]
    )

DATA_DIR = (
    _data_sub if _files_present(_data_sub) else
    _data_dl  if _files_present(_data_dl)  else
    _data_sub
)

def _load(n):
    a = pd.read_csv(os.path.join(DATA_DIR, f"catopt_run{n}_assignments.csv"))
    d = pd.read_csv(os.path.join(DATA_DIR, f"catopt_run{n}_daily.csv"))
    a["sla_met"] = a["sla_met"].astype(str).str.strip().str.lower() == "true"
    a["boosted"] = a["boosted"].astype(str).str.strip().str.lower() == "true"
    return {"assignments": a, "daily": d}

try:
    DATA     = {"run1": _load(1), "run2": _load(2), "run3": _load(3)}
    HAS_DATA = True
except Exception as e:
    print(f"  Data load error: {e}")
    DATA     = {}
    HAS_DATA = False

# ──────────────────────────────────────────────────────────────
#  ANALYTICS
# ──────────────────────────────────────────────────────────────
def _kpis(df):
    n       = len(df)
    met     = int(df["sla_met"].sum())
    s5      = df[df["severity"] == 5]
    s5_met  = int(s5["sla_met"].sum())
    cross   = df["adj_state"] != df["claim_state"]
    op_cost = int((df.loc[cross, "days_to_complete"] * DEPLOY_DAILY).sum())
    penalty = sum(
        int((~df[df["severity"] == sev]["sla_met"]).sum()) * p
        for sev, p in PENALTY_MAP.items()
    )
    return dict(
        overall_sla=round(met / n * 100, 1) if n else 0.0,
        sev5_sla=round(s5_met / len(s5) * 100, 1) if len(s5) else 0.0,
        op_cost=op_cost, penalty=penalty,
        total=n, met=met, s5_met=s5_met, s5_total=len(s5),
    )

def _breakdown(df):
    out = {}
    for sev in [5, 4, 3, 2, 1]:
        s   = df[df["severity"] == sev]
        tot = len(s)
        met = int(s["sla_met"].sum())
        out[sev] = {"met": met, "total": tot,
                    "pct": round(met / tot * 100, 1) if tot else 0.0}
    return out

if HAS_DATA:
    ALL_KPIS  = {k: _kpis(v["assignments"])     for k, v in DATA.items()}
    ALL_BDOWN = {k: _breakdown(v["assignments"]) for k, v in DATA.items()}

# ──────────────────────────────────────────────────────────────
#  UI COMPONENTS
# ──────────────────────────────────────────────────────────────
def make_kpi_card(title, value, subtitle=""):
    return dbc.Card(
        dbc.CardBody([
            html.P(title, className="text-muted mb-0", style={
                "fontSize": "10px", "textTransform": "uppercase",
                "letterSpacing": "1px",
            }),
            html.H3(value, style={
                "color": GOLD, "fontWeight": "700", "fontSize": "26px",
                "margin": "4px 0 2px 0",
            }),
            html.P(subtitle, className="text-muted mb-0",
                   style={"fontSize": "10px"}),
        ], style={"padding": "12px 14px"}),
        style={
            "backgroundColor": CARD_BG,
            "borderLeft": f"3px solid {GOLD}",
            "borderTop": "none", "borderRight": "none", "borderBottom": "none",
            "borderRadius": "4px",
        },
        className="h-100",
    )


def make_skill_stat(label, count, total):
    pct = count / total * 100 if total else 0
    return dbc.Col(html.Div([
        html.P(label, style={
            "fontSize": "10px", "color": MUTED,
            "marginBottom": "2px", "textAlign": "center",
        }),
        html.P(str(count), style={
            "fontSize": "18px", "fontWeight": "700", "color": GOLD,
            "textAlign": "center", "marginBottom": "2px",
        }),
        html.P(f"{pct:.0f}%", style={
            "fontSize": "9px", "color": MUTED, "textAlign": "center",
        }),
    ]), width=True)


# ──────────────────────────────────────────────────────────────
#  APP INIT
# ──────────────────────────────────────────────────────────────
dbc_css = (
    "https://cdn.jsdelivr.net/gh/AnnMarieW/"
    "dash-bootstrap-templates@V1.0.2/dbc.min.css"
)

app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.CYBORG, dbc_css],
    suppress_callback_exceptions=True,
)
app.title = "CATOPT — CAT Claims Optimization"
load_figure_template("cyborg")

# ──────────────────────────────────────────────────────────────
#  STATIC LAYOUT PIECES
# ──────────────────────────────────────────────────────────────
header = dbc.Row([
    dbc.Col(html.Div([
        html.Span("TRAVELERS", style={
            "color": GOLD, "fontWeight": "800", "fontSize": "20px",
            "letterSpacing": "3px", "marginRight": "16px",
        }),
        html.Span("CAT Claims Optimization Dashboard", style={
            "color": TEXT, "fontSize": "15px", "fontWeight": "300",
        }),
    ]), width="auto"),
    dbc.Col(html.Div([
        html.Span("1,054 Claims", style={
            "backgroundColor": GOLD, "color": NAVY,
            "padding": "4px 12px", "borderRadius": "12px",
            "fontSize": "11px", "fontWeight": "700", "marginRight": "8px",
        }),
        html.Span("774 Adjusters", style={
            "backgroundColor": DARK2, "color": TEXT,
            "padding": "4px 12px", "borderRadius": "12px",
            "fontSize": "11px", "fontWeight": "600", "marginRight": "8px",
        }),
        html.Span("CAT Code 82", style={
            "backgroundColor": DARK2, "color": TEXT,
            "padding": "4px 12px", "borderRadius": "12px",
            "fontSize": "11px", "fontWeight": "600",
        }),
    ]), width="auto", className="ms-auto d-flex align-items-center"),
], className="py-2 mb-2",
   style={"borderBottom": f"1px solid {DARK2}"},
   align="center")

kpi_row = dbc.Row([
    dbc.Col(html.Div(id="kpi-sla"),     width=2),
    dbc.Col(html.Div(id="kpi-sev5"),    width=2),
    dbc.Col(html.Div(id="kpi-cost"),    width=2),
    dbc.Col(html.Div(id="kpi-penalty"), width=2),
    dbc.Col([
        html.Label("Active Run", className="text-muted small"),
        dbc.Select(
            id="run-selector", options=RUN_OPTS, value="run1",
            style={
                "backgroundColor": CARD_BG, "color": TEXT,
                "border": f"1px solid {DARK2}", "fontSize": "13px",
            },
        ),
    ], width=2, className="d-flex flex-column justify-content-center"),
], className="g-2 mb-2")

# ── What-If Panel (sliders + SLA chart) ──────────────────────
whatif_panel = dbc.Card([
    dbc.CardBody([
        dbc.Row([
            dbc.Col([
                html.H6("What-If Scenario", className="text-white mb-2",
                        style={"letterSpacing": "1px", "fontSize": "13px"}),
                html.Label("Sev-5 Claims", className="text-muted small mb-0"),
                dcc.Slider(id="sev5-slider", min=0, max=600, value=278, step=1,
                           marks=None,
                           tooltip={"placement": "right", "always_visible": True}),
                html.Label("Sev-4 Claims", className="text-muted small mb-0 mt-2"),
                dcc.Slider(id="sev4-slider", min=0, max=500, value=211, step=1,
                           marks=None,
                           tooltip={"placement": "right", "always_visible": True}),
                html.Label("Sev-3 Claims", className="text-muted small mb-0 mt-2"),
                dcc.Slider(id="sev3-slider", min=0, max=800, value=415, step=1,
                           marks=None,
                           tooltip={"placement": "right", "always_visible": True}),
                html.Label("Sev-2 Claims", className="text-muted small mb-0 mt-2"),
                dcc.Slider(id="sev2-slider", min=0, max=300, value=91, step=1,
                           marks=None,
                           tooltip={"placement": "right", "always_visible": True}),
                html.Label("Sev-1 Claims", className="text-muted small mb-0 mt-2"),
                dcc.Slider(id="sev1-slider", min=0, max=200, value=59, step=1,
                           marks=None,
                           tooltip={"placement": "right", "always_visible": True}),
                dbc.Button(
                    "Reset", id="reset-btn", size="sm",
                    color="warning", outline=True, className="w-100 mt-3",
                    style={"borderColor": GOLD, "color": GOLD, "fontSize": "11px"},
                ),
            ], width=5),
            dbc.Col([
                html.P("SLA % by Severity", className="text-muted small mb-1",
                       style={"textTransform": "uppercase", "letterSpacing": "1px",
                              "fontSize": "10px"}),
                dcc.Graph(id="sla-severity-chart",
                          config={"displayModeBar": False},
                          style={"height": "260px"}),
            ], width=7),
        ])
    ], style={"padding": "14px"}),
], style={"backgroundColor": CARD_BG, "border": f"1px solid {DARK2}"}, className="mb-2")

# ── Donut + Cost Gauges ───────────────────────────────────────
bottom_left = dbc.Row([
    dbc.Col(
        dbc.Card(
            dbc.CardBody(
                dcc.Graph(id="donut-chart", config={"displayModeBar": False},
                          style={"height": "170px"}),
                style={"padding": "8px"},
            ),
            style={"backgroundColor": CARD_BG, "border": f"1px solid {DARK2}"},
        ),
        width=6,
    ),
    dbc.Col(
        dbc.Card(
            dbc.CardBody([
                html.P("Cost Breakdown", className="text-muted small mb-2",
                       style={"textTransform": "uppercase", "letterSpacing": "1px",
                              "fontSize": "10px"}),
                html.P("Operating Cost", className="text-muted mb-1",
                       style={"fontSize": "10px"}),
                html.Div(
                    id="cost-gauge",
                    style={"backgroundColor": DARK2, "borderRadius": "4px",
                           "marginBottom": "10px"},
                ),
                html.P("Penalty Exposure", className="text-muted mb-1",
                       style={"fontSize": "10px"}),
                html.Div(
                    id="penalty-gauge",
                    style={"backgroundColor": DARK2, "borderRadius": "4px"},
                ),
            ], style={"padding": "14px"}),
            style={"backgroundColor": CARD_BG, "border": f"1px solid {DARK2}"},
        ),
        width=6,
    ),
], className="mb-2")

# ── Delta Card ────────────────────────────────────────────────
delta_card = dbc.Card(
    dbc.CardBody(
        html.Div(id="delta-content", children=[
            html.Span(
                "Adjust sliders to see impact vs. baseline",
                className="text-muted",
                style={"fontSize": "12px", "fontStyle": "italic"},
            ),
        ]),
        style={"padding": "10px 14px"},
    ),
    style={"backgroundColor": CARD_BG, "border": f"1px solid {DARK2}"},
)

# ── Assignments Panel ─────────────────────────────────────────
assignments_panel = dbc.Card([
    dbc.CardBody([
        dbc.Row([
            dbc.Col(
                html.H6("Assignments", className="text-white mb-0",
                        style={"letterSpacing": "1px", "fontSize": "13px"}),
                width="auto",
            ),
            dbc.Col(dbc.Select(
                id="assign-sev",
                options=[
                    {"label": "All Severities", "value": "all"},
                    {"label": "Sev-5", "value": "5"},
                    {"label": "Sev-4", "value": "4"},
                    {"label": "Sev-3", "value": "3"},
                    {"label": "Sev-2", "value": "2"},
                    {"label": "Sev-1", "value": "1"},
                ],
                value="all",
                style={"backgroundColor": CARD_BG, "color": TEXT,
                       "border": f"1px solid {DARK2}", "fontSize": "12px"},
            ), width=3),
            dbc.Col(dbc.Select(
                id="assign-sla",
                options=[
                    {"label": "All Status", "value": "all"},
                    {"label": "Met",        "value": "True"},
                    {"label": "Missed",     "value": "False"},
                ],
                value="all",
                style={"backgroundColor": CARD_BG, "color": TEXT,
                       "border": f"1px solid {DARK2}", "fontSize": "12px"},
            ), width=3),
        ], align="center", className="mb-2"),

        dash_table.DataTable(
            id="assignments-table",
            columns=[
                {"name": "Day",     "id": "day"},
                {"name": "Adjuster","id": "adj_id"},
                {"name": "Claim",   "id": "claim_id"},
                {"name": "Skill",   "id": "skill"},
                {"name": "Sev",     "id": "severity"},
                {"name": "SLA By",  "id": "sla_deadline"},
                {"name": "Done",    "id": "completion_day"},
                {"name": "Met",     "id": "sla_met"},
                {"name": "Miles",   "id": "distance_miles"},
            ],
            data=[],
            page_size=15,
            sort_action="native",
            style_header={
                "backgroundColor": CARD_BG,
                "color": GOLD,
                "fontWeight": "600",
                "borderBottom": f"1px solid {GOLD}",
                "textAlign": "center",
                "fontSize": "10px",
                "textTransform": "uppercase",
                "letterSpacing": "0.5px",
                "padding": "8px 4px",
            },
            style_cell={
                "backgroundColor": "transparent",
                "color": TEXT,
                "border": f"1px solid {DARK2}",
                "textAlign": "center",
                "padding": "6px 4px",
                "fontSize": "11px",
                "maxWidth": "80px",
                "overflow": "hidden",
                "textOverflow": "ellipsis",
            },
            style_data_conditional=[
                {
                    "if": {"filter_query": "{sla_met} = False"},
                    "backgroundColor": "rgba(255,68,68,0.12)",
                    "color": RED,
                },
            ],
        ),
    ], style={"padding": "12px"}),
], style={"backgroundColor": CARD_BG, "border": f"1px solid {DARK2}"}, className="mb-2")

# ── Adjuster Summary ──────────────────────────────────────────
adjuster_summary = dbc.Card([
    dbc.CardBody([
        html.H6("Adjuster Breakdown", className="text-white mb-2",
                style={"letterSpacing": "1px", "fontSize": "12px"}),
        dbc.Row(id="adjuster-breakdown-content"),
    ], style={"padding": "12px"}),
], style={"backgroundColor": CARD_BG, "border": f"1px solid {DARK2}"})

# ──────────────────────────────────────────────────────────────
#  LAYOUT
# ──────────────────────────────────────────────────────────────
app.layout = dbc.Container([
    header,
    kpi_row,
    dbc.Row([
        dbc.Col([
            whatif_panel,
            bottom_left,
            delta_card,
        ], width=6),
        dbc.Col([
            assignments_panel,
            adjuster_summary,
        ], width=6),
    ], className="g-2"),
], fluid=True, className="dbc dbc-ag-grid px-3 py-2")


# ──────────────────────────────────────────────────────────────
#  CALLBACKS
# ──────────────────────────────────────────────────────────────

@app.callback(
    Output("kpi-sla",            "children"),
    Output("kpi-sev5",           "children"),
    Output("kpi-cost",           "children"),
    Output("kpi-penalty",        "children"),
    Output("sla-severity-chart", "figure"),
    Output("donut-chart",        "figure"),
    Output("cost-gauge",         "children"),
    Output("penalty-gauge",      "children"),
    Output("delta-content",      "children"),
    Input("sev5-slider",  "value"),
    Input("sev4-slider",  "value"),
    Input("sev3-slider",  "value"),
    Input("sev2-slider",  "value"),
    Input("sev1-slider",  "value"),
    Input("run-selector", "value"),
)
def update_scenario(s5, s4, s3, s2, s1, run_key):
    if not HAS_DATA:
        empty = go.Figure()
        empty.update_layout(**CHART_LAYOUT)
        return (
            make_kpi_card("Overall SLA", "—"),
            make_kpi_card("Sev-5 SLA", "—"),
            make_kpi_card("Operating Cost", "—"),
            make_kpi_card("Penalty Exposure", "—"),
            empty, empty, "", "",
            html.Span("No data", className="text-muted"),
        )

    new_counts = {
        5: s5 or 278, 4: s4 or 211,
        3: s3 or 415, 2: s2 or 91, 1: s1 or 59,
    }
    orig  = DEFAULTS.copy()
    df    = DATA[run_key]["assignments"]
    bdown = ALL_BDOWN[run_key]

    sc_met, sc_missed, sc_sla, sc_cost = {}, {}, {}, {}
    for sev in [5, 4, 3, 2, 1]:
        b      = bdown[sev]
        rate   = b["met"] / b["total"] if b["total"] > 0 else 1.0
        cnt    = new_counts[sev]
        met_n  = round(rate * cnt)
        sc_met[sev]    = met_n
        sc_missed[sev] = cnt - met_n
        sc_sla[sev]    = round(rate * 100, 1)
        sev_df = df[df["severity"] == sev]
        cross  = sev_df["adj_state"] != sev_df["claim_state"]
        base_c = int((sev_df.loc[cross, "days_to_complete"] * DEPLOY_DAILY).sum())
        ratio  = cnt / orig[sev] if orig[sev] > 0 else 1.0
        sc_cost[sev] = int(base_c * ratio)

    total_new   = sum(new_counts.values())
    total_met   = sum(sc_met.values())
    overall_sla = round(total_met / total_new * 100, 1) if total_new else 0.0
    op_cost_new = sum(sc_cost.values())
    penalty_new = sum(sc_missed[sev] * PENALTY_MAP[sev] for sev in [5, 4, 3, 2, 1])

    # ── KPI Cards ────────────────────────────────────────────
    kpi_sla     = make_kpi_card("Overall SLA", f"{overall_sla}%",
                                f"{total_met:,} of {total_new:,} claims")
    kpi_sev5    = make_kpi_card("Sev-5 SLA", f"{sc_sla[5]}%",
                                f"{sc_met[5]} of {new_counts[5]}")
    kpi_cost    = make_kpi_card("Operating Cost", f"${op_cost_new:,}",
                                "Deployed per diem")
    kpi_penalty = make_kpi_card("Penalty Exposure", f"${penalty_new:,}",
                                "SLA failure cost")

    # ── SLA Bar Chart ────────────────────────────────────────
    fig_sla = go.Figure()
    for sev in [5, 4, 3, 2, 1]:
        pct   = sc_sla[sev]
        color = GREEN if pct >= 90 else (GOLD if pct >= 70 else RED)
        is_s5 = sev == 5
        fig_sla.add_trace(go.Bar(
            x=[pct], y=[f"Sev-{sev}"],
            orientation="h",
            marker_color=color,
            marker_line=dict(width=0),
            text=[f"<b>{pct}%</b>"],
            texttemplate="%{text}",
            textposition="outside" if is_s5 else "inside",
            textfont=dict(
                family=FONT, size=11,
                color=RED if is_s5 else "#FFFFFF",
            ),
            showlegend=False,
        ))
    fig_sla.add_vline(
        x=90, line_dash="dash", line_color=RED, line_width=1.2,
        annotation_text=" 90%",
        annotation_font=dict(family=FONT, color=MUTED, size=9),
        annotation_position="top",
    )
    fig_sla.update_layout(**{
        **CHART_LAYOUT,
        "bargap": 0.3,
        "xaxis": dict(
            range=[0, 130],
            showline=False, showticklabels=False, ticks="",
            gridcolor="rgba(255,255,255,0.06)",
            zerolinecolor="rgba(255,255,255,0.06)",
        ),
        "yaxis": dict(
            gridcolor="rgba(255,255,255,0.06)",
            zerolinecolor="rgba(255,255,255,0.06)",
            tickfont=dict(family=FONT, color=TEXT, size=11),
        ),
        "showlegend": False,
        "height": 260,
        "margin": dict(l=10, r=50, t=10, b=10),
    })

    # ── Donut ─────────────────────────────────────────────────
    fig_donut = go.Figure(go.Pie(
        values=[total_met, total_new - total_met],
        hole=0.65,
        marker=dict(colors=[GOLD, DARK2]),
        textinfo="none",
        hovertemplate="<b>%{label}</b>: %{value}<extra></extra>",
        labels=["Met SLA", "Missed SLA"],
        direction="clockwise",
        sort=False,
    ))
    fig_donut.update_layout(
        annotations=[
            dict(text=f"<b>{overall_sla}%</b>", x=0.5, y=0.58,
                 font=dict(size=24, color="#FFFFFF", family=FONT),
                 showarrow=False),
            dict(text="Overall SLA", x=0.5, y=0.40,
                 font=dict(size=10, color=MUTED, family=FONT),
                 showarrow=False),
        ],
        showlegend=False,
        height=170,
        margin=dict(l=0, r=0, t=0, b=0),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
    )

    # ── Cost Gauge Bars ───────────────────────────────────────
    max_val     = max(op_cost_new, penalty_new, 1)
    cost_pct    = min(op_cost_new / max_val * 100, 100)
    penalty_pct = min(penalty_new / max_val * 100, 100)

    cost_gauge_fill = html.Div(
        f"${op_cost_new:,}",
        style={
            "backgroundColor": NAVY, "height": "28px", "borderRadius": "4px",
            "width": f"{cost_pct:.1f}%", "minWidth": "80px",
            "display": "flex", "alignItems": "center",
            "paddingLeft": "10px", "color": "#FFFFFF",
            "fontSize": "12px", "fontWeight": "600",
        },
    )
    penalty_gauge_fill = html.Div(
        f"${penalty_new:,}",
        style={
            "backgroundColor": GOLD, "height": "28px", "borderRadius": "4px",
            "width": f"{penalty_pct:.1f}%", "minWidth": "80px",
            "display": "flex", "alignItems": "center",
            "paddingLeft": "10px", "color": NAVY,
            "fontSize": "12px", "fontWeight": "600",
        },
    )

    # ── Delta Card ────────────────────────────────────────────
    is_default = all(new_counts[sev] == orig[sev] for sev in [5, 4, 3, 2, 1])
    if is_default:
        delta_content = html.Span(
            "Adjust sliders to see impact vs. baseline",
            className="text-muted",
            style={"fontSize": "12px", "fontStyle": "italic"},
        )
    else:
        base   = ALL_KPIS[run_key]
        d_sla  = round(overall_sla - base["overall_sla"], 1)
        d_s5   = round(sc_sla[5]   - base["sev5_sla"],    1)
        d_cost = op_cost_new - base["op_cost"]
        d_pen  = penalty_new - base["penalty"]

        def _ds(v, fmt="pp", invert=False):
            better = (v <= 0) if invert else (v >= 0)
            color  = GREEN if better else RED
            arrow  = "▲" if v >= 0 else "▼"
            txt    = (f"{arrow} {abs(v):.1f} pp"
                      if fmt == "pp" else f"{arrow} ${abs(v):,}")
            return html.Span(txt, style={"color": color, "fontWeight": "700"})

        sep = html.Span("  |  ", style={"color": MUTED})
        delta_content = html.Div([
            html.Span("vs. Baseline:  ",
                      style={"color": TEXT, "fontWeight": "700", "fontSize": "13px"}),
            html.Span("SLA  ",     style={"color": MUTED, "fontSize": "12px"}),
            _ds(d_sla), sep,
            html.Span("Sev-5  ",  style={"color": MUTED, "fontSize": "12px"}),
            _ds(d_s5), sep,
            html.Span("Cost  ",   style={"color": MUTED, "fontSize": "12px"}),
            _ds(d_cost, fmt="$", invert=True), sep,
            html.Span("Penalty  ", style={"color": MUTED, "fontSize": "12px"}),
            _ds(d_pen,  fmt="$", invert=True),
        ], style={"fontFamily": FONT, "fontSize": "12px", "lineHeight": "2"})

    return (
        kpi_sla, kpi_sev5, kpi_cost, kpi_penalty,
        fig_sla, fig_donut,
        cost_gauge_fill, penalty_gauge_fill,
        delta_content,
    )


@app.callback(
    Output("assignments-table", "data"),
    Input("run-selector", "value"),
    Input("assign-sev",   "value"),
    Input("assign-sla",   "value"),
)
def update_table(run_key, sev, sla_val):
    if not HAS_DATA:
        return []
    df = DATA[run_key]["assignments"].copy()
    df["sla_met"] = df["sla_met"].map({True: "True", False: "False"})
    if sev != "all":
        df = df[df["severity"] == int(sev)]
    if sla_val != "all":
        df = df[df["sla_met"] == sla_val]
    cols = ["day", "adj_id", "claim_id", "skill", "severity",
            "sla_deadline", "completion_day", "sla_met", "distance_miles"]
    return df[cols].round({"distance_miles": 1}).to_dict("records")


@app.callback(
    Output("adjuster-breakdown-content", "children"),
    Input("run-selector", "value"),
)
def update_adjuster_breakdown(run_key):
    if not HAS_DATA:
        return []
    df    = DATA[run_key]["assignments"]
    total = len(df)
    skill_counts = df.groupby("skill").size()
    return [
        make_skill_stat(f"PL{s}", skill_counts.get(s, 0), total)
        for s in [5, 4, 3, 2, 1]
    ]


@app.callback(
    Output("sev5-slider", "value"),
    Output("sev4-slider", "value"),
    Output("sev3-slider", "value"),
    Output("sev2-slider", "value"),
    Output("sev1-slider", "value"),
    Input("reset-btn", "n_clicks"),
    prevent_initial_call=True,
)
def reset_sliders(_):
    return 278, 211, 415, 91, 59


# ──────────────────────────────────────────────────────────────
#  ENTRY POINT
# ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("\n" + "=" * 58)
    print("  CATOPT Dashboard")
    print("=" * 58)
    if HAS_DATA:
        print(f"  Data : {DATA_DIR}")
        for k, v in DATA.items():
            n   = len(v["assignments"])
            met = int(v["assignments"]["sla_met"].sum())
            print(f"  {k} : {n} rows  |  SLA {round(met/n*100,1)}%")
    else:
        print(f"  NO DATA — copy CSVs to: {os.path.join(SCRIPT_DIR, 'data')}")
    print(f"  Open : http://localhost:8050")
    print("=" * 58 + "\n")
    app.run(debug=False, port=8050)
