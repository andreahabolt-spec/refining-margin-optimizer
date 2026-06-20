import streamlit as st

st.set_page_config(
    page_title="Refining Margin Optimizer",
    page_icon="🛢️",
    layout="centered",
)

st.title("🛢️ Refining Margin Optimizer")
st.write(
    "Outil simple d'estimation de la marge de raffinage, par baril de brut. "
    "Ajuste les paramètres dans la barre latérale pour voir la marge évoluer."
)

st.sidebar.header("Paramètres")

crude_price = st.sidebar.number_input("Prix du brut ($/bbl)", min_value=0.0, value=80.0, step=1.0)
gasoline_price = st.sidebar.number_input("Prix de l'essence ($/bbl)", min_value=0.0, value=95.0, step=1.0)
diesel_price = st.sidebar.number_input("Prix du diesel ($/bbl)", min_value=0.0, value=100.0, step=1.0)

gasoline_yield = st.sidebar.slider("Rendement essence (%)", 0, 100, 45)
diesel_yield = st.sidebar.slider("Rendement diesel (%)", 0, 100, 40)

opex = st.sidebar.number_input("Coût opératoire ($/bbl)", min_value=0.0, value=4.0, step=0.5)

product_revenue = (gasoline_yield / 100) * gasoline_price + (diesel_yield / 100) * diesel_price
gross_margin = product_revenue - crude_price - opex

col1, col2 = st.columns(2)
col1.metric("Revenu produits ($/bbl)", f"{product_revenue:.2f}")
col2.metric("Marge brute ($/bbl)", f"{gross_margin:.2f}")

if gross_margin >= 0:
    st.success(f"Marge positive : {gross_margin:.2f} $/bbl")
else:
    st.error(f"Marge négative : {gross_margin:.2f} $/bbl")

st.caption("Version simple de démonstration — projet de candidature Varo Energy.")