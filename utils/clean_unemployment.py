"""Member 1: cleaning for the unemployment dataset.

Main file : Unemployment in India.csv  (state x month x Rural/Urban, May 2019 - Jun 2020)
Helper    : Unemployment_Rate_upto_11_2020.csv  (only used for zone + map coordinates)
"""
from pathlib import Path

import pandas as pd

DATA = Path(__file__).parent.parent / "raw_data"

# Chandigarh is missing from the helper file, so we add it by hand.
EXTRA_STATES = {"Chandigarh": ("North", 30.7333, 76.7794)}


def _load_state_info() -> pd.DataFrame:
    z = pd.read_csv(DATA / "Unemployment_Rate_upto_11_2020.csv")
    z.columns = z.columns.str.strip()
    z["Region"] = z["Region"].str.strip()
    # In this file the columns named 'longitude' and 'latitude' are swapped
    # (Andhra Pradesh shows longitude=15.9, which is really its latitude).
    info = (
        z[["Region", "Region.1", "longitude", "latitude"]]
        .drop_duplicates("Region")
        .rename(columns={"Region": "state", "Region.1": "zone",
                         "longitude": "latitude", "latitude": "longitude"})
    )
    extra = pd.DataFrame(
        [(s, *v) for s, v in EXTRA_STATES.items()],
        columns=["state", "zone", "latitude", "longitude"],
    )
    return pd.concat([info, extra], ignore_index=True)


def clean() -> pd.DataFrame:
    df = pd.read_csv(DATA / "Unemployment in India.csv")
    df.columns = df.columns.str.strip()
    df = df.rename(columns={
        "Region": "state",
        "Date": "date",
        "Frequency": "frequency",
        "Estimated Unemployment Rate (%)": "unemployment_rate",
        "Estimated Employed": "employed",
        "Estimated Labour Participation Rate (%)": "labour_participation_rate",
        "Area": "area",
    })
    df = df.dropna(how="all").dropna()            # 28 fully blank rows in the raw file
    for col in ["state", "frequency", "area"]:
        df[col] = df[col].str.strip()
    df["date"] = pd.to_datetime(df["date"].str.strip(), format="%d-%m-%Y")
    df["year"] = df["date"].dt.year
    df["month"] = df["date"].dt.month
    df["period"] = df["date"].dt.strftime("%Y-%m")
    # India's national lockdown began on 25 March 2020.
    df["covid_phase"] = (df["date"] >= "2020-04-01").map(
        {True: "During/after lockdown", False: "Before lockdown"})
    df = df.drop_duplicates()
    df = df.merge(_load_state_info(), on="state", how="left")
    df["date"] = df["date"].dt.strftime("%Y-%m-%d")   # SQLite stores dates as text
    return df.reset_index(drop=True)


if __name__ == "__main__":
    out = clean()
    print(out.shape)
    print(out.head())
