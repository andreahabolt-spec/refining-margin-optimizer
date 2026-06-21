


# app.py
# CRUDE NETBACK & REFINERY MARGIN OPTIMISER
# Phase 1 - Step 1 (extended): enriched crude table + delivered crude cost
#
# What this version does:
#   1. Describes 8 crude grades by quality, geography, logistics and risk.
#   2. Computes the DELIVERED CRUDE COST for each grade:
#         Delivered Cost = FOB Price + Freight + Cargo Insurance + Port/Handling
#      where FOB Price = Brent benchmark + the crude's differential to Brent.
#
# All numbers are illustrative starting assumptions - we make them
# interactive in a later step.
 
import streamlit as st
import pandas as pd
 
# --- Page setup -------------------------------------------------------------
st.set_page_config(
    page_title="Crude Netback & Refinery Margin Optimiser",
    layout="wide",
)
 
st.title("Crude Netback & Refinery Margin Optimiser")
st.caption("North-West Europe refining economics - illustrative model")
 
# --- Market benchmark -------------------------------------------------------
# Brent is the NWE pricing benchmark. Every crude is priced as a differential
# to Brent. For now Brent is a single fixed assumption; later it becomes a
# slider in the sidebar.
BRENT = 82.00  # USD per barrel (illustrative)
 
st.write(
    f"All grades are priced against **Dated Brent = ${BRENT:.2f}/bbl** "
    "(illustrative). The table below builds each crude's **delivered cost** "
    "into North-West Europe, accounting for its quality, route and risk."
)
 
# --- Crude data -------------------------------------------------------------
# Columns:
#   Region / Route          : where the crude is produced and how it reaches NWE
#   Quality                 : plain-language quality category
#   API / Sulphur_%         : physical quality (light vs heavy, sweet vs sour)
#   Diff_vs_Brent ($/bbl)   : FOB price vs Brent (+ premium, - discount)
#   Freight ($/bbl)         : cost to ship the cargo to NWE (longer route = more)
#   Cargo_Insurance ($/bbl) : insurance on the cargo value (rises with risk)
#   Port_Handling ($/bbl)   : terminal / handling cost at discharge
#   Availability_kbd        : how much we can realistically source (kb/d)
#   Geo_Risk                : qualitative exposure to a regional disruption
 
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
 
# --- Delivered crude cost ---------------------------------------------------
# FOB price = what we pay for the crude at the load port = Brent + differential.
crudes["FOB_Price"] = BRENT + crudes["Diff_vs_Brent"]
 
# Delivered cost = FOB + all the costs of getting the cargo into NWE.
crudes["Delivered_Cost"] = (
    crudes["FOB_Price"]
    + crudes["Freight"]
    + crudes["Cargo_Insurance"]
    + crudes["Port_Handling"]
)
 
# --- Display: quality & geography ------------------------------------------
st.subheader("1) Crude profile - quality, origin and risk")
profile_cols = ["Crude", "Region", "Route", "Quality", "API", "Sulphur_%",
                "Availability_kbd", "Geo_Risk"]
st.dataframe(crudes[profile_cols], use_container_width=True, hide_index=True)
 
# --- Display: delivered cost build-up --------------------------------------
st.subheader("2) Delivered cost build-up ($/bbl)")
cost_cols = ["Crude", "Diff_vs_Brent", "FOB_Price", "Freight",
             "Cargo_Insurance", "Port_Handling", "Delivered_Cost"]
st.dataframe(crudes[cost_cols].round(2), use_container_width=True, hide_index=True)
 
st.info(
    "Two things stand out. **Azeri Light** is high quality (light, very sweet) "
    "and trades at a premium to Brent, yet its long BTC/Ceyhan route adds "
    "about $2/bbl of freight, pushing its delivered cost above every short-haul "
    "North Sea grade. **Basrah Medium** is the opposite: the deepest discount "
    "to Brent makes it the cheapest barrel to land in NWE, but it is also the "
    "most sour and the most risk-exposed. Whether 'cheap and sour' really beats "
    "'expensive and clean' depends on what the products are worth - which is "
    "exactly what we add next."
)