"""Member 3: SalaryManager.

All Create / Read / Update / Delete logic for data/salaries.csv lives here.
It extends the team's CSVManager, so loading and saving are already safe.

Every method RETURNS a value. Problems are reported by raising ValueError with a
plain-English message, which the page shows to the user.
"""
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from utils.csv_manager import CSVManager, DataFileError

DATA_FILE = Path(__file__).parent.parent / "data" / "salaries.csv"


class SalaryManager(CSVManager):
    REQUIRED = ["record_id", "age", "gender", "education", "job_title",
                "experience_years", "salary"]
    NUMERIC = ["age", "experience_years", "salary"]
    GENDERS = ["Male", "Female", "Other"]
    EDUCATION = ["High School", "Bachelor's", "Master's", "PhD"]

    def __init__(self, csv_path=DATA_FILE):
        super().__init__(csv_path, self.REQUIRED, self.NUMERIC)

    # ------------------------------------------------------------------ READ
    def get_records(self, genders=None, educations=None, search="", salary_range=None,
                    sort_by="record_id", ascending=True) -> pd.DataFrame:
        """Return the rows that match the filters, sorted by one column."""
        df = self.data
        if genders:
            df = df[df["gender"].isin(genders)]
        if educations:
            df = df[df["education"].isin(educations)]
        if search:
            df = df[df["job_title"].str.lower().str.contains(search.lower(), na=False, regex=False)]
        if salary_range:
            df = df[df["salary"].between(salary_range[0], salary_range[1])]
        if sort_by in df.columns:
            df = df.sort_values(sort_by, ascending=ascending)
        return df

    def get_record(self, record_id):
        """Return one row as a dict, or None if the ID does not exist."""
        match = self._data[self._data["record_id"] == record_id]
        return None if match.empty else match.iloc[0].to_dict()

    def summary_stats(self, df: pd.DataFrame) -> dict:
        """Statistics for the rows given. Rows with a missing salary are EXCLUDED."""
        clean = df.dropna(subset=["salary"])
        stats = {"rows": len(df), "excluded_missing": len(df) - len(clean)}
        if clean.empty:
            return stats
        by_gender = clean.groupby("gender")["salary"].mean()                  # group-by
        stats["average_salary"] = round(float(np.mean(clean["salary"])), 0)
        stats["median_salary"] = round(float(np.median(clean["salary"])), 0)
        stats["average_by_gender"] = {k: round(float(v), 0) for k, v in by_gender.items()}
        if {"Male", "Female"} <= set(by_gender.index):
            gap = (by_gender["Male"] - by_gender["Female"]) / by_gender["Male"] * 100
            stats["gender_pay_gap_percent"] = round(float(gap), 1)
        if len(clean) > 2 and clean["experience_years"].nunique() > 1:
            stats["experience_salary_correlation"] = round(
                float(np.corrcoef(clean["experience_years"], clean["salary"])[0, 1]), 2)
        return stats

    # ---------------------------------------------------------------- CREATE
    def add_record(self, age, gender, education, job_title, experience_years, salary) -> int:
        """Validate, check for duplicates, append, save. Returns the new record_id."""
        job_title = str(job_title).strip()
        self._check(age, gender, education, job_title, experience_years, salary)

        duplicate = ((self._data["age"] == int(age)) & (self._data["gender"] == gender)
                     & (self._data["education"] == education)
                     & (self._data["job_title"].str.lower() == job_title.lower())
                     & (self._data["experience_years"] == int(experience_years))
                     & (self._data["salary"] == float(salary)))
        if duplicate.any():
            raise ValueError("An identical record already exists.")

        new_id = int(self._data["record_id"].max()) + 1 if len(self._data) else 1
        row = {"record_id": new_id, "age": int(age), "gender": gender, "education": education,
               "job_title": job_title, "experience_years": int(experience_years),
               "salary": float(salary), "experience_band": self._band(experience_years)}
        return self._commit(pd.concat(
            [self._data, pd.DataFrame([row]).reindex(columns=self._data.columns)],
            ignore_index=True), new_id)

    # ---------------------------------------------------------------- UPDATE
    def update_record(self, record_id, age, education, job_title, experience_years, salary) -> dict:
        """Change age, education, job title, experience and salary. Returns the new row."""
        idx = self._index_of(record_id)
        job_title = str(job_title).strip()
        self._check(age, self._data.at[idx, "gender"], education, job_title,
                    experience_years, salary)
        updated = self._data.copy()
        updated.at[idx, "age"] = int(age)
        updated.at[idx, "education"] = education
        updated.at[idx, "job_title"] = job_title
        updated.at[idx, "experience_years"] = int(experience_years)
        updated.at[idx, "salary"] = float(salary)
        updated.at[idx, "experience_band"] = self._band(experience_years)
        self._commit(updated, record_id)
        return self.get_record(record_id)

    # ---------------------------------------------------------------- DELETE
    def delete_record(self, record_id) -> dict:
        """Remove a record and rewrite the CSV. Returns the row that was removed."""
        idx = self._index_of(record_id)
        removed = self._data.loc[idx].to_dict()
        self._commit(self._data.drop(index=idx).reset_index(drop=True), record_id)
        return removed

    # ---------------------------------------------------------------- REPORT
    def build_report(self, df: pd.DataFrame, filters: dict) -> str:
        """A plain-text report: timestamp, row count, filters applied, statistics."""
        lines = ["SALARY REPORT",
                 f"Generated: {datetime.now():%Y-%m-%d %H:%M:%S}",
                 f"Rows in report: {len(df)}", "", "Filters applied:"]
        lines += [f"  {k}: {v}" for k, v in filters.items()]
        lines += ["", "Statistics (rows with a missing salary are excluded):"]
        for key, value in self.summary_stats(df).items():
            lines.append(f"  {key.replace('_', ' ')}: {value}")
        return "\n".join(lines)

    # --------------------------------------------------------------- helpers
    def _check(self, age, gender, education, job_title, experience_years, salary):
        if not job_title:
            raise ValueError("Job title is required.")
        if gender not in self.GENDERS:
            raise ValueError("Gender must be Male, Female or Other.")
        if education not in self.EDUCATION:
            raise ValueError("Please choose a valid education level.")
        try:
            age, experience_years, salary = int(age), int(experience_years), float(salary)
        except (TypeError, ValueError):
            raise ValueError("Age, experience and salary must be numbers.")
        if not 18 <= age <= 70:
            raise ValueError("Age must be between 18 and 70.")
        if experience_years < 0 or experience_years > age - 16:
            raise ValueError("Experience cannot be negative or start before age 16.")
        if not 1000 <= salary <= 1_000_000:
            raise ValueError("Salary must be between 1,000 and 1,000,000.")

    @staticmethod
    def _band(years) -> str:
        years = int(years)
        for limit, label in [(2, "0-2 yrs"), (5, "3-5 yrs"), (10, "6-10 yrs"), (20, "11-20 yrs")]:
            if years <= limit:
                return label
        return "20+ yrs"

    def _index_of(self, record_id):
        try:
            record_id = int(record_id)
        except (TypeError, ValueError):
            raise ValueError("Record ID must be a whole number.")
        match = self._data.index[self._data["record_id"] == record_id]
        if len(match) == 0:
            raise ValueError(f"No record with ID {record_id} exists.")
        return match[0]

    def _commit(self, new_table: pd.DataFrame, result):
        """Swap in the new table and save; put the old one back if saving fails."""
        old = self._data
        self._data = new_table
        try:
            self._save()
        except DataFileError:
            self._data = old
            raise
        return result
