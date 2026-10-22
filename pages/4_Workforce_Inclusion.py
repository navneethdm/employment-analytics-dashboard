
import plotly.express as px
import streamlit as st

from utils.csv_manager import DataFileError
from utils.inclusion_manager import InclusionManager

st.set_page_config(page_title="Workforce Inclusion", layout="wide")
st.title("Workforce Inclusion")
st.caption("Owner: Jyothi S | data/labour_participation.csv | female labour force participation by country, 1990 to 2025")

if "wi_flash" in st.session_state:
    st.success(st.session_state.pop("wi_flash"))

try:
    manager = InclusionManager()
except DataFileError as err:
    st.error(str(err))
    st.stop()

for note in manager.warnings:
    st.warning(note)

data = manager.data
years = data["year"].dropna()
year_low, year_high = (
    (int(years.min()), int(years.max()))
    if not years.empty
    else (1990, 2025)
)

st.sidebar.header("Filters")
countries_only = st.sidebar.checkbox(
    "Real countries only (hide groups like 'World')",
    value=True,
    key="wi_only"
)
countries = st.sidebar.multiselect(
    "Country",
    sorted(data["country"].dropna().unique()),
    key="wi_countries"
)
region = st.sidebar.selectbox(
    "Region",
    ["All"] + sorted(data["region"].dropna().unique()),
    key="wi_region"
)
income = st.sidebar.selectbox(
    "Income group",
    ["All"] + sorted(data["income_group"].dropna().unique()),
    key="wi_income"
)
year_range = st.sidebar.slider(
    "Years",
    year_low,
    max(year_high, year_low + 1),
    (year_low, max(year_high, year_low + 1)),
    key="wi_years"
)
sort_by = st.sidebar.selectbox(
    "Sort by",
    ["country", "year", "female_participation_rate", "region"],
    key="wi_sort"
)
ascending = st.sidebar.radio(
    "Order",
    ["Ascending", "Descending"],
    key="wi_order"
) == "Ascending"

filtered = manager.get_records(
    countries,
    region,
    income,
    year_range,
    countries_only,
    sort_by,
    ascending
)

filters_used = {
    "Countries only": countries_only,
    "Country": ", ".join(countries) or "All",
    "Region": region,
    "Income group": income,
    "Years": f"{year_range[0]} to {year_range[1]}",
    "Sorted by": f"{sort_by} ({'ascending' if ascending else 'descending'})"
}

tab_view, tab_add, tab_edit, tab_delete, tab_charts, tab_report = st.tabs(
    ["View", "Add", "Edit", "Delete", "Charts", "Report"]
)

with tab_view:
    stats = manager.summary_stats(filtered)

    if "average_rate" in stats:
        c1, c2, c3, c4 = st.columns(4)

        c1.metric("Rows shown", f"{stats['rows']:,}")
        c2.metric(
            "Average participation",
            f"{stats['average_rate']}%"
        )
        c3.metric(
            "Highest country",
            stats["highest_country"],
            f"{stats['highest_country_rate']}%",
            delta_color="off"
        )
        c4.metric(
            "Lowest country",
            stats["lowest_country"],
            f"{stats['lowest_country_rate']}%",
            delta_color="off"
        )

        st.write(f"Countries covered: **{stats['countries_covered']}**")

        if "average_by_region" in stats:
            st.write("Average by region:", stats["average_by_region"])

    st.caption(
        f"Missing values: rows with a missing rate are excluded from these statistics "
        f"({stats['excluded_missing']} excluded). The rate is the percentage of women aged 15+ "
        f"who are working or looking for work."
    )

    st.dataframe(filtered, width="stretch", hide_index=True)

with tab_add:
    st.subheader("Add a new record")

    with st.form("wi_add_form"):
        a1, a2, a3 = st.columns(3)

        new_country = a1.text_input("Country *", placeholder="e.g. India")
        new_code = a2.text_input(
            "Country code * (3 letters)",
            placeholder="e.g. IND",
            max_chars=3
        )
        new_year = a3.number_input("Year *", 1960, 2100, 2025)

        b1, b2, b3 = st.columns(3)

        new_rate = b1.number_input(
            "Female participation rate (%) *",
            0.0,
            100.0,
            40.0,
            step=0.1
        )
        new_region = b2.text_input(
            "Region (leave empty for a group, not a country)"
        )
        new_income = b3.text_input("Income group (optional)")

        if st.form_submit_button("Add record"):
            try:
                new_id = manager.add_record(
                    new_country,
                    new_code,
                    new_year,
                    new_rate,
                    new_region,
                    new_income
                )
            except (ValueError, DataFileError) as err:
                st.error(str(err))
            else:
                st.session_state["wi_flash"] = f"Record {new_id} added."
                st.rerun()

with tab_edit:
    st.subheader("Edit a record")

    edit_id = st.number_input(
        "Record ID to edit",
        min_value=1,
        step=1,
        key="wi_edit_id"
    )

    row = manager.get_record(int(edit_id))

    if row is None:
        st.warning(f"No record with ID {int(edit_id)} exists.")
    else:
        st.write(
            f"**{row['country']}** ({row['country_code']}), "
            f"{int(row['year'])} (country and year cannot be changed)"
        )

        with st.form(f"wi_edit_form_{int(edit_id)}"):
            e1, e2, e3 = st.columns(3)

            e_rate = e1.number_input(
                "Female participation rate (%)",
                0.0,
                100.0,
                float(row["female_participation_rate"]),
                step=0.1
            )
            e_region = e2.text_input(
                "Region",
                value="" if row["region"] != row["region"] else str(row["region"])
            )
            e_income = e3.text_input(
                "Income group",
                value="" if row["income_group"] != row["income_group"]
                else str(row["income_group"])
            )

            if st.form_submit_button("Save changes"):
                try:
                    manager.update_record(
                        int(edit_id),
                        e_rate,
                        e_region,
                        e_income
                    )
                except (ValueError, DataFileError) as err:
                    st.error(str(err))
                else:
                    st.session_state["wi_flash"] = (
                        f"Record {int(edit_id)} updated."
                    )
                    st.rerun()

with tab_delete:
    st.subheader("Delete a record")

    del_id = st.number_input(
        "Record ID to delete",
        min_value=1,
        step=1,
        key="wi_del_id"
    )

    row = manager.get_record(int(del_id))

    if row is None:
        st.warning(f"No record with ID {int(del_id)} exists.")
    else:
        st.write(
            f"**{row['country']}** | {int(row['year'])} | "
            f"rate {row['female_participation_rate']:.1f}%"
        )

        confirmed = st.checkbox(
            "Yes, delete this record",
            key=f"wi_confirm_{int(del_id)}"
        )

        if st.button("Delete record", disabled=not confirmed):
            try:
                manager.delete_record(int(del_id))
            except (ValueError, DataFileError) as err:
                st.error(str(err))
            else:
                st.session_state["wi_flash"] = (
                    f"Record {int(del_id)} deleted."
                )
                st.rerun()

with tab_charts:
    clean = filtered.dropna(subset=["female_participation_rate"])

    st.caption(
        "Charts use the filtered rows. Rows with a missing rate are excluded."
    )

    if clean.empty:
        st.info("No data to chart with the current filters.")
    else:
        options = sorted(clean["country"].unique())

        default = [
            c for c in ["India", "China", "United States"]
            if c in options
        ][:3] or options[:3]

        picked = st.multiselect(
            "Countries to compare in the line chart",
            options,
            default=default,
            key="wi_pick"
        )

        if picked:
            line = clean[clean["country"].isin(picked)].sort_values("year")

            st.plotly_chart(
                px.line(
                    line,
                    x="year",
                    y="female_participation_rate",
                    color="country",
                    title="Female labour force participation over time"
                ),
                width="stretch"
            )
        else:
            st.info("Pick at least one country for the line chart.")

        st.plotly_chart(
            px.bar(
                manager.region_averages(clean),
                x="region",
                y="average_rate",
                title="Average participation by region"
            ),
            width="stretch"
        )

with tab_report:
    report = manager.build_report(filtered, filters_used)

    st.text(report)

    d1, d2 = st.columns(2)

    d1.download_button(
        "Download report (.txt)",
        report,
        file_name="inclusion_report.txt"
    )

    d2.download_button(
        "Download filtered data (.csv)",
        filtered.to_csv(index=False),
        file_name="labour_participation_filtered.csv",
        mime="text/csv"
    )
