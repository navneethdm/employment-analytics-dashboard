"""Member 4: cleaning for the World Bank female labour force participation file.

The raw file is 'wide' (one column per year) and starts with 4 junk header lines.
We reshape it to 'long' (one row per country per year) so it is easy to chart.
"""
from pathlib import Path

import pandas as pd

DATA = Path(__file__).parent.parent / "raw_data"


def _find(pattern: str) -> Path:
    matches = sorted(DATA.glob(pattern))
    if not matches:
        raise FileNotFoundError(f"No file matching {pattern!r} in {DATA}")
    return matches[0]


def clean() -> pd.DataFrame:
    wide = pd.read_csv(_find("API_SL.TLF.CACT.FE.ZS*.csv"), skiprows=4)
    wide = wide.drop(columns=["Indicator Name", "Indicator Code"], errors="ignore")
    wide = wide.loc[:, ~wide.columns.str.startswith("Unnamed")]

    long = wide.melt(id_vars=["Country Name", "Country Code"],
                     var_name="year", value_name="female_participation_rate")
    long = long.dropna(subset=["female_participation_rate"])
    long["year"] = long["year"].astype(int)
    long = long.rename(columns={"Country Name": "country", "Country Code": "country_code"})

    # The file mixes real countries with groups like 'World' or 'Arab World'.
    # The metadata file has a Region only for real countries, so we use it to tell them apart.
    meta = pd.read_csv(_find("Metadata_Country_API_SL.TLF.CACT.FE.ZS*.csv"))
    meta = meta.rename(columns={"Country Code": "country_code",
                                "Region": "region", "IncomeGroup": "income_group"})
    meta = meta[["country_code", "region", "income_group"]]
    long = long.merge(meta, on="country_code", how="left")
    long["is_country"] = long["region"].notna()
    return long.sort_values(["country", "year"]).reset_index(drop=True)


if __name__ == "__main__":
    out = clean()
    print(out.shape, out.is_country.sum())
    print(out[out.country == "India"].tail())
