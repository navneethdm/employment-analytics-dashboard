from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from utils.csv_manager import CSVManager, DataFileError

DATA_FILE = Path(__file__).parent.parent / "data" / "jobs.csv"

# Words we look for inside the (separator-less) skills text.
SKILL_WORDS = ["python", "sql", "machine learning", "deep learning", "data analysis",
               "statistics", "tableau", "power bi", "excel", "sas", "spark", "hadoop",
               "aws", "azure", "nlp", "tensorflow", "java", "big data", "data visualization"]

# First matching rule wins, so order matters.
ROLE_RULES = [("Data Scientist", ["data scien"]),
              ("Machine Learning / AI", ["machine learning", "ml ", " ai ", "artificial intel", "deep learning", "nlp"]),
              ("Data Engineer", ["data engineer", "etl", "big data", "hadoop", "spark"]),
              ("Data Analyst", ["data analy", "analytics", "analyst"]),
              ("Business Analyst", ["business analy", "business intelligence"]),
              ("Manager / Lead", ["manager", "lead", "head", "director", "principal"])]


class JobsManager(CSVManager):
    REQUIRED = ["record_id", "job_title", "company", "location", "skills", "exp_min", "exp_max"]
    NUMERIC = ["exp_min", "exp_max", "exp_mid", "salary_min_lpa", "salary_max_lpa",
               "salary_mid_lpa", "n_locations", "posted_days_ago"]

    def __init__(self, csv_path=DATA_FILE):
        super().__init__(csv_path, self.REQUIRED, self.NUMERIC)

    # ------------------------------------------------------------------ READ
    def get_records(self, roles=None, cities=None, search="", exp_range=None,
                    salary_only=False, sort_by="record_id", ascending=True) -> pd.DataFrame:
        """Return the rows that match the filters, sorted by one column."""
        df = self.data
        if roles:
            df = df[df["role_category"].isin(roles)]
        if cities:
            df = df[df["city"].isin(cities)]
        if search:
            text = search.lower()
            df = df[df["job_title"].str.lower().str.contains(text, na=False, regex=False)
                    | df["company"].str.lower().str.contains(text, na=False, regex=False)]
        if exp_range:
            df = df[df["exp_mid"].between(exp_range[0], exp_range[1])]
        if salary_only:
            df = df[df["salary_mid_lpa"].notna()]
        if sort_by in df.columns:
            df = df.sort_values(sort_by, ascending=ascending)
        return df

    def get_record(self, record_id):
        """Return one row as a dict, or None if the ID does not exist."""
        match = self._data[self._data["record_id"] == record_id]
        return None if match.empty else match.iloc[0].to_dict()

    def summary_stats(self, df: pd.DataFrame) -> dict:
        """Statistics for the rows given. Missing salaries are EXCLUDED from salary figures."""
        stats = {"job_postings": len(df)}
        if df.empty:
            return stats
        with_pay = df.dropna(subset=["salary_mid_lpa"])
        stats["postings_with_salary"] = len(with_pay)
        stats["postings_without_salary_excluded"] = len(df) - len(with_pay)
        stats["average_experience_years"] = round(float(np.nanmean(df["exp_mid"])), 1)
        if not with_pay.empty:
            stats["median_salary_lakh_per_year"] = round(float(np.median(with_pay["salary_mid_lpa"])), 1)
        stats["top_city"] = df["city"].value_counts().idxmax()
        stats["top_role"] = df["role_category"].value_counts().idxmax()
        return stats

    def city_counts(self, df: pd.DataFrame, top=10) -> pd.DataFrame:
        counts = df["city"].value_counts().head(top).rename_axis("city").reset_index(name="postings")
        return counts

    def skill_counts(self, df: pd.DataFrame, top=12) -> pd.DataFrame:
        """How many postings mention each skill word (a posting counts once per skill)."""
        text = df["skills"].fillna("").str.lower()
        rows = [(word.upper() if len(word) <= 3 else word.title(), int(text.str.contains(word, regex=False).sum()))
                for word in SKILL_WORDS]
        result = pd.DataFrame(rows, columns=["skill", "postings"])
        return result.sort_values("postings", ascending=False).head(top)

    # ---------------------------------------------------------------- CREATE
    def add_record(self, job_title, company, exp_min, exp_max, location, skills="",
                   salary_min=None, salary_max=None) -> int:
        """Validate, check for duplicates, append, save. Returns the new record_id."""
        job_title, company, location = (str(x).strip() for x in (job_title, company, location))
        self._check(job_title, company, location, exp_min, exp_max, salary_min, salary_max)

        duplicate = ((self._data["job_title"].str.lower() == job_title.lower())
                     & (self._data["company"].str.lower() == company.lower())
                     & (self._data["location"].str.lower() == location.lower()))
        if duplicate.any():
            raise ValueError("This job (same title, company and location) already exists.")

        new_id = int(self._data["record_id"].max()) + 1 if len(self._data) else 1
        row = {"record_id": new_id, "job_title": job_title, "company": company,
               "skills": str(skills).strip(), "posted_days_ago": np.nan,
               "is_unpaid": False}
        row.update(self._derived(job_title, location, exp_min, exp_max, salary_min, salary_max))
        return self._commit(pd.concat(
            [self._data, pd.DataFrame([row]).reindex(columns=self._data.columns)],
            ignore_index=True), new_id)

    # ---------------------------------------------------------------- UPDATE
    def update_record(self, record_id, location, skills, exp_min, exp_max,
                      salary_min=None, salary_max=None) -> dict:
        """Change location, skills, experience and salary range. Returns the new row."""
        idx = self._index_of(record_id)
        title = self._data.at[idx, "job_title"]
        location = str(location).strip()
        self._check(title, self._data.at[idx, "company"], location,
                    exp_min, exp_max, salary_min, salary_max)
        updated = self._data.copy()
        updated.at[idx, "skills"] = str(skills).strip()
        for column, value in self._derived(title, location, exp_min, exp_max,
                                           salary_min, salary_max).items():
            updated.at[idx, column] = value
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
        lines = ["JOB MARKET REPORT",
                 f"Generated: {datetime.now():%Y-%m-%d %H:%M:%S}",
                 f"Rows in report: {len(df)}", "", "Filters applied:"]
        lines += [f"  {k}: {v}" for k, v in filters.items()]
        lines += ["", "Statistics (postings without a salary are excluded from salary figures):"]
        for key, value in self.summary_stats(df).items():
            lines.append(f"  {key.replace('_', ' ')}: {value}")
        return "\n".join(lines)

    # --------------------------------------------------------------- helpers
    def _check(self, title, company, location, exp_min, exp_max, salary_min, salary_max):
        if not title:
            raise ValueError("Job title is required.")
        if not company:
            raise ValueError("Company is required.")
        if not location:
            raise ValueError("Location is required.")
        try:
            exp_min, exp_max = float(exp_min), float(exp_max)
        except (TypeError, ValueError):
            raise ValueError("Experience must be numbers.")
        if exp_min < 0 or exp_max < exp_min:
            raise ValueError("Experience must be 0 or more, and the maximum cannot be below the minimum.")
        if salary_min or salary_max:                       # salary is optional, but must be a full range
            if not (salary_min and salary_max):
                raise ValueError("Enter both a minimum and a maximum salary, or leave both empty.")
            if float(salary_max) < float(salary_min):
                raise ValueError("Maximum salary cannot be below the minimum.")

    def _derived(self, title, location, exp_min, exp_max, salary_min, salary_max) -> dict:
        """Recompute every column that is calculated from the ones the user typed."""
        low_title = f" {title.lower()} "
        role = next((name for name, words in ROLE_RULES if any(w in low_title for w in words)), "Other")
        has_pay = bool(salary_min and salary_max)
        return {
            "location": location,
            "city": location.replace("/", ",").split(",")[0].strip().title(),
            "n_locations": location.count(",") + 1,
            "role_category": role,
            "experience": f"{int(exp_min)}-{int(exp_max)} Yrs",
            "exp_min": float(exp_min), "exp_max": float(exp_max),
            "exp_mid": (float(exp_min) + float(exp_max)) / 2,
            "package": f"{salary_min}-{salary_max} Lacs PA" if has_pay else "Not disclosed",
            "salary_min_lpa": float(salary_min) if has_pay else np.nan,
            "salary_max_lpa": float(salary_max) if has_pay else np.nan,
            "salary_mid_lpa": (float(salary_min) + float(salary_max)) / 2 if has_pay else np.nan,
            "salary_disclosed": has_pay,
        }

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
