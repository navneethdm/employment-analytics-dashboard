import plotly.express as px
import streamlit as st

from utils.csv_manager import DataFileError
from utils.jobs_manager import JobsManager

st.set_page_config(page_title="Job Market", layout="wide")
st.title("Job Market & Demand")
st.caption("Owner: Navneeth Dinukumar Menon | data/jobs.csv | data science and analytics job postings from Naukri.com")

if "jb_flash" in st.session_state:
    st.success(st.session_state.pop("jb_flash"))

# The CSV is loaded fresh every time this page runs.
try:
    manager = JobsManager()
except DataFileError as err:
    st.error(str(err))
    st.stop()
for note in manager.warnings:
    st.warning(note)

data = manager.data
MAX_ROWS = 500                                  # the table is capped so the page stays fast

# ---------------------------------------------------------------- sidebar filters
st.sidebar.header("Filters")
search = st.sidebar.text_input("Search job title or company", key="jb_search")
roles = st.sidebar.multiselect("Role type", sorted(data["role_category"].dropna().unique()), key="jb_roles")
top_cities = data["city"].value_counts().head(30).index.tolist()
cities = st.sidebar.multiselect("City (30 most common)", top_cities, key="jb_cities")
exp_range = st.sidebar.slider("Experience (years, midpoint)", 0.0, 30.0, (0.0, 30.0), key="jb_exp")
salary_only = st.sidebar.checkbox("Only postings that show a salary", key="jb_salary")
sort_by = st.sidebar.selectbox("Sort by", ["record_id", "job_title", "company", "exp_mid",
                                           "salary_mid_lpa", "city"], key="jb_sort")
ascending = st.sidebar.radio("Order", ["Ascending", "Descending"], key="jb_order") == "Ascending"

filtered = manager.get_records(roles, cities, search, exp_range, salary_only, sort_by, ascending)
filters_used = {"Search": search or "none", "Role type": ", ".join(roles) or "All",
                "City": ", ".join(cities) or "All", "Experience": f"{exp_range[0]} to {exp_range[1]} years",
                "Only with salary": salary_only,
                "Sorted by": f"{sort_by} ({'ascending' if ascending else 'descending'})"}

tab_view, tab_add, tab_edit, tab_delete, tab_charts, tab_report = st.tabs(
    ["View", "Add", "Edit", "Delete", "Charts", "Report"])

# ---------------------------------------------------------------------------- READ
with tab_view:
    stats = manager.summary_stats(filtered)
    if "top_city" in stats:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Job postings", f"{stats['job_postings']:,}")
        c2.metric("Average experience asked", f"{stats['average_experience_years']} yrs")
        c3.metric("Top city", stats["top_city"])
        c4.metric("Median salary", f"{stats['median_salary_lakh_per_year']} lakh/yr"
                  if "median_salary_lakh_per_year" in stats else "not shown")
        st.write(f"Most common role type: **{stats['top_role']}**")
    st.caption(f"Missing values: {stats.get('postings_without_salary_excluded', 0):,} postings do not show a "
               f"salary, so they are excluded from the salary figures only.")
    st.dataframe(filtered.head(MAX_ROWS).drop(columns=["skills"], errors="ignore"),
                 width="stretch", hide_index=True)
    st.caption(f"Showing the first {min(MAX_ROWS, len(filtered)):,} of {len(filtered):,} matching rows.")

# -------------------------------------------------------------------------- CREATE
with tab_add:
    st.subheader("Add a new job posting")
    with st.form("jb_add_form"):
        a1, a2 = st.columns(2)
        new_title = a1.text_input("Job title *")
        new_company = a2.text_input("Company *")
        new_location = st.text_input("Location *", placeholder="e.g. Kochi, Bengaluru")
        b1, b2, b3, b4 = st.columns(4)
        new_min = b1.number_input("Min experience (yrs) *", 0, 40, 2)
        new_max = b2.number_input("Max experience (yrs) *", 0, 40, 5)
        new_smin = b3.number_input("Min salary (lakh/yr, 0 = not shown)", 0.0, step=0.5)
        new_smax = b4.number_input("Max salary (lakh/yr, 0 = not shown)", 0.0, step=0.5)
        new_skills = st.text_input("Skills (optional)", placeholder="e.g. Python SQL Tableau")
        if st.form_submit_button("Add job posting"):
            try:
                new_id = manager.add_record(new_title, new_company, new_min, new_max, new_location,
                                            new_skills, new_smin or None, new_smax or None)
            except (ValueError, DataFileError) as err:
                st.error(str(err))
            else:
                st.session_state["jb_flash"] = f"Job posting {new_id} added."
                st.rerun()

# -------------------------------------------------------------------------- UPDATE
with tab_edit:
    st.subheader("Edit a job posting")
    edit_id = st.number_input("Record ID to edit", min_value=1, step=1, key="jb_edit_id")
    row = manager.get_record(int(edit_id))
    if row is None:
        st.warning(f"No record with ID {int(edit_id)} exists.")
    else:
        st.write(f"**{row['job_title']}** at {row['company']}")
        has_pay = row["salary_min_lpa"] == row["salary_min_lpa"]        # NaN is never equal to itself
        with st.form(f"jb_edit_form_{int(edit_id)}"):
            e_location = st.text_input("Location", value=str(row["location"]))
            e_skills = st.text_input("Skills", value="" if row["skills"] != row["skills"] else str(row["skills"]))
            f1, f2, f3, f4 = st.columns(4)
            e_min = f1.number_input("Min experience", 0, 40, int(row["exp_min"]))
            e_max = f2.number_input("Max experience", 0, 40, int(row["exp_max"]))
            e_smin = f3.number_input("Min salary (0 = not shown)", 0.0, value=float(row["salary_min_lpa"]) if has_pay else 0.0, step=0.5)
            e_smax = f4.number_input("Max salary (0 = not shown)", 0.0, value=float(row["salary_max_lpa"]) if has_pay else 0.0, step=0.5)
            if st.form_submit_button("Save changes"):
                try:
                    manager.update_record(int(edit_id), e_location, e_skills, e_min, e_max,
                                          e_smin or None, e_smax or None)
                except (ValueError, DataFileError) as err:
                    st.error(str(err))
                else:
                    st.session_state["jb_flash"] = f"Job posting {int(edit_id)} updated."
                    st.rerun()

# -------------------------------------------------------------------------- DELETE
with tab_delete:
    st.subheader("Delete a job posting")
    del_id = st.number_input("Record ID to delete", min_value=1, step=1, key="jb_del_id")
    row = manager.get_record(int(del_id))
    if row is None:
        st.warning(f"No record with ID {int(del_id)} exists.")
    else:
        st.write(f"**{row['job_title']}** at {row['company']} ({row['location']})")
        confirmed = st.checkbox("Yes, delete this record", key=f"jb_confirm_{int(del_id)}")
        if st.button("Delete record", disabled=not confirmed):
            try:
                manager.delete_record(int(del_id))
            except (ValueError, DataFileError) as err:
                st.error(str(err))
            else:
                st.session_state["jb_flash"] = f"Job posting {int(del_id)} deleted."
                st.rerun()

# ------------------------------------------------------------------------ CHARTS
with tab_charts:
    st.caption("Charts use the filtered rows.")
    if filtered.empty:
        st.info("No data to chart with the current filters.")
    else:
        st.plotly_chart(px.bar(manager.city_counts(filtered), x="city", y="postings",
                               title="Cities with the most postings"), width="stretch")
        st.plotly_chart(px.pie(filtered, names="role_category", title="Share of postings by role type"),
                        width="stretch")
        exp = filtered.dropna(subset=["exp_mid"])
        st.plotly_chart(px.histogram(exp, x="exp_mid", nbins=15, title="Experience asked for (years)",
                                     labels={"exp_mid": "Experience midpoint (years)"}),
                        width="stretch")
        if st.checkbox("Also show most requested skills (a little slower)", key="jb_skills_chart"):
            st.plotly_chart(px.bar(manager.skill_counts(filtered), x="skill", y="postings",
                                   title="Skills mentioned most often"), width="stretch")

# ------------------------------------------------------------------------ REPORT
with tab_report:
    report = manager.build_report(filtered, filters_used)
    st.text(report)
    d1, d2 = st.columns(2)
    d1.download_button("Download report (.txt)", report, file_name="job_market_report.txt")
    d2.download_button("Download filtered data (.csv)", filtered.to_csv(index=False),
                       file_name="jobs_filtered.csv", mime="text/csv")
