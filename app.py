import streamlit as st

st.set_page_config(
    page_title="Refining Margin Optimizer",
    page_icon="🛢️",
    layout="centered",
)

st.title("🛢️ Refining Margin Optimizer")
st.write(
    "A simple tool to estimate the refining margin per barrel of crude. "
    "Adjust the parameters in the sidebar to see the margin change."
)

st.sidebar.header("Parameters")

crude_price = st.sidebar.number_input("Crude price ($/bbl)", min_value=0.0, value=80.0, step=1.0)
gasoline_price = st.sidebar.number_input("Gasoline price ($/bbl)", min_value=0.0, value=95.0, step=1.0)
diesel_price = st.sidebar.number_input("Diesel price ($/bbl)", min_value=0.0, value=100.0, step=1.0)

gasoline_yield = st.sidebar.slider("Gasoline yield (%)", 0, 100, 45)
diesel_yield = st.sidebar.slider("Diesel yield (%)", 0, 100, 40)

opex = st.sidebar.number_input("Operating cost ($/bbl)", min_value=0.0, value=4.0, step=0.5)

product_revenue = (gasoline_yield / 100) * gasoline_price + (diesel_yield / 100) * diesel_price
gross_margin = product_revenue - crude_price - opex

col1, col2 = st.columns(2)
col1.metric("Product revenue ($/bbl)", f"{product_revenue:.2f}")
col2.metric("Gross margin ($/bbl)", f"{gross_margin:.2f}")

if gross_margin >= 0:
    st.success(f"Positive margin: {gross_margin:.2f} $/bbl")
else:
    st.error(f"Negative margin: {gross_margin:.2f} $/bbl")

st.caption("Simple demo version — Varo Energy application project.")