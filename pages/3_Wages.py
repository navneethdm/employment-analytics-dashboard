from datetime import datetime
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from utils.csv_manager import DataFileError
from utils.salary_manager import SalaryManager


st.set_page_config(page_title="Wages & Pay Gap", layout="wide")
st.title("Wages & Pay Gap")
st.caption("Owner: Kripa S D |Salaries.csv | Explore salaries by gender, education, job title, and experience.")

ASSETS = Path(__file__).parent.parent / "assets"

for image_name in ["logo.png", "wages_banner.jpg"]:
    image_path = ASSETS / image_name
    if image_path.exists():
        st.image(str(image_path), width=150 if image_name == "logo.png" else None)

try:
    manager = SalaryManager()
except DataFileError as error:
    st.error(str(error))
    st.stop()

for warning in manager.warnings:
    st.warning(warning)

data = manager.data

if data.empty:
    st.info("No records found. You can add a record in the Add tab.")
    min_salary, max_salary = 0, 250000
else:
    min_salary = int(data["salary"].min())
    max_salary = int(data["salary"].max())
if min_salary == max_salary:
    max_salary = min_salary + 1
st.sidebar.header("Filters")

if st.sidebar.button("Reset filters"):
    st.session_state["gender_filter"] = []
    st.session_state["education_filter"] = []
    st.session_state["job_search"] = ""
    st.session_state["salary_filter"] = (min_salary, max_salary)
    st.session_state["sort_filter"] = "record_id"
    st.session_state["order_filter"] = "Ascending"

genders = st.sidebar.multiselect(
    "Gender", manager.GENDERS, key="gender_filter"
)
educations = st.sidebar.multiselect(
    "Education", manager.EDUCATION, key="education_filter"
)
job_search = st.sidebar.text_input(
    "Search job title", key="job_search",
    placeholder="Example: software"
)
salary_range = st.sidebar.slider(
    "Salary range", min_salary, max_salary,
    (min_salary, max_salary), key="salary_filter"
)
sort_by = st.sidebar.selectbox(
    "Sort by",
    ["record_id", "salary", "age", "experience_years", "job_title"],
    key="sort_filter"
)
sort_order = st.sidebar.radio(
    "Order", ["Ascending", "Descending"], key="order_filter"
)
filtered = manager.get_records(
    genders,
    educations,
    "",
    salary_range,
    sort_by,
    sort_order == "Ascending"
)
if job_search.strip():
    filtered = filtered[
        filtered["job_title"].astype(str).str.contains(
            job_search.strip(), case=False, na=False, regex=False
        )
    ]

view_tab, add_tab, edit_tab, delete_tab, charts_tab, compare_tab, report_tab = st.tabs(
    ["View", "Add", "Edit", "Delete", "Charts", "Compare", "Report"]
)

with view_tab:
    st.subheader("Workforce overview")

    col1, col2, col3 = st.columns(3)
    col1.metric("Total employees", len(filtered))

    if "experience_years" in filtered.columns and not filtered.empty:
        average_experience = filtered["experience_years"].dropna().mean()
        col2.metric("Average experience", f"{average_experience:.1f} years")
    else:
        col2.metric("Average experience", "N/A")

    if "salary" in filtered.columns and not filtered["salary"].dropna().empty:
        col3.metric("Highest salary", f"{filtered['salary'].max():,.0f}")
    else:
        col3.metric("Highest salary", "N/A")
    stats = manager.summary_stats(filtered)
    if "average_salary" in stats:
        st.subheader("Salary summary")
        a, b, c = st.columns(3)
        a.metric("Average salary", f"{stats['average_salary']:,.0f}")
        b.metric("Median salary", f"{stats['median_salary']:,.0f}")

        if "gender_pay_gap_percent" in stats:
            c.metric("Gender pay gap", f"{stats['gender_pay_gap_percent']}%")
        else:
            c.metric("Gender pay gap", "Not available")

        if "average_by_gender" in stats:
            st.write("Average salary by gender")
            for gender, average in stats["average_by_gender"].items():
                st.write(f"- Average {gender.lower()} salary: {average:,.0f}")

    st.subheader("Employee records")
    st.dataframe(filtered, use_container_width=True, hide_index=True)
with add_tab:
    st.subheader("Add a new employee")

    with st.form("add_employee_form"):
        age = st.number_input("Age", min_value=18, max_value=70, value=30)
        gender = st.selectbox("Gender", manager.GENDERS)
        education = st.selectbox("Education", manager.EDUCATION)
        job_title = st.text_input("Job title")
        experience = st.number_input(
            "Years of experience", min_value=0, max_value=50, value=5
        )
        salary = st.number_input("Salary", min_value=0.0, value=60000.0)

        add_clicked = st.form_submit_button("Add employee")

    if add_clicked:
        try:
            new_id = manager.add_record(
                age, gender, education, job_title, experience, salary
            )
            st.success(f"Employee record {new_id} added.")
            st.rerun()
        except (ValueError, DataFileError) as error:
            st.error(str(error))

with edit_tab:
    st.subheader("Edit an employee")

    edit_id = st.number_input("Record ID to edit", min_value=1, step=1)
    record = manager.get_record(int(edit_id))

    if record is None:
        st.info("Enter an existing record ID to edit.")
    else:
        st.write(f"Current job title: {record['job_title']}")

        with st.form("edit_employee_form"):
            age = st.number_input(
                "Age", min_value=18, max_value=70, value=int(record["age"])
            )
            education_index = (
                manager.EDUCATION.index(record["education"])
                if record["education"] in manager.EDUCATION else 0
            )
            education = st.selectbox(
                "Education", manager.EDUCATION, index=education_index
            )
            job_title = st.text_input("Job title", value=str(record["job_title"]))
            experience = st.number_input(
                "Years of experience", min_value=0, max_value=50,
                value=int(record["experience_years"])
            )
            salary = st.number_input(
                "Salary", min_value=0.0, value=float(record["salary"])
            )
            save_clicked = st.form_submit_button("Save changes")

        if save_clicked:
            try:
                manager.update_record(
                    int(edit_id), age, education, job_title, experience, salary
                )
                st.success("Record updated.")
                st.rerun()
            except (ValueError, DataFileError) as error:
                st.error(str(error))

with delete_tab:
    st.subheader("Delete an employee")

    delete_id = st.number_input("Record ID to delete", min_value=1, step=1)
    record = manager.get_record(int(delete_id))

    if record is None:
        st.info("Enter an existing record ID to delete.")
    else:
        st.write(
            f"{record['job_title']} | {record['gender']} | "
            f"Salary: {record['salary']:,.0f}"
        )
        confirm_delete = st.checkbox("I want to delete this record")

        if st.button("Delete employee", disabled=not confirm_delete):
            try:
                manager.delete_record(int(delete_id))
                st.success("Record deleted.")
                st.rerun()
            except (ValueError, DataFileError) as error:
                st.error(str(error))

with compare_tab:
    st.subheader("Compare two job profiles")

    job_titles = sorted(data["job_title"].dropna().astype(str).unique())

    if not job_titles:
        st.info("There are no job titles to compare.")
    else:
        left, right = st.columns(2)

        job_a = left.selectbox("Job title A", job_titles, key="job_a")
        education_a = left.selectbox(
            "Education A", ["All education"] + list(manager.EDUCATION),
            key="education_a"
        )

        job_b = right.selectbox("Job title B", job_titles, key="job_b")
        education_b = right.selectbox(
            "Education B", ["All education"] + list(manager.EDUCATION),
            key="education_b"
        )

        profile_a = data[
            data["job_title"].astype(str).str.strip().str.lower()
            == job_a.strip().lower()
        ]
        profile_b = data[
            data["job_title"].astype(str).str.strip().str.lower()
            == job_b.strip().lower()
        ]

        if education_a != "All education":
            profile_a = profile_a[profile_a["education"] == education_a]
        if education_b != "All education":
            profile_b = profile_b[profile_b["education"] == education_b]

        profile_a = profile_a.dropna(subset=["salary"])
        profile_b = profile_b.dropna(subset=["salary"])

        result_a, result_b = st.columns(2)
        result_a.markdown(f"**A: {job_a}**")
        result_a.write(f"Education: {education_a}")
        result_a.metric("Employees", len(profile_a))
        result_a.metric(
            "Average salary",
            f"{profile_a['salary'].mean():,.0f}" if not profile_a.empty else "N/A"
        )

        result_b.markdown(f"**B: {job_b}**")
        result_b.write(f"Education: {education_b}")
        result_b.metric("Employees", len(profile_b))
        result_b.metric(
            "Average salary",
            f"{profile_b['salary'].mean():,.0f}" if not profile_b.empty else "N/A"
        )

        if not profile_a.empty or not profile_b.empty:
            comparison = pd.DataFrame({
                "Profile": [f"A: {job_a}", f"B: {job_b}"],
                "Average salary": [
                    profile_a["salary"].mean() if not profile_a.empty else 0,
                    profile_b["salary"].mean() if not profile_b.empty else 0
                ]
            })
            chart = px.bar(
                comparison, x="Profile", y="Average salary",
                title="Average salary comparison"
            )
            st.plotly_chart(chart, use_container_width=True)

with charts_tab:
    chart_data = filtered.dropna(subset=["salary"])

    if chart_data.empty:
        st.info("No salary data available for the selected filters.")
    else:
        average_salary = chart_data.groupby(
            ["education", "gender"], as_index=False
        )["salary"].mean()

        st.plotly_chart(
            px.bar(
                average_salary, x="education", y="salary", color="gender",
                barmode="group", title="Average salary by education and gender"
            ),
            use_container_width=True
        )

        st.plotly_chart(
            px.scatter(
                chart_data, x="experience_years", y="salary", color="gender",
                title="Experience compared with salary"
            ),
            use_container_width=True
        )

        if "experience_band" in chart_data.columns:
            st.plotly_chart(
                px.box(
                    chart_data, x="experience_band", y="salary", color="gender",
                    title="Salary by experience group"
                ),
                use_container_width=True
            )

with report_tab:
    st.subheader("Salary report")
    st.write(f"Report created: {datetime.now():%d %b %Y, %H:%M}")
    st.write(f"Number of records: {len(filtered)}")

    report_data = filtered.dropna(subset=["salary"])

    if report_data.empty:
        st.info("No records match the current filters.")
    else:
        c1, c2, c3 = st.columns(3)
        c1.metric("Average salary", f"{report_data['salary'].mean():,.0f}")
        c2.metric("Median salary", f"{report_data['salary'].median():,.0f}")
        c3.metric("Highest salary", f"{report_data['salary'].max():,.0f}")

        st.subheader("Salary summary by education and gender")
        summary = report_data.groupby(["education", "gender"])["salary"].agg(
            ["count", "mean", "median", "min", "max"]
        ).round(0)
        st.dataframe(summary, use_container_width=True)

        st.subheader("Top 5 highest-paid employees")
        st.dataframe(
            report_data.nlargest(5, "salary")[
                ["job_title", "gender", "education", "experience_years", "salary"]
            ],
            use_container_width=True,
            hide_index=True
        )

    st.download_button(
        "Download filtered data (CSV)",
        filtered.to_csv(index=False),
        file_name="filtered_salaries.csv",
        mime="text/csv"
    )
