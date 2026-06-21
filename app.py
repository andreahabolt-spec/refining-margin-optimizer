# app.py
# CRUDE NETBACK & REFINERY MARGIN OPTIMISER
# Phase 4 - simplified, chart-first dashboard + manual scenario builder
#
# Flow:  delivered crude cost  ->  product value (GPW)  ->  refining margin
#        ->  crude ranking  ->  crude-slate optimisation  ->  sensitivity
#
# Instead of pre-defined geopolitical shocks, a Manual Scenario Builder lets the
# user stress key variables (freight, insurance, port, differential, product
# prices, availability) for all crudes, a region, or a single crude, and see the
# impact on cost, margin, ranking and the optimal slate.
#
# All figures are illustrative and editable in the sidebar.

import streamlit as st
import pandas as pd
import pulp

st.set_page_config(page_title="Crude Netback & Refinery Margin Optimiser",
                   layout="wide")
st.title("Crude Netback & Refinery Margin Optimiser")
st.caption("North-West Europe refining economics - illustrative decision-support tool")

# ===========================================================================
# SIDEBAR
# ===========================================================================
st.sidebar.header("Controls")

st.sidebar.subheader("Refinery constraints")
throughput_capacity = st.sidebar.slider("Throughput capacity (kb/d)", 200, 900, 700, 25)
sulphur_max = st.sidebar.slider("Max blended sulphur (%)", 0.20, 2.00, 0.60, 0.05)

with st.sidebar.expander("Base market assumptions", expanded=False):
    BRENT = st.slider("Brent benchmark ($/bbl)", 40.0, 120.0, 82.0, 0.5)
    st.caption("Product prices ($/bbl)")
    price_lpg      = st.slider("LPG",             30.0, 90.0,  60.0,  1.0)
    price_naphtha  = st.slider("Naphtha",         40.0, 100.0, 76.0,  1.0)
    price_gasoline = st.slider("Gasoline",        60.0, 150.0, 98.0,  1.0)
    price_jet      = st.slider("Jet / Kerosene",  60.0, 140.0, 102.0, 1.0)
    price_diesel   = st.slider("Diesel / Gasoil", 60.0, 150.0, 112.0, 1.0)
    price_fueloil  = st.slider("Fuel Oil",        30.0, 100.0, 62.0,  1.0)
    st.caption("Processing cost ($/bbl)")
    base_processing = st.slider("Base processing cost",     0.0, 8.0, 2.5, 0.1)
    sulphur_penalty = st.slider("Sulphur penalty (per %S)", 0.0, 3.0, 1.0, 0.1)

st.sidebar.subheader("Manual scenario builder")
st.sidebar.caption("Stress the market and re-solve. Zero = base case.")
scope = st.sidebar.selectbox("Apply adjustments to",
                             ["All crudes", "North Sea", "Middle East", "Caspian",
                              "US Gulf", "Single crude"])
crude_choice = None
brent_adj = st.sidebar.slider("Brent adjustment ($/bbl)", -15.0, 15.0, 0.0, 0.5)
freight_pct = st.sidebar.slider("Freight adjustment (%)", -50, 150, 0, 5)
insurance_pct = st.sidebar.slider("Cargo insurance adjustment (%)", -50, 300, 0, 10)
port_pct = st.sidebar.slider("Port / handling adjustment (%)", -50, 150, 0, 5)
diff_adj = st.sidebar.slider("Crude differential adjustment ($/bbl)", -10.0, 10.0, 0.0, 0.5)
avail_pct = st.sidebar.slider("Availability adjustment (%)", -100, 100, 0, 5)
with st.sidebar.expander("Product price adjustments ($/bbl)"):
    adj_gasoline = st.slider("Gasoline adj", -25.0, 25.0, 0.0, 1.0)
    adj_jet      = st.slider("Jet adj",      -25.0, 25.0, 0.0, 1.0)
    adj_diesel   = st.slider("Diesel adj",   -25.0, 25.0, 0.0, 1.0)
    adj_fueloil  = st.slider("Fuel Oil adj", -25.0, 25.0, 0.0, 1.0)
    adj_naphtha  = st.slider("Naphtha adj",  -25.0, 25.0, 0.0, 1.0)
    adj_lpg      = st.slider("LPG adj",      -25.0, 25.0, 0.0, 1.0)

# ===========================================================================
# DATA
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
crudes["Availability_kbd"] = crudes["Availability_kbd"].astype(float)

if scope == "Single crude":
    crude_choice = st.sidebar.selectbox("Which crude", list(crudes["Crude"]))

base_prices = {"lpg": price_lpg, "naphtha": price_naphtha, "gasoline": price_gasoline,
               "jet": price_jet, "diesel": price_diesel, "fueloil": price_fueloil}
scenario_prices = {"lpg": price_lpg + adj_lpg, "naphtha": price_naphtha + adj_naphtha,
                   "gasoline": price_gasoline + adj_gasoline, "jet": price_jet + adj_jet,
                   "diesel": price_diesel + adj_diesel, "fueloil": price_fueloil + adj_fueloil}

# ===========================================================================
# FUNCTIONS
# ===========================================================================
def scope_mask(df, scope, crude_choice):
    """Boolean mask for which crudes a manual adjustment applies to."""
    if scope == "All crudes":
        return pd.Series(True, index=df.index)
    if scope == "Single crude":
        return df["Crude"] == crude_choice
    return df["Region"] == scope  # one of the region names

def apply_scenario(df, mask):
    """Apply the sidebar's manual adjustments to the masked crudes."""
    df = df.copy()
    df.loc[mask, "Freight"]          *= 1 + freight_pct / 100
    df.loc[mask, "Cargo_Insurance"]  *= 1 + insurance_pct / 100
    df.loc[mask, "Port_Handling"]    *= 1 + port_pct / 100
    df.loc[mask, "Diff_vs_Brent"]    += diff_adj
    df.loc[mask, "Availability_kbd"] *= 1 + avail_pct / 100
    return df

def compute_economics(df, prices, brent):
    df = df.copy()
    df["Logistics_Cost"] = df["Freight"] + df["Cargo_Insurance"] + df["Port_Handling"]
    df["FOB_Price"] = brent + df["Diff_vs_Brent"]
    df["Delivered_Cost"] = df["FOB_Price"] + df["Logistics_Cost"]
    df["GPW"] = (
        df["LPG_%"] * prices["lpg"] + df["Naphtha_%"] * prices["naphtha"]
        + df["Gasoline_%"] * prices["gasoline"] + df["Jet_%"] * prices["jet"]
        + df["Diesel_%"] * prices["diesel"] + df["FuelOil_%"] * prices["fueloil"]
    ) / 100.0
    df["Processing_Cost"] = base_processing + sulphur_penalty * df["Sulphur_%"]
    df["Netback_FOB"] = df["GPW"] - df["Processing_Cost"] - df["Logistics_Cost"]
    df["Refining_Margin"] = df["GPW"] - df["Delivered_Cost"] - df["Processing_Cost"]
    return df

def optimise_slate(df, capacity, smax):
    """LP: choose crude volumes (kb/d) to maximise margin under throughput,
    availability and blended-sulphur limits."""
    df = df.reset_index(drop=True)
    prob = pulp.LpProblem("crude_slate", pulp.LpMaximize)
    vol = {r["Crude"]: pulp.LpVariable(f"v_{i}", lowBound=0,
                                       upBound=max(float(r["Availability_kbd"]), 0.0))
           for i, r in df.iterrows()}
    prob += pulp.lpSum(r["Refining_Margin"] * vol[r["Crude"]] for _, r in df.iterrows())
    prob += (pulp.lpSum(vol.values()) <= capacity, "Throughput")
    prob += (pulp.lpSum((r["Sulphur_%"] - smax) * vol[r["Crude"]] for _, r in df.iterrows()) <= 0,
             "Sulphur")
    prob.solve(pulp.PULP_CBC_CMD(msg=0))
    volumes = pd.Series({c: round(vol[c].value() or 0.0, 1) for c in vol}, name="kb/d")
    total = float(volumes.sum())
    sulf_map = dict(zip(df["Crude"], df["Sulphur_%"]))
    avail_map = dict(zip(df["Crude"], df["Availability_kbd"]))
    margin_map = dict(zip(df["Crude"], df["Refining_Margin"]))
    total_margin = sum(margin_map[c] * volumes[c] for c in volumes.index)
    blended_s = (sum(sulf_map[c] * volumes[c] for c in volumes.index) / total) if total > 0 else 0.0
    if total > 0 and abs(blended_s - smax) < 1e-3:
        binding_short = "Blended sulphur"
    elif total > 0 and abs(total - capacity) < 0.5:
        binding_short = "Throughput"
    elif total > 0:
        binding_short = "Crude availability"
    else:
        binding_short = "None (idle)"
    maxed = [c for c in volumes.index if volumes[c] > avail_map[c] - 0.5 and volumes[c] > 0.5]
    details = []
    if total > 0 and abs(total - capacity) < 0.5: details.append("throughput")
    if total > 0 and abs(blended_s - smax) < 1e-3: details.append("blended sulphur limit")
    if maxed: details.append("availability of " + ", ".join(maxed))
    return {"volumes": volumes, "total": total, "total_margin": total_margin,
            "blended_s": blended_s, "binding_short": binding_short,
            "binding_text": "; ".join(details) if details else "none - spare room"}

# ----- Run base case and scenario -----
adjustments = [brent_adj, freight_pct, insurance_pct, port_pct, diff_adj, avail_pct,
               adj_gasoline, adj_jet, adj_diesel, adj_fueloil, adj_naphtha, adj_lpg]
scenario_active = any(a != 0 for a in adjustments)

base = compute_economics(crudes, base_prices, BRENT)
mask = scope_mask(crudes, scope, crude_choice)
scenario = compute_economics(apply_scenario(crudes, mask), scenario_prices, BRENT + brent_adj)
scenario_brent = BRENT + brent_adj

ranked = scenario.sort_values("Refining_Margin", ascending=False).reset_index(drop=True)
base_slate = optimise_slate(base, throughput_capacity, sulphur_max)
slate = optimise_slate(scenario, throughput_capacity, sulphur_max)

# ===========================================================================
# 1. EXECUTIVE SUMMARY
# ===========================================================================
st.header("1. Executive summary")
if scenario_active:
    st.caption(f"Showing your SCENARIO (adjustments applied to: {scope}). "
               "Base-case comparison is in section 7.")
else:
    st.caption("Showing the base case. Build a scenario with the sidebar sliders.")

best, worst = ranked.iloc[0], ranked.iloc[-1]
hi = scenario.loc[scenario["Delivered_Cost"].idxmax()]
lo = scenario.loc[scenario["Delivered_Cost"].idxmin()]
r1 = st.columns(3)
r1[0].metric("Best refining margin", best["Crude"], f"{best['Refining_Margin']:.2f} $/bbl")
r1[1].metric("Worst refining margin", worst["Crude"], f"{worst['Refining_Margin']:.2f} $/bbl")
r1[2].metric("Brent benchmark", f"${scenario_brent:.2f}")
r2 = st.columns(3)
r2[0].metric("Lowest delivered cost", lo["Crude"], f"${lo['Delivered_Cost']:.2f}/bbl")
r2[1].metric("Highest delivered cost", hi["Crude"], f"${hi['Delivered_Cost']:.2f}/bbl")
r2[2].metric("Optimiser binding constraint", slate["binding_short"])

# ===========================================================================
# 2. CRUDE QUALITY & LOGISTICS
# ===========================================================================
st.header("2. Crude quality & logistics")
st.caption("Quality map: x = API (higher is lighter), y = sulphur (higher is sourer), "
           "bubble size = availability, colour = region. Light sweet crudes sit bottom-right; "
           "heavier, sourer grades sit top-left.")
st.scatter_chart(scenario, x="API", y="Sulphur_%", size="Availability_kbd", color="Region")
st.dataframe(
    scenario[["Crude", "Region", "Route", "Freight", "Cargo_Insurance",
              "Port_Handling", "Delivered_Cost"]].round(2),
    use_container_width=True, hide_index=True)

# ===========================================================================
# 3. DELIVERED COST BUILD-UP
# ===========================================================================
st.header("3. Delivered cost build-up ($/bbl)")
st.caption("FOB price + freight + cargo insurance + port/handling = delivered cost. "
           "A low FOB price can be offset by long-haul freight and insurance.")
st.bar_chart(scenario.set_index("Crude")[["FOB_Price", "Freight",
                                          "Cargo_Insurance", "Port_Handling"]])

# ===========================================================================
# 4. PRODUCT YIELDS & GROSS PRODUCT WORTH
# ===========================================================================
st.header("4. Product yields & gross product worth")
st.caption("Yields sum to 100%. Light sweet crudes yield more gasoline, jet and diesel "
           "(high value); heavier or sourer crudes yield more fuel oil / residue. "
           "Gross product worth = sum of (yield x product price).")
st.bar_chart(scenario.set_index("Crude")[yield_cols])

# ===========================================================================
# 5. REFINING MARGIN RANKING
# ===========================================================================
st.header("5. Refining margin ranking ($/bbl)")
st.caption("Refining margin = gross product worth - delivered cost - processing cost.")
st.bar_chart(ranked.set_index("Crude")["Refining_Margin"])
st.dataframe(
    ranked[["Crude", "Delivered_Cost", "GPW", "Processing_Cost",
            "Netback_FOB", "FOB_Price", "Refining_Margin"]].round(2),
    use_container_width=True, hide_index=True)

# ===========================================================================
# 6. CRUDE SLATE OPTIMISATION
# ===========================================================================
st.header("6. Crude slate optimisation")
o = st.columns(4)
o[0].metric("Total run", f"{slate['total']:.0f} kb/d")
o[1].metric("Total margin", f"${slate['total_margin']:,.0f}k/day")
o[2].metric("Blended sulphur", f"{slate['blended_s']:.2f}%")
o[3].metric("Binding", slate["binding_short"])
st.caption("The optimiser does not just pick the highest standalone margin - it chooses the "
           "best MIX of crudes under availability, throughput and sulphur limits. "
           f"Binding constraint(s): {slate['binding_text']}.")
chosen = slate["volumes"][slate["volumes"] > 0].sort_values()
if len(chosen) > 0:
    st.bar_chart(chosen, horizontal=True)
else:
    st.warning("At these assumptions no crude is profitable to run - the refinery stays idle.")

# ===========================================================================
# 7. MANUAL SCENARIO BUILDER / SENSITIVITY
# ===========================================================================
st.header("7. Manual scenario builder / sensitivity")
st.caption("This tool does not forecast geopolitical shocks. Instead, it lets you manually "
           "stress key market and logistics variables - freight, cargo insurance, crude "
           "differentials, product prices and availability - for all crudes, a region, or one "
           "crude. This keeps the model flexible and easy to defend in an interview.")
if scenario_active:
    change = (scenario.set_index("Crude")["Refining_Margin"]
              - base.set_index("Crude")["Refining_Margin"])
    delta_opt = slate["total_margin"] - base_slate["total_margin"]
    st.write(f"**Optimal total margin:** base ${base_slate['total_margin']:,.0f}k/day "
             f"->  scenario ${slate['total_margin']:,.0f}k/day  ({delta_opt:+,.0f}k/day)")
    st.caption("Margin change by crude ($/bbl): scenario minus base case")
    st.bar_chart(change)
    comparison = pd.DataFrame({
        "Crude": base["Crude"].values,
        "Margin_base": base["Refining_Margin"].round(2).values,
        "Margin_scenario": scenario["Refining_Margin"].round(2).values,
        "Margin_change": (scenario["Refining_Margin"] - base["Refining_Margin"]).round(2).values,
    }).sort_values("Margin_scenario", ascending=False)
    st.dataframe(comparison, use_container_width=True, hide_index=True)
else:
    st.info("No adjustments yet - move the scenario sliders in the sidebar to stress the model "
            "and a base-vs-scenario comparison will appear here.")

# ===========================================================================
# 8. DETAILED DATA (tables tucked away)
# ===========================================================================
st.header("8. Detailed data")
with st.expander("Crude profiles (quality, origin, risk)"):
    st.dataframe(scenario[["Crude", "Region", "Route", "Quality", "API", "Sulphur_%",
                           "Availability_kbd", "Geo_Risk"]].round(2),
                 use_container_width=True, hide_index=True)
with st.expander("Delivered cost build-up (table)"):
    st.dataframe(scenario[["Crude", "Diff_vs_Brent", "FOB_Price", "Freight",
                           "Cargo_Insurance", "Port_Handling", "Delivered_Cost"]].round(2),
                 use_container_width=True, hide_index=True)
with st.expander("Full economics table"):
    st.dataframe(ranked[["Crude", "Quality", "Delivered_Cost", "GPW", "Processing_Cost",
                         "Netback_FOB", "FOB_Price", "Refining_Margin"]].round(2),
                 use_container_width=True, hide_index=True)