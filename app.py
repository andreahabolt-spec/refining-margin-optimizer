# app.py
# CRUDE NETBACK & REFINERY MARGIN OPTIMISER
# Phase 3 - Step 6: two-sided shock module (disruption / relief / mixed) + severity
#
# Shock types:
#   disruption -> freight up, insurance up, availability down, differential up
#   relief     -> freight down, insurance down, availability up, differential down
#   mixed      -> like relief on crude, BUT product cracks also fall (demand collapse)
# A single severity factor (Mild 0.5, Severe 1.0, Extreme 1.6) scales every
# effect's deviation from neutral, so higher severity intensifies any shock.
#
# Key lesson: a "positive" shock for crude buyers (cheaper crude) does NOT
# guarantee a better refining margin - if product cracks fall too (mixed shock),
# gross product worth drops and the net margin can still worsen.
#
# All figures are illustrative and editable in the sidebar.

import streamlit as st
import pandas as pd
import pulp

# --- Page setup -------------------------------------------------------------
st.set_page_config(page_title="Crude Netback & Refinery Margin Optimiser",
                   layout="wide")
st.title("Crude Netback & Refinery Margin Optimiser")
st.caption("North-West Europe refining economics - illustrative model")

# ===========================================================================
# SHOCK SCENARIOS
# Each scenario has a "type" and, per region, multipliers/adjustments at the
# "Severe" level (severity rescales them). Multipliers: 1.0 = no change.
# diff is an additive change to the crude's differential to Brent ($/bbl).
# "product_cracks" (mixed only) lowers product prices ($/bbl).
# ===========================================================================
SHOCKS = {
    "None (base case)": {"type": "none"},

    # --- Disruption shocks (crude gets more expensive / scarcer) ---
    "Middle East / Hormuz disruption": {"type": "disruption",
        "Middle East": {"freight": 1.50, "insurance": 2.00, "availability": 0.65, "diff": 2.50}},
    "Caspian / Black Sea disruption": {"type": "disruption",
        "Caspian": {"freight": 1.35, "insurance": 1.80, "availability": 0.75, "diff": 1.50}},
    "North Sea outage": {"type": "disruption",
        "North Sea": {"freight": 1.15, "insurance": 1.30, "availability": 0.60, "diff": 2.50}},
    "Transatlantic freight spike": {"type": "disruption",
        "US Gulf": {"freight": 1.60, "insurance": 1.15, "availability": 0.95, "diff": 0.80}},
    "Global port congestion": {"type": "disruption",
        "North Sea":   {"freight": 1.20, "insurance": 1.15, "availability": 0.92, "diff": 0.40},
        "US Gulf":     {"freight": 1.25, "insurance": 1.15, "availability": 0.92, "diff": 0.40},
        "Caspian":     {"freight": 1.20, "insurance": 1.15, "availability": 0.92, "diff": 0.40},
        "Middle East": {"freight": 1.20, "insurance": 1.15, "availability": 0.92, "diff": 0.40}},

    # --- Relief shocks (crude gets cheaper / more available) ---
    "Middle East supply normalisation": {"type": "relief",
        "Middle East": {"freight": 0.80, "insurance": 0.70, "availability": 1.20, "diff": -2.00}},
    "Strait of Hormuz reopening": {"type": "relief",
        "Middle East": {"freight": 0.75, "insurance": 0.60, "availability": 1.25, "diff": -2.50}},
    "Global crude oversupply": {"type": "relief",
        "North Sea":   {"freight": 0.90, "insurance": 0.95, "availability": 1.15, "diff": -1.50},
        "US Gulf":     {"freight": 0.85, "insurance": 0.95, "availability": 1.20, "diff": -2.00},
        "Caspian":     {"freight": 0.90, "insurance": 0.95, "availability": 1.15, "diff": -1.50},
        "Middle East": {"freight": 0.85, "insurance": 0.90, "availability": 1.25, "diff": -2.50}},
    "Storage pressure / distressed crude pricing": {"type": "relief",
        "North Sea":   {"freight": 0.90, "insurance": 0.95, "availability": 1.20, "diff": -3.00},
        "US Gulf":     {"freight": 0.88, "insurance": 0.95, "availability": 1.20, "diff": -3.50},
        "Caspian":     {"freight": 0.90, "insurance": 0.95, "availability": 1.20, "diff": -3.50},
        "Middle East": {"freight": 0.88, "insurance": 0.92, "availability": 1.25, "diff": -4.00}},

    # --- Mixed shock (oversupply of crude AND collapse in product demand) ---
    "COVID-style demand collapse / oversupply": {"type": "mixed",
        "North Sea":   {"freight": 0.85, "insurance": 0.95, "availability": 1.20, "diff": -3.00},
        "US Gulf":     {"freight": 0.80, "insurance": 0.95, "availability": 1.25, "diff": -3.50},
        "Caspian":     {"freight": 0.85, "insurance": 0.95, "availability": 1.20, "diff": -3.00},
        "Middle East": {"freight": 0.80, "insurance": 0.90, "availability": 1.30, "diff": -4.00},
        "product_cracks": {"lpg": -2.0, "naphtha": -4.0, "gasoline": -9.0,
                           "jet": -10.0, "diesel": -6.0, "fuel_oil": -2.0}},
}
SEVERITY = {"Mild": 0.5, "Severe": 1.0, "Extreme": 1.6}

TYPE_LABEL = {"disruption": "Disruption shock", "relief": "Relief / oversupply shock",
              "mixed": "Mixed shock (oversupply + demand collapse)", "none": "Base case"}

# ===========================================================================
# SIDEBAR - all interactive controls
# ===========================================================================
st.sidebar.header("Controls")

st.sidebar.subheader("Shock scenario")
scenario = st.sidebar.selectbox("Scenario", list(SHOCKS.keys()))
severity = st.sidebar.selectbox("Severity", list(SEVERITY.keys()), index=1)
sev = SEVERITY[severity]

st.sidebar.subheader("Refinery constraints")
throughput_capacity = st.sidebar.slider("Throughput capacity (kb/d)", 200, 900, 700, 25)
sulphur_max = st.sidebar.slider("Max blended sulphur (%)", 0.20, 2.00, 0.60, 0.05)

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

base_prices = {"lpg": price_lpg, "naphtha": price_naphtha, "gasoline": price_gasoline,
               "jet": price_jet, "diesel": price_diesel, "fueloil": price_fueloil}

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
crudes["Availability_kbd"] = crudes["Availability_kbd"].astype(float)  # so shocks can scale it

# ===========================================================================
# CALCULATION FUNCTIONS
# ===========================================================================
def apply_shock(df, scenario_name, severity_factor):
    """Apply a scenario's region adjustments, scaled by severity (deviation from neutral)."""
    df = df.copy()
    for region, adj in SHOCKS.get(scenario_name, {}).items():
        if region in ("type", "product_cracks"):
            continue
        mask = df["Region"] == region
        df.loc[mask, "Freight"]          *= 1 + (adj.get("freight", 1.0) - 1) * severity_factor
        df.loc[mask, "Cargo_Insurance"]  *= 1 + (adj.get("insurance", 1.0) - 1) * severity_factor
        df.loc[mask, "Availability_kbd"] *= 1 + (adj.get("availability", 1.0) - 1) * severity_factor
        df.loc[mask, "Diff_vs_Brent"]    += adj.get("diff", 0.0) * severity_factor
    return df

def shocked_prices(scenario_name, severity_factor):
    """Lower product prices for mixed shocks (demand collapse weakens cracks)."""
    cracks = SHOCKS.get(scenario_name, {}).get("product_cracks", {})
    key_map = {"lpg": "lpg", "naphtha": "naphtha", "gasoline": "gasoline",
               "jet": "jet", "diesel": "diesel", "fuel_oil": "fueloil"}
    prices = dict(base_prices)
    for crack_key, price_key in key_map.items():
        if crack_key in cracks:
            prices[price_key] = base_prices[price_key] + cracks[crack_key] * severity_factor
    return prices

def compute_economics(df, prices):
    """Add cost, value, netback and margin columns to a crude table."""
    df = df.copy()
    df["Logistics_Cost"] = df["Freight"] + df["Cargo_Insurance"] + df["Port_Handling"]
    df["FOB_Price"] = BRENT + df["Diff_vs_Brent"]
    df["Delivered_Cost"] = df["FOB_Price"] + df["Logistics_Cost"]
    df["GPW"] = (
        df["LPG_%"]      * prices["lpg"]
        + df["Naphtha_%"]  * prices["naphtha"]
        + df["Gasoline_%"] * prices["gasoline"]
        + df["Jet_%"]      * prices["jet"]
        + df["Diesel_%"]   * prices["diesel"]
        + df["FuelOil_%"]  * prices["fueloil"]
    ) / 100.0
    df["Processing_Cost"] = base_processing + sulphur_penalty * df["Sulphur_%"]
    df["Netback_FOB"] = df["GPW"] - df["Processing_Cost"] - df["Logistics_Cost"]
    df["Refining_Margin"] = df["GPW"] - df["Delivered_Cost"] - df["Processing_Cost"]
    return df

def describe_scenario(scenario_name, severity_factor):
    spec = SHOCKS.get(scenario_name, {})
    if spec.get("type", "none") == "none":
        return "No shock applied - base case economics."
    parts = []
    for region, adj in spec.items():
        if region in ("type", "product_cracks"):
            continue
        bits = []
        fr = 1 + (adj.get("freight", 1.0) - 1) * severity_factor
        ins = 1 + (adj.get("insurance", 1.0) - 1) * severity_factor
        av = 1 + (adj.get("availability", 1.0) - 1) * severity_factor
        dd = adj.get("diff", 0.0) * severity_factor
        if abs(fr - 1) > 1e-9:  bits.append(f"freight x{fr:.2f}")
        if abs(ins - 1) > 1e-9: bits.append(f"insurance x{ins:.2f}")
        if abs(av - 1) > 1e-9:  bits.append(f"availability x{av:.2f}")
        if abs(dd) > 1e-9:      bits.append(f"differential {dd:+.2f}")
        parts.append(f"{region}: " + ", ".join(bits))
    text = "   |   ".join(parts)
    cracks = spec.get("product_cracks", {})
    if cracks:
        crack_bits = [f"{k} {v * severity_factor:+.1f}" for k, v in cracks.items()]
        text += "      ||      product prices ($/bbl): " + ", ".join(crack_bits)
    return text

def optimise_slate(df, capacity, smax):
    """LP: choose crude volumes (kb/d) to maximise total margin, subject to
    throughput capacity, per-crude availability, and a blended sulphur limit."""
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
    margin_map = dict(zip(df["Crude"], df["Refining_Margin"]))
    sulf_map = dict(zip(df["Crude"], df["Sulphur_%"]))
    avail_map = dict(zip(df["Crude"], df["Availability_kbd"]))
    total_margin = sum(margin_map[c] * volumes[c] for c in volumes.index)
    blended_s = (sum(sulf_map[c] * volumes[c] for c in volumes.index) / total) if total > 0 else 0.0
    binding = []
    if total > 0 and abs(total - capacity) < 0.5:
        binding.append("refinery throughput")
    if total > 0 and abs(blended_s - smax) < 1e-3:
        binding.append("blended sulphur limit")
    maxed = [c for c in volumes.index if volumes[c] > avail_map[c] - 0.5 and volumes[c] > 0.5]
    if maxed:
        binding.append("availability of " + ", ".join(maxed))
    binding_text = "; ".join(binding) if binding else "none - the refinery has spare room"
    s_pi = abs(prob.constraints["Sulphur"].pi or 0.0)
    return {"volumes": volumes, "total": total, "total_margin": total_margin,
            "blended_s": blended_s, "binding_text": binding_text,
            "sulphur_binding": (total > 0 and abs(blended_s - smax) < 1e-3),
            "value_per_tenth": s_pi * total * 0.1}

# ----- Run base case and shocked case -----
stype = SHOCKS.get(scenario, {}).get("type", "none")
shock_active = stype != "none"

base = compute_economics(crudes, base_prices)
shocked = compute_economics(apply_shock(crudes, scenario, sev), shocked_prices(scenario, sev))
shocked["Margin_change"] = shocked["Refining_Margin"] - base["Refining_Margin"]
ranked = shocked.sort_values("Refining_Margin", ascending=False).reset_index(drop=True)

base_slate = optimise_slate(base, throughput_capacity, sulphur_max)
slate = optimise_slate(shocked, throughput_capacity, sulphur_max)

# ===========================================================================
# DISPLAY
# ===========================================================================
if stype == "disruption" or stype == "mixed":
    st.warning(f"{TYPE_LABEL[stype]}  -  {scenario}  ({severity})")
elif stype == "relief":
    st.info(f"{TYPE_LABEL[stype]}  -  {scenario}  ({severity})")
else:
    st.success("Base case - no shock applied")

if shock_active:
    st.caption("Effects ->  " + describe_scenario(scenario, sev))

st.caption(
    "The shock module includes both disruption scenarios and relief / oversupply scenarios. "
    "Disruption shocks increase logistics costs, reduce availability and widen crude differentials. "
    "Relief shocks reduce risk premiums and can make crude cheaper. Mixed shocks, such as a "
    "COVID-style demand collapse, can reduce crude costs but also weaken product cracks, so the net "
    "impact on refining margin may be negative or positive depending on assumptions."
)

top, worst = ranked.iloc[0], ranked.iloc[-1]
c1, c2, c3 = st.columns(3)
c1.metric("Most profitable", top["Crude"],   f"{top['Refining_Margin']:.2f} $/bbl")
c2.metric("Least profitable", worst["Crude"], f"{worst['Refining_Margin']:.2f} $/bbl")
c3.metric("Brent benchmark", f"${BRENT:.2f}")

st.subheader("Refining margin by crude ($/bbl)")
st.bar_chart(ranked.set_index("Crude")["Refining_Margin"])

# --- Optimiser ---
st.subheader("Optimal crude slate (linear program)")
o1, o2, o3 = st.columns(3)
o1.metric("Total run", f"{slate['total']:.0f} kb/d")
delta_margin = slate["total_margin"] - base_slate["total_margin"]
o2.metric("Total margin", f"${slate['total_margin']:,.0f}k/day",
          delta=(f"{delta_margin:,.0f}k/day vs base" if shock_active else None))
o3.metric("Blended sulphur", f"{slate['blended_s']:.2f}%")
st.write(f"**Binding constraint(s):** {slate['binding_text']}")
if slate["sulphur_binding"]:
    st.caption(f"Sulphur limit is binding - relaxing it by +0.1%S is worth about "
               f"${slate['value_per_tenth']:,.0f}k/day. Loosen the cap to run more sour crude.")
chosen = slate["volumes"][slate["volumes"] > 0]
if len(chosen) > 0:
    st.bar_chart(chosen)
else:
    st.warning("At these assumptions no crude is profitable to run - the refinery stays idle.")

# --- Scenario impact (base vs shocked) ---
if shock_active:
    st.subheader("Scenario impact: base case vs shocked")
    impact = pd.DataFrame({
        "Crude": base["Crude"].values,
        "Delivered_base": base["Delivered_Cost"].round(2).values,
        "Delivered_shock": shocked["Delivered_Cost"].round(2).values,
        "GPW_base": base["GPW"].round(2).values,
        "GPW_shock": shocked["GPW"].round(2).values,
        "Margin_base": base["Refining_Margin"].round(2).values,
        "Margin_shock": shocked["Refining_Margin"].round(2).values,
        "Rank_base": base["Refining_Margin"].rank(ascending=False).astype(int).values,
        "Rank_shock": shocked["Refining_Margin"].rank(ascending=False).astype(int).values,
    }).sort_values("Margin_shock", ascending=False)
    st.dataframe(impact, use_container_width=True, hide_index=True)
    if stype == "mixed":
        st.info(
            "Mixed shock: crude is cheaper (delivered cost falls) BUT product cracks fall too, "
            "so gross product worth drops. Compare the optimiser's total margin with the base "
            "case above - cheaper crude does not rescue the margin when product demand collapses."
        )
    elif stype == "relief":
        st.info("Relief shock: lower freight, insurance and differentials cut delivered crude "
                "cost while product worth is unchanged, so margins improve.")
    else:
        st.info("Disruption shock: higher freight, insurance and differentials raise delivered "
                "crude cost, so margins fall - hardest on the exposed region's grades.")

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