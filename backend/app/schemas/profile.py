from datetime import date, datetime

from pydantic import BaseModel, Field

from app.models import Seniority


class ProfileUpdate(BaseModel):
    """Every field optional: the profile is filled in over time, not in one go."""

    headline: str = Field(default="", max_length=160)
    seniority: Seniority | None = None
    years_experience: int | None = Field(default=None, ge=0, le=60)
    target_roles: str = Field(default="", max_length=300)
    location: str = Field(default="", max_length=120)
    languages: str = Field(default="", max_length=200)
    summary: str = Field(default="", max_length=1200)
    linkedin_url: str = Field(default="", max_length=300)
    github_url: str = Field(default="", max_length=300)
    portfolio_url: str = Field(default="", max_length=300)
    phone: str = Field(default="", max_length=40)
    date_of_birth: date | None = None
    gender: str = Field(default="", max_length=40)
    nationality: str = Field(default="", max_length=80)


class ProfileOut(ProfileUpdate):
    id: int
    full_name: str
    email: str
    age: int | None = None
    has_cv: bool = False
    cv_filename: str = ""
    cv_page_count: int = 0
    cv_uploaded_at: datetime | None = None
    updated_at: datetime
