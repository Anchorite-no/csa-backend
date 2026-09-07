from datetime import datetime
from pathlib import Path

from fastapi import HTTPException
import pandas as pd

from misc.recruit_deadline import BEIJING

CATALOG_DIR = Path(__file__).resolve().parents[1] / "major"


def current_enrollment_year():
    return datetime.now(BEIJING).year


def validate_enrollment_grade(value):
    if not 21 <= value <= current_enrollment_year() % 100:
        raise ValueError("请选择有效的入学年级")
    return value


def recruitment_options():
    year = current_enrollment_year()
    grades = list(range(year % 100, 20, -1))
    catalogs = [
        grade for grade in grades
        if (CATALOG_DIR / f"specialties_data_20{grade}.csv").is_file()
    ]
    return {"year": year, "grades": grades, "catalog_grades": catalogs}


def undergraduate_major(data):
    catalog = CATALOG_DIR / f"specialties_data_20{data.grade}.csv"
    if not catalog.is_file():
        major = data.major_name.strip()
        college = (data.college_name or "").strip()
        if not 1 <= len(major) <= 24 or not 1 <= len(college) <= 24:
            raise HTTPException(400, "请填写专业和学院名称，各为 1–24 个字符")
        # No official catalog is available. Preserve the applicant's text and
        # keep identifiers empty so admins can distinguish unverified entries.
        return {
            "major_id": None, "major_name": major,
            "college_id": None, "college_name": college,
        }
    frame = pd.read_csv(catalog, dtype=str)
    matches = frame[frame["major_name"] == data.major_name]
    if matches.empty:
        raise HTTPException(400, "专业不存在")
    row = matches.iloc[0]
    if any(getattr(data, key) != row[key] for key in ["major_id", "college_id", "college_name"]):
        raise HTTPException(400, "专业或学院信息不匹配")
    return {key: row[key] for key in ["major_id", "major_name", "college_id", "college_name"]}
