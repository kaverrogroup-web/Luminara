import streamlit as st

st.title("🌌 Luminara Labs")
st.write("Astro-financial analytics playground — planetary cycles, harmonics, and timing.")

st.subheader("Test Input")
date = st.date_input("Select a date")
st.write(f"You picked {date}")
