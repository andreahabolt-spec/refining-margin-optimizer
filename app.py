# app.py
# ROTTERDAM CRUDE PROCUREMENT & PRODUCT SLATE OPTIMIZER
#
# A crude procurement & refining-margin decision tool for a North-West Europe
# refinery. For each crude grade it computes:
#   delivered cost -> product yields -> gross product worth -> refining margin,
# ranks the grades by margin, recommends the best, and lets the user pick a
# crude to compare against the recommendation (opportunity cost). Manual,
# stackable market shocks can be applied to individual crude grades.
#
# This is NOT an inventory tool: all products are valued at market prices.

import streamlit as st
import pandas as pd
import altair as alt

st.set_page_config(page_title="Rotterdam Crude Procurement & Product Slate Optimizer",
                   layout="wide")
st.title("Rotterdam Crude Procurement & Product Slate Optimizer")

# ---- "Start here" purpose + how-to-use box -------------------------------
st.info(
    "**What this tool does:** it helps a Rotterdam (North-West Europe) refinery decide "
    "**which crude grade(s) to buy** to maximise refining margin under today's prices, freight, "
    "insurance and supply risks.\n\n"
    "**How to use it:**\n\n"
    "1. Set your market view in the sidebar (Brent, refined product prices, volume).\n"
    "2. Read the **Executive summary** for the recommended grade.\n"
    "3. Check the **Financial results / margin breakdown** (Section 7).\n"
    "4. Stress-test it with **market shocks** (Section 2).\n"
    "5. If you want to challenge the model recommendation, select **Manual crude selection** in "
    "the sidebar to compare the recommended crude with your own selected crude (Section 5).\n"
    "6. Build the optimal multi-crude blend in **Crude slate optimisation** (Section 8).\n"
    "7. Use the **Crude quality map** (Section 9) to visually understand crude quality, sulphur "
    "level and margin.\n"
    "8. Use **Detailed data & assumptions** (Section 10) to check the assumptions, inputs and "
    "calculations behind the results.")
st.caption("Scope: all refined products are valued at market prices to estimate Gross Product "
           "Worth. Inventory management and stock roll-forward are outside the scope of this tool.")

with st.expander("New to the terms? 60-second glossary"):
    st.markdown(
        "- **Delivered cost** - all-in cost of one barrel landed at the refinery: crude price "
        "(Brent + differential) + freight + cargo insurance + port/handling.\n"
        "- **Gross Product Worth (GPW)** - the market value of everything one barrel yields "
        "(each product's yield % x its selling price).\n"
        "- **Refining margin** - GPW - delivered crude cost - processing cost. The profit per "
        "barrel; this is what the model ranks crudes on.\n"
        "- **Break-even FOB (netback)** - the highest crude price you could pay and still break "
        "even. The wider the gap to the actual price, the more margin.\n"
        "- **Crude slate** - the mix of several crudes a refinery actually buys and blends.\n"
        "- **Sweet/sour, light/heavy** - low-sulphur 'sweet' and high-API 'light' crudes are "
        "easier and cheaper to refine; 'sour' / 'heavy' grades cost more to process.")

# ---------------------------------------------------------------------------
# Products
# ---------------------------------------------------------------------------
PROD_KEYS = ["Diesel", "Jet", "Gasoline", "Naphtha", "FuelOil", "LPG"]
PROD_LABEL = {"Diesel": "Diesel / Gasoil", "Jet": "Jet / Kerosene", "Gasoline": "Gasoline",
              "Naphtha": "Naphtha", "FuelOil": "Fuel Oil / Residue", "LPG": "LPG"}
YIELD_COL = {k: k + "_%" for k in PROD_KEYS}

# ---------------------------------------------------------------------------
# Crude basket. Region is for interpretation only; shocks target crude NAMES.
# Yields (% of barrel) sum to 100. Processing cost ($/bbl) captures refining
# difficulty (light sweet = low, heavy/sour = high).
# ---------------------------------------------------------------------------
crude_data = [
    {"Crude": "Ekofisk",        "Region": "North Sea",   "Quality": "Light sweet", "API": 37.5, "Sulphur_%": 0.25, "Diff_vs_Brent": 1.50,  "Freight": 0.60, "Cargo_Insurance": 0.05, "Port_Handling": 0.30, "Processing_cost": 2.5, "Note": "North Sea light sweet - nearby European barrel"},
    {"Crude": "Forties",        "Region": "North Sea",   "Quality": "Light sour",  "API": 40.0, "Sulphur_%": 0.60, "Diff_vs_Brent": 0.30,  "Freight": 0.55, "Cargo_Insurance": 0.05, "Port_Handling": 0.30, "Processing_cost": 2.8, "Note": "North Sea, part of Dated Brent"},
    {"Crude": "Johan Sverdrup", "Region": "North Sea",   "Quality": "Medium sour", "API": 28.0, "Sulphur_%": 0.80, "Diff_vs_Brent": -2.00, "Freight": 0.60, "Cargo_Insurance": 0.05, "Port_Handling": 0.30, "Processing_cost": 3.3, "Note": "Norwegian medium sour - sweet/sour trade-off"},
    {"Crude": "WTI Midland",    "Region": "US Gulf",     "Quality": "Light sweet", "API": 42.0, "Sulphur_%": 0.20, "Diff_vs_Brent": 0.80,  "Freight": 2.50, "Cargo_Insurance": 0.08, "Port_Handling": 0.35, "Processing_cost": 2.5, "Note": "US light sweet - transatlantic arbitrage"},
    {"Crude": "CPC Blend",      "Region": "Caspian",     "Quality": "Light sour",  "API": 45.0, "Sulphur_%": 0.55, "Diff_vs_Brent": -1.50, "Freight": 2.40, "Cargo_Insurance": 0.15, "Port_Handling": 0.40, "Processing_cost": 3.0, "Note": "Caspian via Black Sea - geopolitical sensitivity"},
    {"Crude": "Azeri Light",    "Region": "Caspian",     "Quality": "Light sweet", "API": 36.6, "Sulphur_%": 0.15, "Diff_vs_Brent": 1.20,  "Freight": 2.20, "Cargo_Insurance": 0.12, "Port_Handling": 0.35, "Processing_cost": 2.6, "Note": "Caspian light sweet via Ceyhan"},
    {"Crude": "Arab Light",     "Region": "Middle East", "Quality": "Medium sour", "API": 33.0, "Sulphur_%": 1.80, "Diff_vs_Brent": -3.50, "Freight": 3.20, "Cargo_Insurance": 0.18, "Port_Handling": 0.40, "Processing_cost": 4.0, "Note": "Middle East medium sour - Hormuz risk"},
    {"Crude": "Basrah Medium",  "Region": "Middle East", "Quality": "Medium sour", "API": 30.0, "Sulphur_%": 2.70, "Diff_vs_Brent": -4.50, "Freight": 3.40, "Cargo_Insurance": 0.22, "Port_Handling": 0.40, "Processing_cost": 5.0, "Note": "Iraqi medium sour - sour economics, geo risk"},
    {"Crude": "Urals",          "Region": "Russia",      "Quality": "Medium sour", "API": 31.0, "Sulphur_%": 1.50, "Diff_vs_Brent": -7.00, "Freight": 2.80, "Cargo_Insurance": 0.30, "Port_Handling": 0.40, "Processing_cost": 3.8, "Note": "Russian - SANCTIONS RISK / restricted supply; test replacement barrels"},
    {"Crude": "Bonny Light",    "Region": "West Africa", "Quality": "Light sweet", "API": 35.3, "Sulphur_%": 0.15, "Diff_vs_Brent": 1.00,  "Freight": 1.80, "Cargo_Insurance": 0.10, "Port_Handling": 0.35, "Processing_cost": 2.5, "Note": "Nigerian light sweet - West African replacement barrel"},
    {"Crude": "Qua Iboe",       "Region": "West Africa", "Quality": "Light sweet", "API": 36.0, "Sulphur_%": 0.12, "Diff_vs_Brent": 1.10,  "Freight": 1.85, "Cargo_Insurance": 0.10, "Port_Handling": 0.35, "Processing_cost": 2.5, "Note": "Nigerian light sweet - extra West African optionality"},
    {"Crude": "Dalia",          "Region": "West Africa", "Quality": "Medium sweet","API": 23.5, "Sulphur_%": 0.55, "Diff_vs_Brent": -1.50, "Freight": 2.10, "Cargo_Insurance": 0.12, "Port_Handling": 0.38, "Processing_cost": 3.5, "Note": "Angolan, heavier - West African supply not homogeneous"},
    {"Crude": "Oman",           "Region": "Middle East", "Quality": "Medium sour", "API": 33.5, "Sulphur_%": 1.20, "Diff_vs_Brent": -1.00, "Freight": 3.30, "Cargo_Insurance": 0.18, "Port_Handling": 0.40, "Processing_cost": 3.8, "Note": "Dubai-Oman linked - Middle East / Asian flow"},
    {"Crude": "Cold Lake Blend", "Region": "Canada",     "Quality": "Heavy sour",  "API": 21.0, "Sulphur_%": 3.70, "Diff_vs_Brent": -13.00,"Freight": 2.60, "Cargo_Insurance": 0.10, "Port_Handling": 0.40, "Processing_cost": 6.5, "Note": "Canadian heavy sour crude used to test heavy crude economics, high sulphur, lower light-product yield and higher processing cost"},
]
crudes = pd.DataFrame(crude_data)
yield_data = [
    {"Crude": "Ekofisk",        "Diesel_%": 33, "Jet_%": 12, "Gasoline_%": 22, "Naphtha_%": 12, "FuelOil_%": 18, "LPG_%": 3},
    {"Crude": "Forties",        "Diesel_%": 32, "Jet_%": 11, "Gasoline_%": 21, "Naphtha_%": 11, "FuelOil_%": 22, "LPG_%": 3},
    {"Crude": "Johan Sverdrup", "Diesel_%": 32, "Jet_%": 10, "Gasoline_%": 13, "Naphtha_%": 8,  "FuelOil_%": 35, "LPG_%": 2},
    {"Crude": "WTI Midland",    "Diesel_%": 31, "Jet_%": 11, "Gasoline_%": 26, "Naphtha_%": 14, "FuelOil_%": 14, "LPG_%": 4},
    {"Crude": "CPC Blend",      "Diesel_%": 28, "Jet_%": 10, "Gasoline_%": 24, "Naphtha_%": 16, "FuelOil_%": 18, "LPG_%": 4},
    {"Crude": "Azeri Light",    "Diesel_%": 36, "Jet_%": 13, "Gasoline_%": 20, "Naphtha_%": 11, "FuelOil_%": 17, "LPG_%": 3},
    {"Crude": "Arab Light",     "Diesel_%": 30, "Jet_%": 11, "Gasoline_%": 15, "Naphtha_%": 9,  "FuelOil_%": 33, "LPG_%": 2},
    {"Crude": "Basrah Medium",  "Diesel_%": 29, "Jet_%": 9,  "Gasoline_%": 12, "Naphtha_%": 8,  "FuelOil_%": 40, "LPG_%": 2},
    {"Crude": "Urals",          "Diesel_%": 30, "Jet_%": 10, "Gasoline_%": 18, "Naphtha_%": 9,  "FuelOil_%": 31, "LPG_%": 2},
    {"Crude": "Bonny Light",    "Diesel_%": 34, "Jet_%": 13, "Gasoline_%": 22, "Naphtha_%": 12, "FuelOil_%": 16, "LPG_%": 3},
    {"Crude": "Qua Iboe",       "Diesel_%": 34, "Jet_%": 13, "Gasoline_%": 23, "Naphtha_%": 12, "FuelOil_%": 15, "LPG_%": 3},
    {"Crude": "Dalia",          "Diesel_%": 31, "Jet_%": 11, "Gasoline_%": 14, "Naphtha_%": 9,  "FuelOil_%": 33, "LPG_%": 2},
    {"Crude": "Oman",           "Diesel_%": 31, "Jet_%": 11, "Gasoline_%": 17, "Naphtha_%": 10, "FuelOil_%": 29, "LPG_%": 2},
    {"Crude": "Cold Lake Blend", "Diesel_%": 22, "Jet_%": 7,  "Gasoline_%": 9,  "Naphtha_%": 6,  "FuelOil_%": 55, "LPG_%": 1},
]
crudes = crudes.merge(pd.DataFrame(yield_data), on="Crude")   # master basket (all grades)
RESTRICTED_CRUDES = ["Urals"]   # sanctions-risk; hidden entirely unless the user enables them

if "shocks" not in st.session_state:
    st.session_state.shocks = []   # list of {target, brent, freight, insurance, diff}

# ===========================================================================
# SIDEBAR - market assumptions + crude selection mode
# ===========================================================================
st.sidebar.header("Controls")
st.sidebar.caption("Set your market view here. Everything on the main page updates automatically.")

with st.sidebar.expander("1. Market assumptions", expanded=True):
    BRENT = st.slider("Brent benchmark ($/bbl)", 40.0, 120.0, 82.0, 0.5,
                      help="Global benchmark crude price. Each grade is priced as Brent plus its "
                           "own quality / location differential.")
    st.caption("Refined product selling prices ($/bbl) - user-defined market assumptions.")
    price_diesel   = st.slider("Diesel / Gasoil",     50.0, 180.0, 105.0, 1.0,
                               help="Assumed market selling price for this refined product.")
    price_jet      = st.slider("Jet / Kerosene",      50.0, 180.0, 102.0, 1.0,
                               help="Assumed market selling price for this refined product.")
    price_gasoline = st.slider("Gasoline",            50.0, 180.0, 92.0,  1.0,
                               help="Assumed market selling price for this refined product.")
    price_naphtha  = st.slider("Naphtha",             30.0, 150.0, 85.0,  1.0,
                               help="Assumed market selling price for this refined product.")
    price_fueloil  = st.slider("Fuel Oil / Residue",  20.0, 130.0, 70.0,  1.0,
                               help="Assumed market selling price for this refined product.")
    price_lpg      = st.slider("LPG",                 20.0, 130.0, 65.0,  1.0,
                               help="Assumed market selling price for this refined product.")
    volume_bbl = st.number_input("Volume to process (bbl)", min_value=0, value=100000, step=10000,
                                 help="Barrels of the single selected grade used in the Product "
                                      "slate (Section 6) and Financial results (Section 7).")

PRICES = {"Diesel": price_diesel, "Jet": price_jet, "Gasoline": price_gasoline,
          "Naphtha": price_naphtha, "FuelOil": price_fueloil, "LPG": price_lpg}

st.sidebar.subheader("3. Crude selection mode")
mode = st.sidebar.radio("Mode", ["Model recommendation", "Manual crude selection"],
                        help="Model recommendation shows the best grade automatically. Manual lets "
                             "you pick a grade and see what choosing it would cost vs the best.")
include_restricted = st.sidebar.checkbox(
    "Include restricted / sanctions-risk crudes in recommendation", value=False,
    help="Off by default: sanctioned grades (Urals) are hidden everywhere. Turn on to include them.")
st.sidebar.caption("Urals is hidden by default because it is treated as a restricted / "
                   "sanctions-risk crude. Enable restricted crudes to include it in rankings, "
                   "tables and optimization.")

# Active crude universe: when the box is unchecked, restricted grades (Urals) are dropped here,
# so they are invisible in every table, chart, ranking and the optimizer downstream.
if include_restricted:
    active_crudes = crudes.copy()
else:
    active_crudes = crudes[~crudes["Crude"].isin(RESTRICTED_CRUDES)].reset_index(drop=True)
CRUDE_NAMES = list(active_crudes["Crude"])

selected_crude = None
if mode == "Manual crude selection":
    selected_crude = st.sidebar.selectbox("Select a crude to test", CRUDE_NAMES,
                                          help="The grade whose economics you want to compare "
                                               "against the model's recommended grade.")

# ===========================================================================
# CORE: delivered cost + margin per crude, with stacked shocks applied
# ===========================================================================
def compute_table(df, shocks, prices, brent):
    """Apply all active shocks (additive per crude), then compute delivered cost,
    gross product worth, refining margin, and rank by margin."""
    df = df.copy()
    sb, sf, si, sd = [], [], [], []
    for crude in df["Crude"]:
        b = f = i = d = 0.0
        for s in shocks:                      # combine: "All crudes" + the crude's own shocks
            if s["target"] == "All crudes" or s["target"] == crude:
                b += s["brent"]; f += s["freight"]; i += s["insurance"]; d += s["diff"]
        sb.append(b); sf.append(f); si.append(i); sd.append(d)
    df["Shock_Brent"], df["Shock_Freight%"], df["Shock_Ins%"], df["Shock_Diff"] = sb, sf, si, sd
    # Dollar shocks add; percentage shocks scale the base value.
    df["FOB_Price"] = (brent + df["Shock_Brent"]) + (df["Diff_vs_Brent"] + df["Shock_Diff"])
    df["Freight_adj"] = df["Freight"] * (1 + df["Shock_Freight%"] / 100)
    df["Insurance_adj"] = df["Cargo_Insurance"] * (1 + df["Shock_Ins%"] / 100)
    df["Delivered_Cost"] = df["FOB_Price"] + df["Freight_adj"] + df["Insurance_adj"] + df["Port_Handling"]
    df["GPW"] = sum(df[YIELD_COL[k]] / 100 * prices[k] for k in PROD_KEYS)
    df["Refining_Margin"] = df["GPW"] - df["Delivered_Cost"] - df["Processing_cost"]
    # Netback / break-even FOB: the highest FOB crude price you could pay and still break even
    # (margin = 0) = product worth minus processing, freight, insurance and port costs.
    df["Breakeven_FOB"] = (df["GPW"] - df["Processing_cost"]
                           - df["Freight_adj"] - df["Insurance_adj"] - df["Port_Handling"])
    df = df.sort_values("Refining_Margin", ascending=False).reset_index(drop=True)
    df["Rank"] = df.index + 1
    return df

ranked = compute_table(active_crudes, st.session_state.shocks, PRICES, BRENT)
# active_crudes is already filtered, so the whole app (ranking, charts, tables, optimizer,
# recommendation) sees the same crude set - restricted grades are either all in or all out.
recommended = ranked.iloc[0]
rec_crude = recommended["Crude"]
if selected_crude is None:
    selected_crude = rec_crude            # model mode focuses on the recommended crude
sel = ranked[ranked["Crude"] == selected_crude].iloc[0]
opportunity_cost = sel["Refining_Margin"] - recommended["Refining_Margin"]   # <= 0

# ===========================================================================
# 2. MANUAL MARKET SHOCK BUILDER
# ===========================================================================
st.header("2. Manual market shock builder")
st.caption("This section helps you test the model under changing market conditions. ")
st.caption("You can simulate different shocks, such as a Brent price move, higher freight costs, higher cargo insurance, or a change in the crude differential. ")
st.caption("After clicking **Apply shock**, the model updates the crude ranking and the recommended crude. You can apply several shocks one after another to build a full market scenario. ")

# Seed the four adjustment sliders once so they can be reset to zero after each Apply.
for _k, _v in [("shock_brent", 0.0), ("shock_freight", 0), ("shock_ins", 0), ("shock_diff", 0.0)]:
    if _k not in st.session_state:
        st.session_state[_k] = _v

def apply_shock():
    """Append the current shock, then reset the four adjustment sliders to zero.
    Runs as a button callback (before the widgets are re-created), so resetting the
    widget values via session_state is allowed - this prevents the previous shock
    values from being carried over and re-applied to the next crude."""
    st.session_state.shocks.append({
        "target": st.session_state.shock_target,
        "brent": st.session_state.shock_brent,
        "freight": st.session_state.shock_freight,
        "insurance": st.session_state.shock_ins,
        "diff": st.session_state.shock_diff,
    })
    st.session_state.shock_brent = 0.0
    st.session_state.shock_freight = 0
    st.session_state.shock_ins = 0
    st.session_state.shock_diff = 0.0

st.selectbox("Apply shock to", ["All crudes"] + CRUDE_NAMES, key="shock_target",
             help="Apply the shock to every grade ('All crudes') or to one grade only.")
sc = st.columns(4)
sc[0].slider("Brent adjustment ($/bbl)", -30.0, 30.0, step=0.5, key="shock_brent",
             help="Move the Brent benchmark up or down (a market-wide price move).")
sc[1].slider("Freight adjustment (%)", -100, 300, step=5, key="shock_freight",
             help="Raise or lower freight cost, e.g. a shipping disruption.")
sc[2].slider("Cargo insurance adjustment (%)", -100, 500, step=10, key="shock_ins",
             help="Raise or lower cargo insurance, e.g. a war-risk premium.")
sc[3].slider("Crude differential adjustment ($/bbl)", -20.0, 20.0, step=0.5, key="shock_diff",
             help="Move the crude's differential to Brent, e.g. a discount on a sanctioned barrel.")
st.button("Apply shock", on_click=apply_shock)

st.caption("Active shock adjustments")
if st.session_state.shocks:
    shocks_df = pd.DataFrame(st.session_state.shocks).rename(
        columns={"target": "Target crude", "brent": "Brent adj $", "freight": "Freight adj %",
                 "insurance": "Insurance adj %", "diff": "Differential adj $"})
    st.dataframe(shocks_df, use_container_width=True, hide_index=True)
    rc = st.columns(2)
    options = [f"{i + 1}. {s['target']}" for i, s in enumerate(st.session_state.shocks)]
    to_remove = rc[0].selectbox("Remove which shock?", options)
    if rc[0].button("Remove selected shock"):
        st.session_state.shocks.pop(int(to_remove.split(".")[0]) - 1)
        st.rerun()
    if rc[1].button("Reset all shocks"):
        st.session_state.shocks = []
        st.rerun()
else:
    st.info("No active shocks. Pick a target, move the sliders, and click 'Apply shock'.")

# ===========================================================================
# 4. EXECUTIVE SUMMARY
# ===========================================================================
st.header("4. Executive summary")
st.caption("Your decision summary: which crude the model recommends buying now, the margin it generates per barrel "
           "and the opportunity cost of choosing the crude you manually selected. Hover over each metric for a quick explanation.")

k = st.columns(4)
k[0].metric("Recommended crude", rec_crude, f"{recommended['Refining_Margin']:.2f} $/bbl",
            help="The available grade with the highest refining margin per barrel.")
k[1].metric("Selected crude", selected_crude, f"{sel['Refining_Margin']:.2f} $/bbl",
            help="The grade you chose in the sidebar (defaults to the recommended one).")
k[2].metric("Opportunity cost", f"{opportunity_cost:.2f} $/bbl",
            help="Margin per barrel given up by buying the selected grade instead of the "
                 "recommended one (0 if they are the same).")
k[3].metric("Brent benchmark", f"${BRENT:.2f}", help="Your current Brent assumption from the sidebar.")
k2 = st.columns(4)
k2[0].metric("Selected delivered cost", f"${sel['Delivered_Cost']:.2f}/bbl",
             help="All-in landed cost of one barrel: FOB (Brent + differential) + freight + "
                  "insurance + port/handling.")
k2[1].metric("Selected GPW", f"${sel['GPW']:.2f}/bbl",
             help="Gross Product Worth: market value of all products from one barrel.")
k2[2].metric("Selected processing", f"${sel['Processing_cost']:.2f}/bbl",
             help="Estimated cost to refine one barrel of this grade.")
k2[3].metric("Selected rank", f"#{int(sel['Rank'])} of {len(ranked)}",
             help="Where the selected grade ranks among the available grades by refining margin.")
if mode == "Manual crude selection" and selected_crude != rec_crude:
    st.warning(f"{selected_crude} ranks #{int(sel['Rank'])} with {sel['Refining_Margin']:.2f} $/bbl. "
               f"The model recommends {rec_crude} at {recommended['Refining_Margin']:.2f} $/bbl - "
               f"an opportunity cost of {opportunity_cost:.2f} $/bbl by not buying the best grade.")
else:
    st.success(f"In plain terms: buy {rec_crude} - it earns the highest refining margin at "
               f"{recommended['Refining_Margin']:.2f} $/bbl after all delivered and processing costs.")

# ===========================================================================
# 5. RECOMMENDED VS SELECTED CRUDE
# ===========================================================================
st.header("5. Recommended vs selected crude")
st.caption("This section compares the model recommendation with the crude you selected. "
           "The chart gives a quick visual ranking of all crudes by refining margin ($/bbl)."
           "The table below provides the detailed breakdown behind the ranking: delivered cost, GPW, break-even FOB, processing cost and margin.")
compare = pd.DataFrame({
    "Metric": ["Region", "Quality", "Delivered cost $/bbl", "Gross product worth $/bbl",
               "Processing cost $/bbl", "Refining margin $/bbl", "Rank"],
    "Selected (" + selected_crude + ")": [
        sel["Region"], sel["Quality"], round(sel["Delivered_Cost"], 2), round(sel["GPW"], 2),
        round(sel["Processing_cost"], 2), round(sel["Refining_Margin"], 2), int(sel["Rank"])],
    "Recommended (" + rec_crude + ")": [
        recommended["Region"], recommended["Quality"], round(recommended["Delivered_Cost"], 2),
        round(recommended["GPW"], 2), round(recommended["Processing_cost"], 2),
        round(recommended["Refining_Margin"], 2), int(recommended["Rank"])],
})
st.dataframe(compare, use_container_width=True, hide_index=True)
st.write(f"**Difference in margin:** {sel['Refining_Margin'] - recommended['Refining_Margin']:.2f} $/bbl   "
         f"|   **Opportunity cost of the selected crude:** {opportunity_cost:.2f} $/bbl")

st.subheader("Full crude ranking ($/bbl)")
st.bar_chart(ranked.set_index("Crude")["Refining_Margin"])
st.caption("How to read it ? A higher ranking means the crude is more profitable under today's "
           "prices and costs. The table below adds the delivered cost, GPW and break-even FOB.")
st.dataframe(
    ranked[["Rank", "Crude", "Region", "Quality", "API", "Sulphur_%", "Delivered_Cost",
            "GPW", "Breakeven_FOB", "Processing_cost", "Refining_Margin"]]
    .rename(columns={"Sulphur_%": "Sulphur", "Delivered_Cost": "Delivered $/bbl",
                     "GPW": "GPW $/bbl", "Breakeven_FOB": "Break-even FOB $/bbl",
                     "Processing_cost": "Processing $/bbl",
                     "Refining_Margin": "Margin $/bbl"}).round(2),
    use_container_width=True, hide_index=True)

# ===========================================================================
# 6. PRODUCT SLATE OUTPUT (for the selected / recommended crude)
# ===========================================================================
st.header("6. Product slate output")
st.caption("What one chosen crude turns into ? the barrels of each refined product and the value "
           "each contributes. This is where the Gross Product Worth comes from.")
st.caption(f"From {volume_bbl:,.0f} bbl of {selected_crude}, estimated product output:")
output_bbl = {k: sel[YIELD_COL[k]] / 100 * volume_bbl for k in PROD_KEYS}
slate = pd.DataFrame({
    "Product": [PROD_LABEL[k] for k in PROD_KEYS],
    "Yield %": [sel[YIELD_COL[k]] for k in PROD_KEYS],
    "Output bbl": [round(output_bbl[k], 0) for k in PROD_KEYS],
    "Price $/bbl": [PRICES[k] for k in PROD_KEYS],
    "Product value $": [round(output_bbl[k] * PRICES[k], 0) for k in PROD_KEYS],
})
c_slate = st.columns([2, 1])
c_slate[0].dataframe(slate, use_container_width=True, hide_index=True)
c_slate[1].bar_chart(slate.set_index("Product")["Product value $"])

# ===========================================================================
# 7. FINANCIAL RESULTS / MARGIN BREAKDOWN
# ===========================================================================
st.header("7. Financial results / margin breakdown")
st.caption("The margin maths for the chosen crude, from product worth down to the total gross "
           "margin on your volume. Refining margin = GPW - delivered crude cost - processing cost.")
gross_margin_total = sel["Refining_Margin"] * volume_bbl
fin = pd.DataFrame({
    "Item": ["Gross product worth", "Delivered crude cost", "Processing cost",
             "Refining margin", "Volume processed", "Estimated gross margin"],
    "Value": [f"${sel['GPW']:.2f}/bbl", f"-${sel['Delivered_Cost']:.2f}/bbl",
              f"-${sel['Processing_cost']:.2f}/bbl", f"${sel['Refining_Margin']:.2f}/bbl",
              f"{volume_bbl:,.0f} bbl", f"${gross_margin_total:,.0f}"],
})
st.dataframe(fin, use_container_width=True, hide_index=True)
st.write(f"**Interpretation:** {selected_crude} generates a refining margin of "
         f"{sel['Refining_Margin']:.2f} $/bbl, equal to an estimated gross margin of "
         f"${gross_margin_total:,.0f} on {volume_bbl:,.0f} barrels processed.")

# ===========================================================================
# 8. CRUDE SLATE OPTIMISATION (LINEAR PROGRAM)
# ===========================================================================
st.header("8. Crude slate optimisation (linear program)")
st.caption("""
This section turns the crude ranking into a practical procurement decision.

The ranking above shows the best crude on a **stand-alone basis**. But in reality, a refinery does not usually buy only one crude. It builds a **crude slate**, meaning a mix of several grades.

The optimiser answers the key decision question:

**Which combination of crudes should the refinery buy to maximise total margin?**

The model selects the number of barrels for each crude while respecting three constraints:

- total refinery throughput;
- available volume for each crude;
- maximum average sulphur allowed in the slate.

Margins already include any active market shocks. Restricted crudes are automatically excluded based on the sidebar setting.
""")
lp_pool = ranked.reset_index(drop=True)   # ranked already reflects the restricted-crude filter

lp_c = st.columns(2)
throughput = lp_c[0].number_input("Refinery throughput to fill (bbl)",
                                  min_value=0, value=1_000_000, step=100_000,
                                  help="Total barrels the refinery will run; the slate must fill "
                                       "exactly this.")
max_sulphur = lp_c[1].slider("Maximum average sulphur of the slate (%)",
                             0.1, float(round(lp_pool["Sulphur_%"].max(), 2)), 1.00, 0.05,
                             help="Product-spec limit on the blend's average sulphur. Lower it to "
                                  "force in sweeter (lower-sulphur) grades.")

st.caption("Availability = the most barrels you could realistically source of each crude (editable).")
avail = st.data_editor(
    pd.DataFrame({"Crude": lp_pool["Crude"], "Available bbl": [200_000.0] * len(lp_pool)}),
    use_container_width=True, hide_index=True, disabled=["Crude"],
    column_config={"Available bbl": st.column_config.NumberColumn(
        "Available bbl", min_value=0.0, step=50_000.0)})

if st.button("Optimise crude slate"):
    try:
        import pulp
    except ModuleNotFoundError:
        st.error("This module needs the 'pulp' package. Install it with:  py -m pip install pulp")
    else:
        names = list(lp_pool["Crude"])
        margin = dict(zip(names, lp_pool["Refining_Margin"]))
        sulph = dict(zip(names, lp_pool["Sulphur_%"]))
        cap = dict(zip(avail["Crude"], avail["Available bbl"]))

        prob = pulp.LpProblem("crude_slate", pulp.LpMaximize)
        x = {c: pulp.LpVariable(f"bbl_{i}", lowBound=0) for i, c in enumerate(names)}
        prob += pulp.lpSum(margin[c] * x[c] for c in names)                        # objective
        prob += pulp.lpSum(x[c] for c in names) == throughput, "throughput"        # fill the plant
        for c in names:
            prob += x[c] <= float(cap.get(c, 0.0)), f"avail_{c}"                   # availability
        prob += pulp.lpSum(sulph[c] * x[c] for c in names) <= max_sulphur * throughput, "sulphur"
        prob.solve(pulp.PULP_CBC_CMD(msg=0))

        if pulp.LpStatus[prob.status] != "Optimal":
            st.warning(f"No feasible slate for these limits ({pulp.LpStatus[prob.status]}). "
                       "Raise total availability or the sulphur cap, or lower throughput.")
        else:
            bought = sum(x[c].value() for c in names)
            total_margin = sum(margin[c] * x[c].value() for c in names)
            blended_sulphur = (sum(sulph[c] * x[c].value() for c in names) / bought
                               if bought else 0.0)
            avg_margin = total_margin / bought if bought else 0.0

            alloc = pd.DataFrame({
                "Crude": names,
                "Barrels bought": [round(x[c].value(), 0) for c in names],
                "% of slate": [round(x[c].value() / throughput * 100, 1) if throughput else 0.0
                               for c in names],
                "Margin $/bbl": [round(margin[c], 2) for c in names],
                "Sulphur %": [round(sulph[c], 2) for c in names],
                "Margin contribution $": [round(margin[c] * x[c].value(), 0) for c in names],
            })
            alloc = alloc[alloc["Barrels bought"] > 0].sort_values("Barrels bought", ascending=False)

            st.caption("This is the optimal slate to buy: how many barrels of each grade, the % of "
                       "the blend, and each grade's margin contribution.")
            mcol = st.columns(3)
            mcol[0].metric("Total slate margin", f"${total_margin:,.0f}",
                           help="Total refining margin across the whole purchased slate.")
            mcol[1].metric("Average margin", f"${avg_margin:.2f}/bbl",
                           help="Refining margin per barrel, averaged across the slate.")
            mcol[2].metric("Blended sulphur", f"{blended_sulphur:.2f}% / {max_sulphur:.2f}% cap",
                           help="Volume-weighted average sulphur of the chosen slate vs your cap.")
            st.dataframe(alloc, use_container_width=True, hide_index=True)

            binding = ["throughput (the plant is filled exactly)"]
            if abs(blended_sulphur - max_sulphur) < 1e-3:
                binding.append("maximum average sulphur (product spec)")
            at_cap = [c for c in names
                      if x[c].value() > 1e-6 and abs(x[c].value() - float(cap.get(c, 0.0))) < 1e-3]
            if at_cap:
                binding.append("availability of " + ", ".join(at_cap))
            st.info("**Binding constraints (what limits the margin):** " + "; ".join(binding)
                    + ". Extra margin can only come from relaxing one of these.")
            st.caption("Sweet/sour trade-off: when a sour crude is cheap (e.g. a discounted barrel "
                       "or after a differential shock) it tops the margin ranking, but the sulphur "
                       "cap then forces sweeter, costlier grades into the slate - trading some "
                       "margin for spec compliance. Loosen the cap and the LP leans back on the "
                       "cheaper sour grade.")
else:
    st.caption("Set the limits, edit availability if needed, then click 'Optimise crude slate'.")

# ===========================================================================
# 9. CRUDE QUALITY MAP
# ===========================================================================
st.header("9. Crude quality map")
st.caption("Where each crude sits on quality: light/sweet grades (bottom-right) are easier and "
           "cheaper to refine; heavy/sour grades (top-left) cost more to process. Bigger bubble = "
           "more refining margin.")
st.caption("x = API (higher is lighter), y = sulphur (higher is sourer), colour = region, "
           "bubble size = refining margin.")
qmap = ranked.copy()
qmap["Margin_size"] = qmap["Refining_Margin"].clip(lower=0.1)   # size must be positive
quality_chart = (
    alt.Chart(qmap).mark_circle(opacity=0.75).encode(
        x=alt.X("API:Q", title="API gravity (higher = lighter)", scale=alt.Scale(zero=False)),
        y=alt.Y("Sulphur_%:Q", title="Sulphur (%)", scale=alt.Scale(zero=False)),
        size=alt.Size("Margin_size:Q", title="Refining margin $/bbl"),
        color=alt.Color("Region:N", title="Region"),
        tooltip=[alt.Tooltip("Crude:N"), alt.Tooltip("Region:N"), alt.Tooltip("Quality:N"),
                 alt.Tooltip("API:Q"), alt.Tooltip("Sulphur_%:Q"),
                 alt.Tooltip("Delivered_Cost:Q", title="Delivered $/bbl", format=".2f"),
                 alt.Tooltip("Refining_Margin:Q", title="Margin $/bbl", format=".2f")],
    ).interactive()
)
st.altair_chart(quality_chart, use_container_width=True)

# ===========================================================================
# 10. DETAILED DATA & ASSUMPTIONS
# ===========================================================================
st.header("10. Detailed data & assumptions")
st.caption("This section contains the data and assumptions behind the model results. "
           "Open the expanders if you want to check the details, such as crude characteristics, product yields, prices or shock calculations.")
with st.expander("Crude characteristics & delivered cost build-up"):
    st.dataframe(ranked[["Crude", "Region", "Quality", "API", "Sulphur_%", "Diff_vs_Brent",
                         "FOB_Price", "Freight_adj", "Insurance_adj", "Port_Handling",
                         "Delivered_Cost", "Breakeven_FOB", "Processing_cost", "Note"]].round(2),
                 use_container_width=True, hide_index=True)
with st.expander("Product yield assumptions & gross product worth"):
    st.dataframe(ranked[["Crude", "Quality"] + [YIELD_COL[k] for k in PROD_KEYS]
                        + ["GPW", "Refining_Margin"]].round(2),
                 use_container_width=True, hide_index=True)
with st.expander("Product price assumptions ($/bbl)"):
    st.dataframe(pd.DataFrame({"Product": [PROD_LABEL[k] for k in PROD_KEYS],
                               "Price $/bbl": [PRICES[k] for k in PROD_KEYS]}),
                 use_container_width=True, hide_index=True)
with st.expander("Active shock calculations (total adjustment applied per crude)"):
    st.dataframe(ranked[["Crude", "Shock_Brent", "Shock_Freight%", "Shock_Ins%", "Shock_Diff"]].round(2),
                 use_container_width=True, hide_index=True)