# app.py
# ROTTERDAM CRUDE PROCUREMENT & PRODUCT SLATE OPTIMIZER
#
# Which crude mix should a Rotterdam refinery BUY to satisfy client product
# orders, within crude availability, given delivered crude costs and per-crude
# processing costs - and what is the total profit on the order portfolio?
#
# Logic chain:
#   Client orders -> product demand in barrels -> available crudes ->
#   delivered crude cost + processing cost -> product yields ->
#   optimised crude mix -> product allocation -> surplus -> total profit.
#
# Refined products are valued at DIRECT selling prices ($/bbl), set by the user
# like the Brent benchmark. API gravity and sulphur are shown only as crude
# characteristics; refining difficulty is captured by the per-crude processing
# cost. Manual shocks act on crude / logistics variables only.

import streamlit as st
import pandas as pd
import pulp
import altair as alt

st.set_page_config(page_title="Rotterdam Crude Procurement & Product Slate Optimizer",
                   layout="wide")
st.title("Rotterdam Crude Procurement & Product Slate Optimizer")
st.caption("Which crudes to buy to satisfy client product orders - illustrative decision-support tool")

st.info(
    "This model estimates which crude mix a Rotterdam refinery should purchase to satisfy "
    "client product orders. It combines delivered crude costs, per-crude processing costs, "
    "product yields and crude availability. Refined products are valued at user-defined direct "
    "selling prices ($/bbl). It estimates the crude volumes to buy, products generated, demand "
    "covered, surplus products and total profit from the order portfolio."
)

# ---------------------------------------------------------------------------
# Reference data
# ---------------------------------------------------------------------------
PRODUCTS = ["Diesel / Gasoil", "Jet fuel / Kerosene", "Gasoline", "Naphtha", "Fuel oil", "LPG"]
YIELD_COL = {"Diesel / Gasoil": "Diesel_%", "Jet fuel / Kerosene": "Jet_%",
             "Gasoline": "Gasoline_%", "Naphtha": "Naphtha_%",
             "Fuel oil": "FuelOil_%", "LPG": "LPG_%"}
# Approximate conversion factors (barrels per metric tonne).
BBL_PER_TONNE = {"Diesel / Gasoil": 7.45, "Jet fuel / Kerosene": 7.88, "Gasoline": 8.50,
                 "Naphtha": 8.90, "Fuel oil": 6.35, "LPG": 11.60}

# ---------------------------------------------------------------------------
# SIDEBAR - market assumptions and manual shocks
# ---------------------------------------------------------------------------
st.sidebar.header("Controls")

with st.sidebar.expander("Market assumptions", expanded=True):
    BRENT = st.slider("Brent benchmark ($/bbl)", 40.0, 120.0, 82.0, 0.5)
    st.caption("Refined product selling prices ($/bbl) - user-defined market assumptions, "
               "just like the Brent benchmark above.")
    price_diesel   = st.slider("Diesel / Gasoil selling price",     50.0, 180.0, 105.0, 1.0)
    price_jet      = st.slider("Jet fuel / Kerosene selling price", 50.0, 180.0, 102.0, 1.0)
    price_gasoline = st.slider("Gasoline selling price",            50.0, 180.0, 92.0,  1.0)
    price_naphtha  = st.slider("Naphtha selling price",             30.0, 150.0, 85.0,  1.0)
    price_fueloil  = st.slider("Fuel oil selling price",            20.0, 130.0, 70.0,  1.0)
    price_lpg      = st.slider("LPG selling price",                 20.0, 130.0, 65.0,  1.0)

st.sidebar.subheader("Manual market shock")
st.sidebar.caption("Stress crude / logistics variables. Zero = no shock. "
                   "Example: Middle East insurance +200% mimics a Hormuz shock.")
scope = st.sidebar.selectbox("Apply shock to",
                             ["All crudes", "North Sea", "US Gulf", "Caspian",
                              "Middle East", "West Africa", "Canada", "Single crude"])
crude_choice = None
brent_adj = st.sidebar.slider("Brent adjustment ($/bbl)", -20.0, 50.0, 0.0, 0.5)
freight_pct = st.sidebar.slider("Freight adjustment (%)", -100, 500, 0, 5)
insurance_pct = st.sidebar.slider("Cargo insurance adjustment (%)", -100, 500, 0, 10)
port_pct = st.sidebar.slider("Port / handling adjustment (%)", -100, 200, 0, 5)
diff_adj = st.sidebar.slider("Crude differential adjustment ($/bbl)", -20.0, 20.0, 0.0, 0.5)
avail_pct = st.sidebar.slider("Availability adjustment (%)", -100, 200, 0, 5)

PRICES = {"Diesel / Gasoil": price_diesel, "Jet fuel / Kerosene": price_jet,
          "Gasoline": price_gasoline, "Naphtha": price_naphtha,
          "Fuel oil": price_fueloil, "LPG": price_lpg}

# ---------------------------------------------------------------------------
# Crude slate. API and sulphur are informative only. Refining difficulty is
# captured by Processing_cost ($/bbl): light sweet = low, heavy sour = high.
# Available_bbl and Processing_cost are editable in the app.
# ---------------------------------------------------------------------------
crude_data = [
    {"Crude": "Ekofisk",         "Region": "North Sea",   "Route": "North Sea to NWE",               "Quality": "Light sweet", "API": 37.5, "Sulphur_%": 0.25, "Diff_vs_Brent": 1.50,  "Freight": 0.60, "Cargo_Insurance": 0.05, "Port_Handling": 0.30, "Available_bbl": 30000, "Processing_cost": 2.5},
    {"Crude": "Forties",         "Region": "North Sea",   "Route": "North Sea to NWE",               "Quality": "Light sour",  "API": 40.0, "Sulphur_%": 0.60, "Diff_vs_Brent": 0.30,  "Freight": 0.55, "Cargo_Insurance": 0.05, "Port_Handling": 0.30, "Available_bbl": 40000, "Processing_cost": 2.8},
    {"Crude": "Johan Sverdrup",  "Region": "North Sea",   "Route": "North Sea to NWE",               "Quality": "Medium sour", "API": 28.0, "Sulphur_%": 0.80, "Diff_vs_Brent": -2.00, "Freight": 0.60, "Cargo_Insurance": 0.05, "Port_Handling": 0.30, "Available_bbl": 50000, "Processing_cost": 3.3},
    {"Crude": "WTI Midland",     "Region": "US Gulf",     "Route": "US Gulf to NWE (transatlantic)", "Quality": "Light sweet", "API": 42.0, "Sulphur_%": 0.20, "Diff_vs_Brent": 0.80,  "Freight": 2.50, "Cargo_Insurance": 0.08, "Port_Handling": 0.35, "Available_bbl": 60000, "Processing_cost": 2.5},
    {"Crude": "CPC Blend",       "Region": "Caspian",     "Route": "CPC / Black Sea to NWE",         "Quality": "Light sour",  "API": 45.0, "Sulphur_%": 0.55, "Diff_vs_Brent": -1.50, "Freight": 2.40, "Cargo_Insurance": 0.15, "Port_Handling": 0.40, "Available_bbl": 35000, "Processing_cost": 3.0},
    {"Crude": "Basrah Medium",   "Region": "Middle East", "Route": "Persian Gulf to NWE",            "Quality": "Medium sour", "API": 30.0, "Sulphur_%": 2.70, "Diff_vs_Brent": -4.50, "Freight": 3.40, "Cargo_Insurance": 0.22, "Port_Handling": 0.40, "Available_bbl": 25000, "Processing_cost": 5.0},
    {"Crude": "Bonny Light",     "Region": "West Africa", "Route": "West Africa to NWE",             "Quality": "Light sweet", "API": 35.3, "Sulphur_%": 0.15, "Diff_vs_Brent": 1.00,  "Freight": 1.80, "Cargo_Insurance": 0.10, "Port_Handling": 0.35, "Available_bbl": 20000, "Processing_cost": 2.5},
    {"Crude": "Cold Lake Blend", "Region": "Canada",      "Route": "Canada via US Gulf to NWE",      "Quality": "Heavy sour",  "API": 21.0, "Sulphur_%": 3.70, "Diff_vs_Brent": -13.00,"Freight": 2.60, "Cargo_Insurance": 0.10, "Port_Handling": 0.40, "Available_bbl": 10000, "Processing_cost": 6.5},
]
crudes = pd.DataFrame(crude_data)

# Product yields (% of one barrel; each row sums to 100).
yield_data = [
    {"Crude": "Ekofisk",         "Diesel_%": 33, "Jet_%": 12, "Gasoline_%": 22, "Naphtha_%": 12, "FuelOil_%": 18, "LPG_%": 3},
    {"Crude": "Forties",         "Diesel_%": 32, "Jet_%": 11, "Gasoline_%": 21, "Naphtha_%": 11, "FuelOil_%": 22, "LPG_%": 3},
    {"Crude": "Johan Sverdrup",  "Diesel_%": 32, "Jet_%": 10, "Gasoline_%": 13, "Naphtha_%": 8,  "FuelOil_%": 35, "LPG_%": 2},
    {"Crude": "WTI Midland",     "Diesel_%": 31, "Jet_%": 11, "Gasoline_%": 26, "Naphtha_%": 14, "FuelOil_%": 14, "LPG_%": 4},
    {"Crude": "CPC Blend",       "Diesel_%": 28, "Jet_%": 10, "Gasoline_%": 24, "Naphtha_%": 16, "FuelOil_%": 18, "LPG_%": 4},
    {"Crude": "Basrah Medium",   "Diesel_%": 29, "Jet_%": 9,  "Gasoline_%": 12, "Naphtha_%": 8,  "FuelOil_%": 40, "LPG_%": 2},
    {"Crude": "Bonny Light",     "Diesel_%": 34, "Jet_%": 13, "Gasoline_%": 22, "Naphtha_%": 12, "FuelOil_%": 16, "LPG_%": 3},
    {"Crude": "Cold Lake Blend", "Diesel_%": 22, "Jet_%": 7,  "Gasoline_%": 9,  "Naphtha_%": 6,  "FuelOil_%": 55, "LPG_%": 1},
]
crudes = crudes.merge(pd.DataFrame(yield_data), on="Crude")
crudes["Available_bbl"] = crudes["Available_bbl"].astype(float)
crudes["Processing_cost"] = crudes["Processing_cost"].astype(float)

# ===========================================================================
# SECTION 1 - CLIENT ORDERS  (starts empty; add and delete rows freely)
# ===========================================================================
st.header("1. Client orders")
st.caption("Add client orders below (click + to add a row; tick a row and press Delete to "
           "remove it). Quantity can be in metric tonnes or barrels; tonnes are converted to "
           "barrels automatically.")
empty_orders = pd.DataFrame({"Client": pd.Series([], dtype="object"),
                             "Product": pd.Series([], dtype="object"),
                             "Quantity": pd.Series([], dtype="float64"),
                             "Unit": pd.Series([], dtype="object")})
orders = st.data_editor(
    empty_orders, num_rows="dynamic", use_container_width=True, hide_index=True,
    column_config={
        "Client": st.column_config.TextColumn("Client"),
        "Product": st.column_config.SelectboxColumn("Product", options=PRODUCTS),
        "Quantity": st.column_config.NumberColumn("Quantity", min_value=0.0, step=10.0),
        "Unit": st.column_config.SelectboxColumn("Unit", options=["Metric tonnes", "Barrels"]),
    },
)

# Convert active orders to barrels and aggregate demand by product.
demand_bbl = {p: 0.0 for p in PRODUCTS}
for _, row in orders.iterrows():
    prod, qty, unit = row.get("Product"), row.get("Quantity"), row.get("Unit")
    if pd.isna(prod) or pd.isna(qty) or prod not in PRODUCTS or float(qty) <= 0:
        continue
    qty = float(qty)
    demand_bbl[prod] += qty if unit == "Barrels" else qty * BBL_PER_TONNE[prod]

# ===========================================================================
# SECTION 2 - CRUDE AVAILABILITY & PROCESSING COST  (editable per crude)
# ===========================================================================
st.header("2. Crude availability & processing cost")
st.caption("Maximum barrels available per crude (0 to exclude it), and the per-barrel "
           "processing cost. Light sweet crudes refine cheaply; heavy sour crudes cost more.")
crude_inputs = crudes[["Crude", "Available_bbl", "Processing_cost"]].copy()
edited = st.data_editor(
    crude_inputs, num_rows="fixed", use_container_width=True, hide_index=True,
    column_config={
        "Crude": st.column_config.TextColumn("Crude", disabled=True),
        "Available_bbl": st.column_config.NumberColumn("Available (bbl)", min_value=0.0, step=1000.0),
        "Processing_cost": st.column_config.NumberColumn("Processing $/bbl", min_value=0.0, step=0.1),
    },
)
crudes["Available_bbl"] = crudes["Crude"].map(dict(zip(edited["Crude"], edited["Available_bbl"]))).fillna(0.0).astype(float)
crudes["Processing_cost"] = crudes["Crude"].map(dict(zip(edited["Crude"], edited["Processing_cost"]))).fillna(0.0).astype(float)

# ----- Gate: do not run the optimiser without at least one client order -----
if sum(demand_bbl.values()) <= 0:
    st.warning("Please enter at least one client order to run the crude procurement optimizer.")
    st.stop()

# ===========================================================================
# ECONOMICS (delivered cost + processing cost) + manual shock
# ===========================================================================
def scope_mask(df, scope, crude_choice):
    if scope == "All crudes":
        return pd.Series(True, index=df.index)
    if scope == "Single crude":
        return df["Crude"] == crude_choice
    return df["Region"] == scope

if scope == "Single crude":
    crude_choice = st.sidebar.selectbox("Which crude", list(crudes["Crude"]))

mask = scope_mask(crudes, scope, crude_choice)
c = crudes.copy()
c.loc[mask, "Freight"]         *= 1 + freight_pct / 100
c.loc[mask, "Cargo_Insurance"] *= 1 + insurance_pct / 100
c.loc[mask, "Port_Handling"]   *= 1 + port_pct / 100
c.loc[mask, "Diff_vs_Brent"]   += diff_adj
c.loc[mask, "Available_bbl"]   *= 1 + avail_pct / 100

brent = BRENT + brent_adj
c["Logistics_Cost"] = c["Freight"] + c["Cargo_Insurance"] + c["Port_Handling"]
c["FOB_Price"] = brent + c["Diff_vs_Brent"]
c["Delivered_Cost"] = c["FOB_Price"] + c["Logistics_Cost"]
c["Processing_Cost"] = c["Processing_cost"]
c["Total_Cost"] = c["Delivered_Cost"] + c["Processing_Cost"]
# Gross product worth per barrel (direct product prices), for context only.
c["GPW"] = sum(c[YIELD_COL[p]] / 100 * PRICES[p] for p in PRODUCTS)
c["Margin_per_bbl"] = c["GPW"] - c["Total_Cost"]

# ===========================================================================
# PROCUREMENT OPTIMISER
#   minimise total (delivered + processing) cost + big penalty for unmet demand
#   s.t. production >= demand and 0 <= barrels <= availability.
#   (No sulphur constraint - refining difficulty is in the processing cost.)
# ===========================================================================
def optimise_purchase(c, demand_bbl):
    BIG = 1e5  # penalty per barrel of unmet demand -> demand met whenever possible
    prob = pulp.LpProblem("procurement", pulp.LpMinimize)
    x = {r["Crude"]: pulp.LpVariable(f"x_{i}", lowBound=0, upBound=float(r["Available_bbl"]))
         for i, r in c.iterrows()}
    short = {p: pulp.LpVariable(f"short_{j}", lowBound=0) for j, p in enumerate(PRODUCTS)}
    prob += (pulp.lpSum(r["Total_Cost"] * x[r["Crude"]] for _, r in c.iterrows())
             + BIG * pulp.lpSum(short.values()))
    for p in PRODUCTS:
        prob += (pulp.lpSum(r[YIELD_COL[p]] / 100 * x[r["Crude"]] for _, r in c.iterrows())
                 + short[p] >= demand_bbl[p])
    prob.solve(pulp.PULP_CBC_CMD(msg=0))
    bought = {cr: max(x[cr].value() or 0.0, 0.0) for cr in x}
    shortfall = {p: max(short[p].value() or 0.0, 0.0) for p in PRODUCTS}
    return bought, shortfall

bought, shortfall = optimise_purchase(c, demand_bbl)
c["Barrels_bought"] = c["Crude"].map(bought)
total_crude = c["Barrels_bought"].sum()

# One barrel makes several products. Allocate to orders; the rest is surplus.
production = {p: float((c[YIELD_COL[p]] / 100 * c["Barrels_bought"]).sum()) for p in PRODUCTS}
allocated = {p: min(production[p], demand_bbl[p]) for p in PRODUCTS}
surplus = {p: max(production[p] - demand_bbl[p], 0.0) for p in PRODUCTS}

# --- Realized P&L vs inventory ---------------------------------------------
# Cost is allocated per barrel of product: total crude + processing cost is
# spread evenly across all barrels produced (yields sum to 100%, so total
# product barrels = total crude barrels). The cost of barrels SOLD to clients
# is the COGS in realized P&L; the cost of UNSOLD barrels stays in inventory.
crude_cost = float((c["Delivered_Cost"] * c["Barrels_bought"]).sum())
processing_cost = float((c["Processing_Cost"] * c["Barrels_bought"]).sum())
total_cost = crude_cost + processing_cost
revenue_orders = sum(allocated[p] * PRICES[p] for p in PRODUCTS)          # sold to clients
surplus_inventory_value = sum(surplus[p] * PRICES[p] for p in PRODUCTS)   # unsold stock at market
total_sold_bbl = sum(allocated.values())
total_surplus_bbl = sum(surplus.values())
avg_cost_per_bbl = total_cost / total_crude if total_crude > 0 else 0.0
cost_of_sold = avg_cost_per_bbl * total_sold_bbl                          # COGS of products sold
realized_pnl = revenue_orders - cost_of_sold                             # realized profit (sold only)
economic_value = revenue_orders + surplus_inventory_value - total_cost   # incl. inventory at market
avg_realized_per_bbl = realized_pnl / total_sold_bbl if total_sold_bbl > 0 else 0.0

uncovered = {p: shortfall[p] for p in PRODUCTS if shortfall[p] > 0.5}
maxed = list(c.loc[(c["Barrels_bought"] > c["Available_bbl"] - 0.5) & (c["Barrels_bought"] > 0.5), "Crude"])

# ===========================================================================
# SECTION 3 - EXECUTIVE SUMMARY
# ===========================================================================
st.header("3. Executive summary")
st.caption("Realized P&L counts only products sold to client orders. Unsold surplus is "
           "inventory, valued separately - not realized profit.")
k = st.columns(4)
k[0].metric("Realized P&L (orders)", f"${realized_pnl:,.0f}")
k[1].metric("Surplus inventory value", f"${surplus_inventory_value:,.0f}")
k[2].metric("Total crude purchased", f"{total_crude:,.0f} bbl")
k[3].metric("Avg realized profit", f"${avg_realized_per_bbl:.2f}/bbl sold")

# ===========================================================================
# SECTION 4 - RECOMMENDED CRUDE PURCHASE
# ===========================================================================
st.header("4. Recommended crude purchase")
buy = c[c["Barrels_bought"] > 0.5].copy()
if len(buy) > 0:
    st.bar_chart(buy.set_index("Crude")["Barrels_bought"].sort_values(), horizontal=True)
else:
    st.warning("No crude purchased - check client orders and availability.")
table_a = c.copy()
table_a["Share of mix %"] = (table_a["Barrels_bought"] / total_crude * 100).round(1) if total_crude > 0 else 0
table_a["Availability used %"] = (table_a["Barrels_bought"] / table_a["Available_bbl"].replace(0, pd.NA) * 100).round(1)
table_a["Availability remaining"] = (table_a["Available_bbl"] - table_a["Barrels_bought"]).round(0)
st.dataframe(
    table_a[["Crude", "Barrels_bought", "Share of mix %", "Delivered_Cost", "Processing_Cost",
             "Available_bbl", "Availability used %", "Availability remaining"]]
    .rename(columns={"Barrels_bought": "Barrels bought", "Delivered_Cost": "Delivered $/bbl",
                     "Processing_Cost": "Processing $/bbl", "Available_bbl": "Available bbl"}).round(2),
    use_container_width=True, hide_index=True)

# ===========================================================================
# SECTION 5 - PRODUCT PRODUCTION & ALLOCATION
# ===========================================================================
st.header("5. Product production & allocation")
table_b = pd.DataFrame({
    "Product": PRODUCTS,
    "Produced bbl": [round(production[p], 0) for p in PRODUCTS],
    "Client demand bbl": [round(demand_bbl[p], 0) for p in PRODUCTS],
    "Allocated to orders bbl": [round(allocated[p], 0) for p in PRODUCTS],
    "Surplus bbl": [round(surplus[p], 0) for p in PRODUCTS],
    "Coverage": ["Not covered (-%.0f)" % shortfall[p] if shortfall[p] > 0.5
                 else ("Covered" if demand_bbl[p] > 0 else "No order") for p in PRODUCTS],
})
prod_long = pd.DataFrame(
    [{"Product": p, "Series": "Produced", "bbl": production[p]} for p in PRODUCTS]
    + [{"Product": p, "Series": "Client demand", "bbl": demand_bbl[p]} for p in PRODUCTS])
prod_chart = (
    alt.Chart(prod_long).mark_bar().encode(
        x=alt.X("Product:N", title=None), xOffset="Series:N",
        y=alt.Y("bbl:Q", title="Barrels"), color=alt.Color("Series:N", title=None),
        tooltip=["Product:N", "Series:N", alt.Tooltip("bbl:Q", format=",.0f")],
    )
)
st.altair_chart(prod_chart, use_container_width=True)
st.dataframe(table_b, use_container_width=True, hide_index=True)

# ===========================================================================
# SECTION 6 - FINANCIAL RESULTS
# ===========================================================================
st.header("6. Financial results")
st.info("Sold products impact P&L. Unsold surplus products are inventory, not profit. "
        "Realized P&L = revenue from client orders minus the cost allocated to the barrels sold.")
fin = pd.DataFrame({
    "Item": [
        "Revenue from client orders (sold)",
        "Allocated cost of products sold",
        "Realized P&L from client orders",
        "Total delivered crude cost (all barrels bought)",
        "Total processing cost (all barrels bought)",
        "Surplus inventory value - NOT included in realized P&L",
        "Economic value including inventory (not realized profit)",
        "Average realized profit ($/bbl sold)",
    ],
    "Value": [
        f"${revenue_orders:,.0f}",
        f"-${cost_of_sold:,.0f}",
        f"${realized_pnl:,.0f}",
        f"-${crude_cost:,.0f}",
        f"-${processing_cost:,.0f}",
        f"${surplus_inventory_value:,.0f}",
        f"${economic_value:,.0f}",
        f"${avg_realized_per_bbl:.2f}",
    ],
})
st.dataframe(fin, use_container_width=True, hide_index=True)
st.caption("Realized P&L bridge (surplus inventory is excluded - it is stock, not profit):")
breakdown = pd.Series({"Order revenue": revenue_orders,
                       "Cost of products sold": -cost_of_sold,
                       "Realized P&L": realized_pnl})
st.bar_chart(breakdown)

# ===========================================================================
# SECTION 7 - CRUDE QUALITY (informative) & LOGISTICS
# ===========================================================================
st.header("7. Crude quality & logistics")
st.caption("Quality map (informative only): x = API, y = sulphur, bubble size = availability, "
           "colour = region. Hover a bubble to see the crude. Light sweet crudes sit bottom-right.")
quality_chart = (
    alt.Chart(c).mark_circle(opacity=0.75).encode(
        x=alt.X("API:Q", title="API gravity (higher = lighter)", scale=alt.Scale(zero=False)),
        y=alt.Y("Sulphur_%:Q", title="Sulphur (%)", scale=alt.Scale(zero=False)),
        size=alt.Size("Available_bbl:Q", title="Available (bbl)"),
        color=alt.Color("Region:N", title="Region"),
        tooltip=[alt.Tooltip("Crude:N"), alt.Tooltip("Region:N"), alt.Tooltip("Quality:N"),
                 alt.Tooltip("API:Q"), alt.Tooltip("Sulphur_%:Q"),
                 alt.Tooltip("Processing_Cost:Q", title="Processing $/bbl", format=".2f"),
                 alt.Tooltip("Delivered_Cost:Q", title="Delivered $/bbl", format=".2f")],
    ).interactive()
)
st.altair_chart(quality_chart, use_container_width=True)
st.caption("Manual shocks in the sidebar (freight, insurance, port, differential, availability) "
           "re-solve the whole procurement instantly - e.g. raise Middle East insurance to stress "
           "Basrah Medium.")

# ===========================================================================
# SECTION 8 - DETAILED DATA
# ===========================================================================
st.header("8. Detailed data")
with st.expander("Crude characteristics & delivered cost build-up"):
    st.dataframe(c[["Crude", "Region", "API", "Sulphur_%", "Diff_vs_Brent", "FOB_Price",
                    "Freight", "Cargo_Insurance", "Port_Handling", "Delivered_Cost",
                    "Processing_Cost"]].round(2),
                 use_container_width=True, hide_index=True)
with st.expander("Product yields (% of barrel) and per-barrel economics"):
    st.dataframe(c[["Crude", "Quality", "Diesel_%", "Jet_%", "Gasoline_%", "Naphtha_%",
                    "FuelOil_%", "LPG_%", "GPW", "Margin_per_bbl"]].round(2),
                 use_container_width=True, hide_index=True)
with st.expander("Refined product selling prices ($/bbl)"):
    st.dataframe(pd.DataFrame({"Product": PRODUCTS, "Selling price ($/bbl)": [PRICES[p] for p in PRODUCTS]}),
                 use_container_width=True, hide_index=True)