"""Member 4: InclusionManager.

All Create / Read / Update / Delete logic for data/labour_participation.csv lives here
(female labour force participation rate by country and year, World Bank / ILO).
It extends the team's CSVManager, so loading and saving are already safe.

Every method RETURNS a value. Problems are reported by raising ValueError with a
plain-English message, which the page shows to the user.
"""
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from utils.csv_manager import CSVManager, DataFileError

DATA_FILE = Path(__file__).parent.parent / "data" / "labour_participation.csv"


class InclusionManager(CSVManager):
    REQUIRED = ["record_id", "country", "country_code", "year", "female_participation_rate"]
    NUMERIC = ["year", "female_participation_rate"]

    def __init__(self, csv_path=DATA_FILE):
        super().__init__(csv_path, self.REQUIRED, self.NUMERIC)

    # ------------------------------------------------------------------ READ
    def get_records(self, countries=None, region="All", income="All", year_range=None,
                    countries_only=True, sort_by="country", ascending=True) -> pd.DataFrame:
        """Return the rows that match the filters, sorted by one column.

        The raw World Bank file mixes real countries with groups such as 'World' or
        'Arab World'. `countries_only` hides those groups.
        """
        df = self.data
        if countries_only:
            df = df[df["is_country"].astype(str) == "True"]
        if countries:
            df = df[df["country"].isin(countries)]
        if region != "All":
            df = df[df["region"] == region]
        if income != "All":
            df = df[df["income_group"] == income]
        if year_range:
            df = df[df["year"].between(year_range[0], year_range[1])]
        if sort_by in df.columns:
            df = df.sort_values(sort_by, ascending=ascending)
        return df

    def get_record(self, record_id):
        """Return one row as a dict, or None if the ID does not exist."""
        match = self._data[self._data["record_id"] == record_id]
        return None if match.empty else match.iloc[0].to_dict()

    def summary_stats(self, df: pd.DataFrame) -> dict:
        """Statistics for the rows given. Rows with a missing rate are EXCLUDED."""
        clean = df.dropna(subset=["female_participation_rate"])
        stats = {"rows": len(df), "excluded_missing": len(df) - len(clean)}
        if clean.empty:
            return stats
        by_country = clean.groupby("country")["female_participation_rate"].mean()   # group-by
        by_region = clean.dropna(subset=["region"]).groupby("region")["female_participation_rate"].mean()
        stats.update({
            "average_rate": round(float(np.mean(clean["female_participation_rate"])), 1),
            "highest_country": by_country.idxmax(),
            "highest_country_rate": round(float(by_country.max()), 1),
            "lowest_country": by_country.idxmin(),
            "lowest_country_rate": round(float(by_country.min()), 1),
            "countries_covered": int(clean["country"].nunique()),
        })
        if not by_region.empty:
            stats["average_by_region"] = {k: round(float(v), 1) for k, v in by_region.items()}
        return stats

    def region_averages(self, df: pd.DataFrame) -> pd.DataFrame:
        """Average rate per region, for the bar chart."""
        clean = df.dropna(subset=["female_participation_rate", "region"])
        result = clean.groupby("region")["female_participation_rate"].mean().round(1)
        return result.rename("average_rate").reset_index().sort_values("average_rate")

    # ---------------------------------------------------------------- CREATE
    def add_record(self, country, country_code, year, rate, region="", income_group="") -> int:
        """Validate, check for duplicates, append, save. Returns the new record_id."""
        country = str(country).strip()
        country_code = str(country_code).strip().upper()
        self._check(country, country_code, year, rate)

        duplicate = ((self._data["country_code"] == country_code)
                     & (self._data["year"] == int(year)))
        if duplicate.any():
            raise ValueError(f"{country_code} already has a record for {int(year)}. Use Update instead.")

        new_id = int(self._data["record_id"].max()) + 1 if len(self._data) else 1
        region = str(region).strip() or np.nan
        row = {"record_id": new_id, "country": country, "country_code": country_code,
               "year": int(year), "female_participation_rate": float(rate),
               "region": region, "income_group": str(income_group).strip() or np.nan,
               "is_country": isinstance(region, str)}      # only real countries have a region
        return self._commit(pd.concat(
            [self._data, pd.DataFrame([row]).reindex(columns=self._data.columns)],
            ignore_index=True), new_id)

    # ---------------------------------------------------------------- UPDATE
    def update_record(self, record_id, rate, region="", income_group="") -> dict:
        """Change the rate, region and income group. Returns the new row."""
        idx = self._index_of(record_id)
        self._check(self._data.at[idx, "country"], self._data.at[idx, "country_code"],
                    self._data.at[idx, "year"], rate)
        updated = self._data.copy()
        updated.at[idx, "female_participation_rate"] = float(rate)
        updated.at[idx, "region"] = str(region).strip() or np.nan
        updated.at[idx, "income_group"] = str(income_group).strip() or np.nan
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
        lines = ["WORKFORCE INCLUSION REPORT",
                 f"Generated: {datetime.now():%Y-%m-%d %H:%M:%S}",
                 f"Rows in report: {len(df)}", "", "Filters applied:"]
        lines += [f"  {k}: {v}" for k, v in filters.items()]
        lines += ["", "Statistics (rows with a missing rate are excluded):"]
        for key, value in self.summary_stats(df).items():
            lines.append(f"  {key.replace('_', ' ')}: {value}")
        return "\n".join(lines)

    # --------------------------------------------------------------- helpers
    def _check(self, country, country_code, year, rate):
        if not str(country).strip():
            raise ValueError("Country is required.")
        if not (len(str(country_code)) == 3 and str(country_code).isalpha()):
            raise ValueError("Country code must be exactly 3 letters, like IND.")
        try:
            year, rate = int(year), float(rate)
        except (TypeError, ValueError):
            raise ValueError("Year must be a whole number and the rate must be a number.")
        if not 1960 <= year <= 2100:
            raise ValueError("Year must be between 1960 and 2100.")
        if not 0 <= rate <= 100:
            raise ValueError("Participation rate must be between 0 and 100.")

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
