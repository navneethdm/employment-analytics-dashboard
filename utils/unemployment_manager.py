"""Member 1: UnemploymentManager.

All Create / Read / Update / Delete logic for data/unemployment.csv lives here.
It extends the team's CSVManager, so loading and saving are already safe; this class
adds the rules that are specific to unemployment data.

Every method RETURNS a value (a table, a dict, a new ID, ...). Problems are reported
by raising ValueError with a plain-English message, which the page shows to the user.
"""
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from utils.csv_manager import CSVManager, DataFileError

DATA_FILE = Path(__file__).parent.parent / "data" / "unemployment.csv"


class UnemploymentManager(CSVManager):
    REQUIRED = ["record_id", "state", "date", "unemployment_rate", "employed",
                "labour_participation_rate", "area"]
    NUMERIC = ["unemployment_rate", "employed", "labour_participation_rate", "year", "month"]
    AREAS = ["Rural", "Urban"]

    def __init__(self, csv_path=DATA_FILE):
        super().__init__(csv_path, self.REQUIRED, self.NUMERIC)

    # ------------------------------------------------------------------ READ
    def get_records(self, states=None, area="All", zone="All", phase="All",
                    sort_by="date", ascending=True) -> pd.DataFrame:
        """Return the rows that match the filters, sorted by one column."""
        df = self.data
        if states:
            df = df[df["state"].isin(states)]
        if area != "All":
            df = df[df["area"] == area]
        if zone != "All":
            df = df[df["zone"] == zone]
        if phase != "All":
            df = df[df["covid_phase"] == phase]
        if sort_by in df.columns:
            df = df.sort_values(sort_by, ascending=ascending)
        return df

    def get_record(self, record_id):
        """Return one row as a dict, or None if the ID does not exist."""
        match = self._data[self._data["record_id"] == record_id]
        return None if match.empty else match.iloc[0].to_dict()

    def summary_stats(self, df: pd.DataFrame) -> dict:
        """Statistics for the rows given. Rows with a missing rate are EXCLUDED."""
        clean = df.dropna(subset=["unemployment_rate"])
        stats = {"rows": len(df), "excluded_missing": len(df) - len(clean)}
        if clean.empty:
            return stats
        by_state = clean.groupby("state")["unemployment_rate"].mean()      # group-by
        by_area = clean.groupby("area")["unemployment_rate"].mean()
        stats.update({
            "average_rate": round(float(np.mean(clean["unemployment_rate"])), 2),
            "median_rate": round(float(np.median(clean["unemployment_rate"])), 2),
            "highest_state": by_state.idxmax(),
            "highest_state_rate": round(float(by_state.max()), 2),
            "lowest_state": by_state.idxmin(),
            "lowest_state_rate": round(float(by_state.min()), 2),
            "by_area": {k: round(float(v), 2) for k, v in by_area.items()},
        })
        return stats

    # ---------------------------------------------------------------- CREATE
    def add_record(self, state, date, area, rate, employed, participation) -> int:
        """Validate, check for duplicates, append, save. Returns the new record_id."""
        state = str(state).strip()
        self._check(state, area, rate, employed, participation)
        when = pd.Timestamp(date)

        duplicate = (
            (self._data["state"].str.lower() == state.lower())
            & (self._data["date"] == when.strftime("%Y-%m-%d"))
            & (self._data["area"] == area)
        )
        if duplicate.any():
            raise ValueError(f"A record for {state} ({area}) on {when:%d %b %Y} already exists.")

        # zone and map coordinates are copied from an existing row for the same state
        same_state = self._data[self._data["state"].str.lower() == state.lower()]
        zone, lat, lon = (same_state.iloc[0][["zone", "latitude", "longitude"]]
                          if not same_state.empty else (np.nan, np.nan, np.nan))
        new_id = int(self._data["record_id"].max()) + 1 if len(self._data) else 1
        row = {
            "record_id": new_id, "state": state, "date": when.strftime("%Y-%m-%d"),
            "frequency": "Monthly", "unemployment_rate": float(rate),
            "employed": float(employed), "labour_participation_rate": float(participation),
            "area": area, "year": when.year, "month": when.month,
            "period": when.strftime("%Y-%m"),
            "covid_phase": "During/after lockdown" if when >= pd.Timestamp("2020-04-01")
                           else "Before lockdown",
            "zone": zone, "latitude": lat, "longitude": lon,
        }
        return self._commit(pd.concat(
            [self._data, pd.DataFrame([row]).reindex(columns=self._data.columns)],
            ignore_index=True), new_id)

    # ---------------------------------------------------------------- UPDATE
    def update_record(self, record_id, rate, employed, participation) -> dict:
        """Change the three numeric fields of an existing record. Returns the new row."""
        idx = self._index_of(record_id)
        self._check(self._data.at[idx, "state"], self._data.at[idx, "area"],
                    rate, employed, participation)
        updated = self._data.copy()
        updated.at[idx, "unemployment_rate"] = float(rate)
        updated.at[idx, "employed"] = float(employed)
        updated.at[idx, "labour_participation_rate"] = float(participation)
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
        stats = self.summary_stats(df)
        lines = ["UNEMPLOYMENT REPORT",
                 f"Generated: {datetime.now():%Y-%m-%d %H:%M:%S}",
                 f"Rows in report: {len(df)}", "", "Filters applied:"]
        lines += [f"  {k}: {v}" for k, v in filters.items()]
        lines += ["", "Statistics (rows with a missing rate are excluded):"]
        for key, value in stats.items():
            lines.append(f"  {key.replace('_', ' ')}: {value}")
        return "\n".join(lines)

    # --------------------------------------------------------------- helpers
    def _check(self, state, area, rate, employed, participation):
        if not str(state).strip():
            raise ValueError("State is required.")
        if area not in self.AREAS:
            raise ValueError("Area must be Rural or Urban.")
        for label, value, low, high in [("Unemployment rate", rate, 0, 100),
                                        ("Labour participation rate", participation, 0, 100),
                                        ("Employed", employed, 0, float("inf"))]:
            try:
                number = float(value)
            except (TypeError, ValueError):
                raise ValueError(f"{label} must be a number.")
            if not (low <= number <= high):
                raise ValueError(f"{label} must be between {low} and {high}.")

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
