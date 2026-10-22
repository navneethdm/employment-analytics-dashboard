
import pandas as pd
import plotly.express as px
import streamlit as st

from utils.csv_manager import DataFileError
from utils.unemployment_manager import UnemploymentManager

st.set_page_config(page_title="Unemployment Trends", layout="wide")
st.title("Unemployment in India")
st.caption("Explore state-wise unemployment trends from May 2019 to June 2020.")
st.info(
    "Each row is an estimate for a state, month and area (Rural or Urban). "
    "This is historical data, not a measure of unemployment today."
)

if "un_flash" in st.session_state:
    st.success(st.session_state.pop("un_flash"))

try:
    manager = UnemploymentManager()
except DataFileError as err:
    st.error(str(err))
    st.stop()

for note in manager.warnings:
    st.warning(note)

data = manager.data.copy()
if data.empty:
    st.warning("The unemployment dataset is empty.")
    st.stop()

# Filters are shared by all five tabs.
st.sidebar.header("Filters")
all_states = sorted(data["state"].dropna().unique().tolist())
selected_states = st.sidebar.multiselect("State", all_states)
selected_area = st.sidebar.selectbox("Area", ["All", "Rural", "Urban"])
selected_phase = st.sidebar.selectbox(
    "Period", ["All", "Before lockdown", "During/after lockdown"]
)

filtered = manager.get_records(
    selected_states, selected_area, "All", selected_phase, "date", True
).copy()
filters_used = {
    "State": ", ".join(selected_states) if selected_states else "All states",
    "Area": selected_area,
    "Period": selected_phase,
}
clean = filtered.dropna(subset=["unemployment_rate"]).copy()

# Five clear sections: View, Manage Data, Compare, Charts and Report.
tab_view, tab_manage, tab_compare, tab_charts, tab_report = st.tabs(
    ["View", "Manage Data", "Compare", "Charts", "Report"]
)

# VIEW: keep the main trend chart and key information simple.
with tab_view:
    st.subheader("Unemployment at a glance")
    if clean.empty:
        st.info("No records match these filters. Change the filters on the left.")
    else:
        state_average = clean.groupby("state")["unemployment_rate"].mean().sort_values(ascending=False)
        average_rate = clean["unemployment_rate"].mean()
        c1, c2, c3 = st.columns(3)
        c1.metric("Average unemployment", f"{average_rate:.2f}%")
        c2.metric("Highest state average", state_average.index[0], f"{state_average.iloc[0]:.2f}%")
        c3.metric("Lowest state average", state_average.index[-1], f"{state_average.iloc[-1]:.2f}%")

        trend = clean.groupby(["period", "area"], as_index=False)["unemployment_rate"].mean()
        trend = trend.sort_values("period")
        fig = px.line(
            trend, x="period", y="unemployment_rate", color="area", markers=True,
            title="Monthly unemployment trend",
            labels={"period": "Month", "unemployment_rate": "Unemployment rate (%)", "area": "Area"},
        )
        fig.update_layout(legend_title_text="Area")
        st.plotly_chart(fig, use_container_width=True)
        st.caption("The lines show average unemployment rates across the selected records for each month.")

        st.subheader("Quick insights")
        st.write(f"- **Records shown:** {len(filtered):,}")
        st.write(f"- **States included:** {clean['state'].nunique()}")
        if "Rural" in clean["area"].values and "Urban" in clean["area"].values:
            area_average = clean.groupby("area")["unemployment_rate"].mean()
            higher_area = "Rural" if area_average["Rural"] > area_average["Urban"] else "Urban"
            gap = abs(area_average["Rural"] - area_average["Urban"])
            st.write(f"- **Rural/urban comparison:** {higher_area} is higher by {gap:.2f} percentage points on average.")
        st.caption("These are descriptive comparisons. They do not prove what caused unemployment to change.")
        with st.expander("View the filtered data table"):
            st.dataframe(filtered, use_container_width=True, hide_index=True)

# MANAGE DATA: Add, Edit and Delete are in one place, selected using a simple menu.
with tab_manage:
    st.subheader("Manage unemployment records")
    st.caption("Choose an action below. Changes are saved to the project CSV file.")
    action = st.radio("Action", ["Add record", "Edit record", "Delete record"], horizontal=True)

    if action == "Add record":
        with st.form("simple_add_record"):
            col1, col2, col3 = st.columns(3)
            new_state = col1.text_input("State")
            new_date = col2.date_input("Date", value=pd.Timestamp("2020-07-31"))
            new_area = col3.selectbox("Area", manager.AREAS)
            col4, col5, col6 = st.columns(3)
            new_rate = col4.number_input("Unemployment rate (%)", 0.0, 100.0, 5.0, step=0.1)
            new_employed = col5.number_input("Estimated employed", min_value=0.0, value=1000000.0, step=1000.0)
            new_participation = col6.number_input("Labour participation rate (%)", 0.0, 100.0, 40.0, step=0.1)
            submitted = st.form_submit_button("Add record")
        if submitted:
            try:
                record_id = manager.add_record(new_state, new_date, new_area, new_rate, new_employed, new_participation)
                st.session_state["un_flash"] = f"Record {record_id} added successfully."
                st.rerun()
            except (ValueError, DataFileError) as err:
                st.error(str(err))

    elif action == "Edit record":
        record_id = st.number_input("Record ID to edit", min_value=1, step=1, key="simple_edit_id")
        row = manager.get_record(int(record_id))
        if row is None:
            st.info("Enter the ID of an existing record.")
        else:
            st.write(f"Editing: **{row['state']} — {row['area']} — {row['date']}**")
            with st.form("simple_edit_record"):
                rate = st.number_input("Unemployment rate (%)", 0.0, 100.0, float(row["unemployment_rate"]), step=0.1)
                employed = st.number_input("Estimated employed", min_value=0.0, value=float(row["employed"]), step=1000.0)
                participation = st.number_input("Labour participation rate (%)", 0.0, 100.0, float(row["labour_participation_rate"]), step=0.1)
                submitted = st.form_submit_button("Save changes")
            if submitted:
                try:
                    manager.update_record(int(record_id), rate, employed, participation)
                    st.session_state["un_flash"] = f"Record {int(record_id)} updated successfully."
                    st.rerun()
                except (ValueError, DataFileError) as err:
                    st.error(str(err))

    else:
        record_id = st.number_input("Record ID to delete", min_value=1, step=1, key="simple_delete_id")
        row = manager.get_record(int(record_id))
        if row is None:
            st.info("Enter the ID of an existing record.")
        else:
            st.warning(f"You selected {row['state']} — {row['area']} — {row['date']} (rate: {row['unemployment_rate']}%).")
            confirm = st.checkbox("I confirm I want to delete this record.")
            if st.button("Delete record", disabled=not confirm):
                try:
                    manager.delete_record(int(record_id))
                    st.session_state["un_flash"] = f"Record {int(record_id)} deleted successfully."
                    st.rerun()
                except (ValueError, DataFileError) as err:
                    st.error(str(err))

# COMPARE: charts specifically intended to compare groups.
with tab_compare:
    st.subheader("Compare unemployment")
    if clean.empty:
        st.info("No records match these filters. Change the filters on the left.")
    else:
        left, right = st.columns(2)
        with left:
            state_avg = clean.groupby("state", as_index=False)["unemployment_rate"].mean()
            state_avg = state_avg.sort_values("unemployment_rate", ascending=False).head(10).sort_values("unemployment_rate")
            fig_state = px.bar(
                state_avg, x="unemployment_rate", y="state", orientation="h",
                title="10 states with highest average unemployment",
                labels={"state": "State", "unemployment_rate": "Average rate (%)"},
            )
            st.plotly_chart(fig_state, use_container_width=True)
        with right:
            area_avg = clean.groupby("area", as_index=False)["unemployment_rate"].mean()
            fig_area = px.bar(
                area_avg, x="area", y="unemployment_rate", text_auto=".2f",
                title="Rural vs Urban", labels={"area": "Area", "unemployment_rate": "Average rate (%)"},
            )
            st.plotly_chart(fig_area, use_container_width=True)
            if len(area_avg) == 2:
                values = area_avg.set_index("area")["unemployment_rate"]
                higher = "Rural" if values["Rural"] > values["Urban"] else "Urban"
                st.write(f"**Takeaway:** {higher} has a higher average by {abs(values['Rural'] - values['Urban']):.2f} percentage points.")

        phase_avg = clean.groupby("covid_phase", as_index=False)["unemployment_rate"].mean()
        if not phase_avg.empty:
            fig_phase = px.bar(
                phase_avg, x="covid_phase", y="unemployment_rate", text_auto=".2f",
                title="Before lockdown vs during/after lockdown",
                labels={"covid_phase": "Period", "unemployment_rate": "Average rate (%)"},
            )
            st.plotly_chart(fig_phase, use_container_width=True)
            st.caption("This comparison does not prove that lockdown alone caused any change.")

# CHARTS: preserve the three analysis charts from the original page.
with tab_charts:
    st.subheader("Unemployment charts")
    st.caption("All charts use the filters selected in the sidebar.")
    if clean.empty:
        st.info("No records match these filters.")
    else:
        trend = clean.groupby(["period", "area"], as_index=False)["unemployment_rate"].mean().sort_values("period")
        fig1 = px.line(
            trend, x="period", y="unemployment_rate", color="area", markers=True,
            title="Monthly unemployment trend",
            labels={"period": "Month", "unemployment_rate": "Unemployment rate (%)", "area": "Area"},
        )
        fig1.update_layout(xaxis_tickangle=-45, legend_title_text="Area")
        st.plotly_chart(fig1, use_container_width=True)

        state_avg = clean.groupby("state", as_index=False)["unemployment_rate"].mean()
        state_avg = state_avg.sort_values("unemployment_rate", ascending=False).head(10).sort_values("unemployment_rate")
        fig2 = px.bar(
            state_avg, x="unemployment_rate", y="state", orientation="h", text_auto=".2f",
            title="Top 10 states by average unemployment",
            labels={"state": "State", "unemployment_rate": "Average rate (%)"},
        )
        st.plotly_chart(fig2, use_container_width=True)

# REPORT: a separate, clean place to read and download the report.
with tab_report:
    st.subheader("Unemployment report")
    report = manager.build_report(filtered, filters_used)
    st.text(report)
    col1, col2 = st.columns(2)
    col1.download_button(
        "Download report (.txt)", report, file_name="unemployment_report.txt",
        mime="text/plain", use_container_width=True,
    )
    col2.download_button(
        "Download filtered data (.csv)", filtered.to_csv(index=False),
        file_name="unemployment_filtered.csv", mime="text/csv", use_container_width=True,
    )

