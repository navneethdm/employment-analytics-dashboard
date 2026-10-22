import streamlit as st

st.set_page_config(page_title="Employment Analytics Dashboard", layout="wide")
st.title("Employment Analytics Dashboard")
st.caption("Team B14 | SDG 8: Decent Work and Economic Growth")
st.write(
    "Use the sidebar to open a page. Each page lets you view, add, edit and "
    "delete records in its own dataset, explore charts, and download a report."
)
st.subheader("Pages and datasets")
st.table({
    "Page": ["1 Unemployment", "2 Job Market", "3 Wages", "4 Workforce Inclusion"],
    "Dataset": ["unemployment.csv", "jobs.csv", "salaries.csv", "labour_participation.csv"],
    "Owner": ["Anamika P Vivekan", "Navneeth Dinukumar Menon", "Kripa S D", "Jyothi S"],
})