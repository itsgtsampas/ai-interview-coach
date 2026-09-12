"""The candidate's profile: the things that stay the same across applications.

A CV and a target role do not change per job posting, so asking for them on
every session is busywork. The profile holds them once; a session takes a copy.

Two fields need a word of explanation. `date_of_birth` and `gender` are here
because the Europass CV — the EU's own standard format — includes them, and
users filling in a European CV expect to record them. They are protected
characteristics, they say nothing about whether a CV meets a requirement, and
they are therefore **never placed in a prompt**: `profile_context()` is the only
path into the AI pipeline and it omits them by construction.
"""

from datetime import date, datetime
from enum import Enum

from sqlmodel import Field, SQLModel

from app.models.user import utcnow


class Seniority(str, Enum):
    intern = "intern"
    junior = "junior"
    mid = "mid"
    senior = "senior"
    lead = "lead"
    principal = "principal"


class UserProfile(SQLModel, table=True):
    __tablename__ = "user_profile"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True, unique=True)

    # --- professional identity (used by the AI pipeline) -------------------
    headline: str = Field(default="", max_length=160)
    seniority: Seniority | None = None
    years_experience: int | None = Field(default=None, ge=0, le=60)
    target_roles: str = Field(default="", max_length=300)
    location: str = Field(default="", max_length=120)
    languages: str = Field(default="", max_length=200)
    summary: str = Field(default="", max_length=1200)

    # --- links ------------------------------------------------------------
    linkedin_url: str = Field(default="", max_length=300)
    github_url: str = Field(default="", max_length=300)
    portfolio_url: str = Field(default="", max_length=300)
    phone: str = Field(default="", max_length=40)

    # --- Europass demographics (never sent to a model) --------------------
    date_of_birth: date | None = None
    gender: str = Field(default="", max_length=40)
    nationality: str = Field(default="", max_length=80)

    # --- the default CV ---------------------------------------------------
    cv_filename: str = Field(default="", max_length=255)
    cv_storage_path: str = Field(default="", max_length=500)
    cv_size_bytes: int = 0
    cv_page_count: int = 0
    cv_uploaded_at: datetime | None = None

    updated_at: datetime = Field(default_factory=utcnow)

    @property
    def has_cv(self) -> bool:
        return bool(self.cv_storage_path)

    @property
    def age(self) -> int | None:
        """Shown back to the user only; never reaches a prompt."""
        if self.date_of_birth is None:
            return None
        today = date.today()
        return today.year - self.date_of_birth.year - (
            (today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day)
        )

    def profile_context(self) -> str:
        """The only profile text the AI pipeline may see.

        Demographics are excluded deliberately: they cannot make a requirement
        met or unmet, and including them would let them colour the feedback.
        """
        parts: list[str] = []
        if self.headline:
            parts.append(f"Current title: {self.headline}")
        if self.seniority:
            parts.append(f"Seniority: {self.seniority.value}")
        if self.years_experience is not None:
            parts.append(f"Years of experience: {self.years_experience}")
        if self.target_roles:
            parts.append(f"Targeting: {self.target_roles}")
        if self.languages:
            parts.append(f"Languages: {self.languages}")
        return "\n".join(parts)
