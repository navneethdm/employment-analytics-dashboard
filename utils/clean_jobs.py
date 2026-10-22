import re
from pathlib import Path

import pandas as pd

DATA = Path(__file__).parent.parent / "raw_data"

FILES = [
    "NaukriData_Data Science.csv",
    "NaukriData_data analytics.csv",
    "Naukri_Data_Scientist_and_Data_Analytics_Jobs_Data.csv",
]

RENAME = {
    "Job_Titles": "job_title", "Job Titles": "job_title",
    "Company_Names": "company", "Company Names": "company",
    "Experience_Required": "experience", "Experience Required": "experience",
    "Package_Details": "package", "Package": "package",
    "Locations": "location",
    "Skills": "skills",
    "Post_Time": "post_time",
}

# Naukri writes the same city in several ways.
CITY_FIX = {
    "bangalore/bengaluru": "Bengaluru", "bangalore": "Bengaluru", "bengaluru": "Bengaluru",
    "gurgaon/gurugram": "Gurugram", "gurgaon": "Gurugram", "gurugram": "Gurugram",
    "hyderabad/secunderabad": "Hyderabad", "hyderabad": "Hyderabad",
    "delhi / ncr": "Delhi NCR", "delhi/ncr": "Delhi NCR", "new delhi": "Delhi NCR", "delhi": "Delhi NCR",
    "noida": "Delhi NCR", "mumbai": "Mumbai", "mumbai suburbs": "Mumbai", "navi mumbai": "Mumbai",
    "pune": "Pune", "chennai": "Chennai", "kolkata": "Kolkata", "remote": "Remote",
}

# The Skills column has no separators ("Machine learningSQLPython"), so instead of
# splitting it we search for well-known skills inside the text.
SKILL_KEYWORDS = [
    "python", "sql", "machine learning", "deep learning", "data analysis", "data analytics",
    "data science", "statistics", "tableau", "power bi", "excel", "sas", "spark",
    "hadoop", "aws", "azure", "gcp", "nlp", "tensorflow", "pytorch", "java", "scala",
    "data visualization", "etl", "big data", "artificial intelligence", "data modeling",
    "forecasting", "project management", "communication",
]

ROLE_RULES = [
    ("Data Scientist", r"data scien"),
    ("Machine Learning / AI", r"machine learning|\bml\b|\bai\b|artificial intelligence|deep learning|nlp"),
    ("Data Engineer", r"data engineer|etl|big data|hadoop|spark"),
    ("Data Analyst", r"data analy|analytics|\banalyst\b"),
    ("Business Analyst", r"business analy|business intelligence|\bbi\b"),
    ("Manager / Lead", r"manager|lead|head|director|principal"),
]


def _city(loc):
    if pd.isna(loc):
        return None
    first = re.split(r",|;", str(loc))[0].strip().lower()
    return CITY_FIX.get(first, first.title())


def _role(title):
    t = str(title).lower()
    for name, pattern in ROLE_RULES:
        if re.search(pattern, t):
            return name
    return "Other"


def _post_days(text):
    if pd.isna(text):
        return None
    m = re.match(r"\s*(\d+)\+?\s*day", str(text), flags=re.I)
    return int(m.group(1)) if m else None      # 'Starts in 1-3 months' etc. -> blank


def clean():
    frames = []
    for name in FILES:
        df = pd.read_csv(DATA / name)
        df = df.rename(columns=RENAME)
        keep = list(dict.fromkeys(RENAME.values()))          # unique names, same order
        df = df[[c for c in keep if c in df.columns]]
        df["source_file"] = name
        frames.append(df)
    jobs = pd.concat(frames, ignore_index=True)

    for col in ["job_title", "company", "experience", "package", "location", "skills"]:
        jobs[col] = jobs[col].astype("string").str.strip()

    jobs = jobs.dropna(subset=["job_title"])                   # ~15k blank rows in the raw files
    jobs = jobs.drop_duplicates(subset=["job_title", "company", "experience", "location"])

    # Experience: '4-8 Yrs' -> 4, 8, 6
    exp = jobs["experience"].str.extract(r"(\d+)\s*-\s*(\d+)").astype(float)
    jobs["exp_min"], jobs["exp_max"] = exp[0], exp[1]
    jobs["exp_mid"] = (jobs["exp_min"] + jobs["exp_max"]) / 2

    # Package: '18-22.5 Lacs PA' -> 18, 22.5, 20.25 (in lakh rupees per year)
    pay = jobs["package"].str.extract(r"([\d.]+)\s*-\s*([\d.]+)\s*Lacs", flags=re.I).astype(float)
    jobs["salary_min_lpa"], jobs["salary_max_lpa"] = pay[0], pay[1]
    jobs["salary_mid_lpa"] = (jobs["salary_min_lpa"] + jobs["salary_max_lpa"]) / 2
    jobs["salary_disclosed"] = jobs["salary_mid_lpa"].notna()
    jobs["is_unpaid"] = jobs["package"].str.lower().eq("unpaid").fillna(False)

    jobs["city"] = jobs["location"].map(_city)
    jobs["n_locations"] = jobs["location"].fillna("").str.count(",") + jobs["location"].notna()
    jobs["role_category"] = jobs["job_title"].map(_role)
    jobs["posted_days_ago"] = jobs["post_time"].map(_post_days)

    jobs = jobs.reset_index(drop=True)
    jobs.insert(0, "job_id", jobs.index + 1)

    # One row per (job, skill) found in the skills text.
    low = jobs["skills"].fillna("").str.lower()
    rows = []
    for kw in SKILL_KEYWORDS:
        hit = low.str.contains(re.escape(kw), regex=True)
        for jid in jobs.loc[hit, "job_id"]:
            rows.append((jid, kw.strip().title() if kw.strip() not in ("sql", "aws", "gcp", "nlp", "sas", "etl")
                         else kw.strip().upper()))
    skills = pd.DataFrame(rows, columns=["job_id", "skill"])

    jobs = jobs.drop(columns=["post_time"])
    jobs["skills"] = jobs["skills"].astype(object)
    for c in ["job_title", "company", "experience", "package", "location"]:
        jobs[c] = jobs[c].astype(object)
    return jobs, skills


if __name__ == "__main__":
    j, s = clean()
    print(j.shape, s.shape)
    print(j.role_category.value_counts())
    print(j.city.value_counts().head(8))
    print(s.skill.value_counts().head(8))
