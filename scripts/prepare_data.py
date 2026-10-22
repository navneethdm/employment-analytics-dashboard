"""One-time data preparation: turns the raw downloads into the four clean CSVs the app uses.

Run from the project root:
    python scripts/prepare_data.py
On Windows, if `python` is not found:  py -3.11 scripts/prepare_data.py

Input : raw_data/   (the original files downloaded from Kaggle / World Bank)
Output: data/       (one clean CSV per team member; these ARE committed to GitHub)

The app itself never touches raw_data/. It only reads and writes the files in data/.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from utils import clean_inclusion, clean_jobs, clean_salary, clean_unemployment

OUT = ROOT / "data"


def _write(df, filename):
    df = df.copy()
    df.insert(0, "record_id", range(1, len(df) + 1))    # every row gets a unique ID for Update/Delete
    df.to_csv(OUT / filename, index=False)
    print(f"  {filename:28s} {len(df):>7,} rows")


def main():
    OUT.mkdir(exist_ok=True)
    print("Writing clean CSVs to data/ ...")
    _write(clean_unemployment.clean(), "unemployment.csv")           # Member 1
    jobs, _skills = clean_jobs.clean()
    _write(jobs.drop(columns=["job_id", "source_file"]), "jobs.csv")  # Member 2
    _write(clean_salary.clean(), "salaries.csv")                     # Member 3
    _write(clean_inclusion.clean(), "labour_participation.csv")      # Member 4
    print("Done.")


if __name__ == "__main__":
    main()
