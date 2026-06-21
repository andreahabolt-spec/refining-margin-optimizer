# app.py
# CRUDE NETBACK & REFINERY MARGIN OPTIMISER
# Phase 2 - Step 4: geopolitical shock module
#
# A scenario selector applies region-based shocks to freight, cargo insurance,
# crude availability and the differential to Brent. The model recomputes
# netbacks and margins under the shock and compares them with the calm base
# case, so the ranking reshuffles live.
#
#   Delivered Cost   = FOB + Freight + Insurance + Port/Handling
#   Gross Product Worth (GPW) = sum(product yield % x product price)
#   Refining Margin  = GPW - Delivered Cost - Processing Cost
#   Netback (FOB)    = GPW - Processing Cost - Logistics   (Margin = Netback - FOB)
#
# All figures are illustrative and editable in the sidebar.

import streamlit as st
import pandas as pd

# --- Page setup -------------------------------------------------------------
st.set_page_config(page_title="Crude Netback & Refinery Margin Optimiser",
                   layout="wide")
st.title("Crude Netback & Refinery Margin Optimiser")
st.caption("North-West Europe refining economics - illustrative model")

# ===========================================================================
# GEOPOLITICAL SHOCK SCENARIOS
# Each scenario lists, by region, the multipliers/adjustments to apply:
#   freight / insurance / availability are MULTIPLIERS (1.35 = +35%)
#   diff is an ADDITIVE widening of the crude's differential to Brent ($/bbl)
# A shock only touches the regions named in it.
# ===========================================================================
SHOCKS = {
    "None (base case)": {},
    "Middle East / Hormuz disruption": {
        "Middle East": {"freight": 1.35, "insurance": 1.60, "availability": 0.80, "diff": 1.50},
    },
    "Caspian / Black Sea disruption": {
        "Caspian": {"freight": 1.25, "insurance": 1.80, "availability": 0.85, "diff": 1.00},
    },
    "North Sea outage": {
        "North Sea": {"freight": 1.10, "insurance": 1.20, "availability": 0.65, "diff": 2.00},
    },
    "Transatlantic freight spike": {
        "US Gulf": {"freight": 1.50, "insurance": 1.10, "availability": 1.00, "diff": 0.50},
    },
    "Global port congestion": {
        "North Sea":   {"freight": 1.15, "insurance": 1.10, "availability": 0.95, "diff": 0.30},
        "US Gulf":     {"freight": 1.15, "insurance": 1.10, "availability": 0.95, "diff": 0.30},
        "Caspian":     {"freight": 1.15, "insurance": 1.10, "availability": 0.95, "diff": 0.30},
        "Middle East": {"freight": 1.15, "insurance": 1.10, "availability": 0.95, "diff": 0.30},
    },
}

# ===========================================================================
# SIDEBAR - all interactive controls live here
# Streamlit re-runs the whole script whenever a control changes.
# ===========================================================================
st.sidebar.header("Controls")

st.sidebar.subheader("Geopolitical scenario")
scenario = st.sidebar.selectbox("Active scenario", list(SHOCKS.keys()))

st.sidebar.subheader("Market assumptions")
BRENT = st.sidebar.slider("Brent benchmark ($/bbl)", 40.0, 120.0, 82.0, 0.5)

st.sidebar.caption("Product prices ($/bbl)")
price_lpg      = st.sidebar.slider("LPG",             30.0, 90.0,  60.0,  1.0)
price_naphtha  = st.sidebar.slider("Naphtha",         40.0, 100.0, 76.0,  1.0)
price_gasoline = st.sidebar.slider("Gasoline",        60.0, 150.0, 98.0,  1.0)
price_jet      = st.sidebar.slider("Jet / Kerosene",  60.0, 140.0, 102.0, 1.0)
price_diesel   = st.sidebar.slider("Diesel / Gasoil", 60.0, 150.0, 112.0, 1.0)
price_fueloil  = st.sidebar.slider("Fuel Oil",        30.0, 100.0, 62.0,  1.0)

st.sidebar.caption("Processing cost ($/bbl)")
base_processing = st.sidebar.slider("Base processing cost",     0.0, 8.0, 2.5, 0.1)
sulphur_penalty = st.sidebar.slider("Sulphur penalty (per %S)", 0.0, 3.0, 1.0, 0.1)

# ===========================================================================
# CRUDE DATA
# ===========================================================================
crude_data = [
    {"Crude": "Ekofisk",        "Region": "North Sea",  "Route": "North Sea to NWE",              "Quality": "Light sweet", "API": 37.5, "Sulphur_%": 0.25, "Diff_vs_Brent": 1.50,  "Freight": 0.60, "Cargo_Insurance": 0.05, "Port_Handling": 0.30, "Availability_kbd": 60,  "Geo_Risk": "Low"},
    {"Crude": "Forties",        "Region": "North Sea",  "Route": "North Sea to NWE",              "Quality": "Light sour",  "API": 40.0, "Sulphur_%": 0.60, "Diff_vs_Brent": 0.30,  "Freight": 0.55, "Cargo_Insurance": 0.05, "Port_Handling": 0.30, "Availability_kbd": 80,  "Geo_Risk": "Low"},
    {"Crude": "Johan Sverdrup", "Region": "North Sea",  "Route": "North Sea to NWE",              "Quality": "Medium sour", "API": 28.0, "Sulphur_%": 0.80, "Diff_vs_Brent": -2.00, "Freight": 0.60, "Cargo_Insurance": 0.05, "Port_Handling": 0.30, "Availability_kbd": 120, "Geo_Risk": "Low"},
    {"Crude": "WTI Midland",    "Region": "US Gulf",    "Route": "US Gulf to NWE (transatlantic)","Quality": "Light sweet", "API": 42.0, "Sulphur_%": 0.20, "Diff_vs_Brent": 0.80,  "Freight": 2.50, "Cargo_Insurance": 0.08, "Port_Handling": 0.35, "Availability_kbd": 150, "Geo_Risk": "Low"},
    {"Crude": "CPC Blend",      "Region": "Caspian",    "Route": "CPC / Black Sea to NWE",        "Quality": "Light sour",  "API": 45.0, "Sulphur_%": 0.55, "Diff_vs_Brent": -1.50, "Freight": 2.40, "Cargo_Insurance": 0.15, "Port_Handling": 0.40, "Availability_kbd": 100, "Geo_Risk": "High"},
    {"Crude": "Azeri Light",    "Region": "Caspian",    "Route": "BTC / Ceyhan (Med) to NWE",     "Quality": "Light sweet", "API": 36.6, "Sulphur_%": 0.15, "Diff_vs_Brent": 1.20,  "Freight": 2.20, "Cargo_Insurance": 0.12, "Port_Handling": 0.35, "Availability_kbd": 70,  "Geo_Risk": "Medium"},
    {"Crude": "Arab Light",     "Region": "Middle East","Route": "Persian Gulf to NWE",           "Quality": "Medium sour", "API": 33.0, "Sulphur_%": 1.80, "Diff_vs_Brent": -3.50, "Freight": 3.20, "Cargo_Insurance": 0.18, "Port_Handling": 0.40, "Availability_kbd": 200, "Geo_Risk": "High"},
    {"Crude": "Basrah Medium",  "Region": "Middle East","Route": "Persian Gulf to NWE",           "Quality": "Medium sour", "API": 30.0, "Sulphur_%": 2.70, "Diff_vs_Brent": -4.50, "Freight": 3.40, "Cargo_Insurance": 0.22, "Port_Handling": 0.40, "Availability_kbd": 120, "Geo_Risk": "High"},
]
crudes = pd.DataFrame(crude_data)

yield_data = [
    {"Crude": "Ekofisk",        "LPG_%": 3, "Naphtha_%": 12, "Gasoline_%": 22, "Jet_%": 12, "Diesel_%": 33, "FuelOil_%": 18},
    {"Crude": "Forties",        "LPG_%": 3, "Naphtha_%": 11, "Gasoline_%": 21, "Jet_%": 11, "Diesel_%": 32, "FuelOil_%": 22},
    {"Crude": "Johan Sverdrup", "LPG_%": 2, "Naphtha_%": 8,  "Gasoline_%": 13, "Jet_%": 10, "Diesel_%": 32, "FuelOil_%": 35},
    {"Crude": "WTI Midland",    "LPG_%": 4, "Naphtha_%": 14, "Gasoline_%": 26, "Jet_%": 11, "Diesel_%": 31, "FuelOil_%": 14},
    {"Crude": "CPC Blend",      "LPG_%": 4, "Naphtha_%": 16, "Gasoline_%": 24, "Jet_%": 10, "Diesel_%": 28, "FuelOil_%": 18},
    {"Crude": "Azeri Light",    "LPG_%": 3, "Naphtha_%": 11, "Gasoline_%": 20, "Jet_%": 13, "Diesel_%": 36, "FuelOil_%": 17},
    {"Crude": "Arab Light",     "LPG_%": 2, "Naphtha_%": 9,  "Gasoline_%": 15, "Jet_%": 11, "Diesel_%": 30, "FuelOil_%": 33},
    {"Crude": "Basrah Medium",  "LPG_%": 2, "Naphtha_%": 8,  "Gasoline_%": 12, "Jet_%": 9,  "Diesel_%": 29, "FuelOil_%": 40},
]
yields = pd.DataFrame(yield_data)

yield_cols = ["LPG_%", "Naphtha_%", "Gasoline_%", "Jet_%", "Diesel_%", "FuelOil_%"]
if (yields[yield_cols].sum(axis=1) != 100).any():
    st.error("Some crude yields do not sum to 100%. Please check the yield table.")

crudes = crudes.merge(yields, on="Crude")

# ===========================================================================
# CALCULATION FUNCTIONS
# We put the economics in a function so we can run it twice - once for the
# calm base case and once for the shocked case - and compare the two.
# ===========================================================================
def apply_shock(df, scenario_name):
    """Return a copy of df with the chosen scenario's region adjustments applied."""
    df = df.copy()
    for region, adj in SHOCKS.get(scenario_name, {}).items():
        mask = df["Region"] == region
        df.loc[mask, "Freight"]          *= adj.get("freight", 1.0)
        df.loc[mask, "Cargo_Insurance"]  *= adj.get("insurance", 1.0)
        df.loc[mask, "Availability_kbd"] *= adj.get("availability", 1.0)
        df.loc[mask, "Diff_vs_Brent"]    += adj.get("diff", 0.0)
    return df

def compute_economics(df):
    """Add cost, value, netback and margin columns to a crude table."""
    df = df.copy()
    df["Logistics_Cost"] = df["Freight"] + df["Cargo_Insurance"] + df["Port_Handling"]
    df["FOB_Price"] = BRENT + df["Diff_vs_Brent"]
    df["Delivered_Cost"] = df["FOB_Price"] + df["Logistics_Cost"]
    df["GPW"] = (
        df["LPG_%"]      * price_lpg
        + df["Naphtha_%"]  * price_naphtha
        + df["Gasoline_%"] * price_gasoline
        + df["Jet_%"]      * price_jet
        + df["Diesel_%"]   * price_diesel
        + df["FuelOil_%"]  * price_fueloil
    ) / 100.0
    df["Processing_Cost"] = base_processing + sulphur_penalty * df["Sulphur_%"]
    df["Netback_FOB"] = df["GPW"] - df["Processing_Cost"] - df["Logistics_Cost"]
    df["Refining_Margin"] = df["GPW"] - df["Delivered_Cost"] - df["Processing_Cost"]
    return df

def describe_scenario(scenario_name):
    """Build a short text description of what the active scenario changes."""
    adjustments = SHOCKS.get(scenario_name, {})
    if not adjustments:
        return "No shock applied - base case economics."
    parts = []
    for region, adj in adjustments.items():
        bits = []
        if adj.get("freight", 1) != 1:      bits.append(f"freight x{adj['freight']}")
        if adj.get("insurance", 1) != 1:    bits.append(f"insurance x{adj['insurance']}")
        if adj.get("availability", 1) != 1: bits.append(f"availability x{adj['availability']}")
        if adj.get("diff", 0) != 0:         bits.append(f"differential +{adj['diff']}")
        parts.append(f"{region}: " + ", ".join(bits))
    return "  |  ".join(parts)

# Run the model for the base case and the shocked case.
base = compute_economics(crudes)
shocked = compute_economics(apply_shock(crudes, scenario))
shocked["Margin_change"] = shocked["Refining_Margin"] - base["Refining_Margin"]

ranked = shocked.sort_values("Refining_Margin", ascending=False).reset_index(drop=True)

# ===========================================================================
# DISPLAY
# ===========================================================================
shock_active = bool(SHOCKS[scenario])
if shock_active:
    st.warning(f"Active scenario: {scenario}")
    st.caption("Effects ->  " + describe_scenario(scenario))
    hit = ranked.loc[ranked["Margin_change"].idxmin()]
    st.caption(f"Hardest hit: {hit['Crude']}  ({hit['Margin_change']:+.2f} $/bbl vs base case)")
else:
    st.success("Base case - no geopolitical shock applied")

top, worst = ranked.iloc[0], ranked.iloc[-1]
c1, c2, c3 = st.columns(3)
c1.metric("Most profitable", top["Crude"],   f"{top['Refining_Margin']:.2f} $/bbl")
c2.metric("Least profitable", worst["Crude"], f"{worst['Refining_Margin']:.2f} $/bbl")
c3.metric("Brent benchmark", f"${BRENT:.2f}")

st.subheader("Refining margin by crude ($/bbl)")
st.bar_chart(ranked.set_index("Crude")["Refining_Margin"])

st.subheader("Netback & margin ranking ($/bbl)")
st.caption("Netback (break-even FOB) = the most you would pay for the crude. "
           "Margin = Netback - actual FOB price. Buy when FOB < Netback.")
econ_cols = ["Crude", "GPW", "Processing_Cost", "Logistics_Cost",
             "Netback_FOB", "FOB_Price", "Refining_Margin"]
if shock_active:
    econ_cols.append("Margin_change")
st.dataframe(ranked[econ_cols].round(2), use_container_width=True, hide_index=True)

st.subheader("Product yield structure (% of barrel)")
st.dataframe(ranked[["Crude", "Quality"] + yield_cols],
             use_container_width=True, hide_index=True)

with st.expander("Show delivered cost build-up ($/bbl)"):
    cost_cols = ["Crude", "Diff_vs_Brent", "FOB_Price", "Freight",
                 "Cargo_Insurance", "Port_Handling", "Delivered_Cost"]
    st.dataframe(ranked[cost_cols].round(2), use_container_width=True, hide_index=True)

with st.expander("Show crude profiles (quality, origin, risk)"):
    profile_cols = ["Crude", "Region", "Route", "API", "Sulphur_%",
                    "Availability_kbd", "Geo_Risk"]
    st.dataframe(ranked[profile_cols].round(2), use_container_width=True, hide_index=True)

st.info(
    "Pick a scenario in the sidebar and watch the ranking move. A "
    "**Middle East / Hormuz** shock lifts Arab Light and Basrah freight and "
    "cargo insurance, widens their differentials and cuts their availability - "
    "so the sour Gulf grades fall and the short-haul North Sea barrels look "
    "even better. A **North Sea outage** does the reverse. This is the heart of "
    "supply-chain risk: the same shock hits each crude differently depending on "
    "where it is produced and how it travels."
)