"""Member 3: cleaning for Salary_Data.csv (age, gender, education, job title, experience, salary)."""
from pathlib import Path

import pandas as pd

DATA = Path(__file__).parent.parent / "raw_data"

EDU_FIX = {
    "bachelor's degree": "Bachelor's",
    "bachelor's": "Bachelor's",
    "master's degree": "Master's",
    "master's": "Master's",
    "phd": "PhD",
    "high school": "High School",
}


def clean() -> pd.DataFrame:
    df = pd.read_csv(DATA / "Salary_Data.csv")
    df = df.rename(columns={
        "Age": "age", "Gender": "gender", "Education Level": "education",
        "Job Title": "job_title", "Years of Experience": "experience_years",
        "Salary": "salary",
    })
    df = df.dropna()                                  
    df["education"] = df["education"].str.strip().str.lower().map(EDU_FIX)
    df["gender"] = df["gender"].str.strip().str.title()
    df["job_title"] = df["job_title"].str.strip()
    df = df.drop_duplicates()
    df = df[df["salary"] >= 1000]                      
    df["age"] = df["age"].astype(int)
    df["experience_years"] = df["experience_years"].astype(int)
    df["salary"] = df["salary"].astype(float)
    df["experience_band"] = pd.cut(
        df["experience_years"], bins=[-1, 2, 5, 10, 20, 100],
        labels=["0-2 yrs", "3-5 yrs", "6-10 yrs", "11-20 yrs", "20+ yrs"])
    df["experience_band"] = df["experience_band"].astype(str)
    return df.reset_index(drop=True)


if __name__ == "__main__":
    out = clean()
    print(out.shape)
    print(out.groupby("gender").salary.mean())
