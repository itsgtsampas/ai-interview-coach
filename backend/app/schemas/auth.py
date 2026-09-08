from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator


class RegisterRequest(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=120)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("password")
    @classmethod
    def not_trivial(cls, v: str) -> str:
        if v.isalpha() or v.isdigit():
            raise ValueError("Use a password with both letters and numbers.")
        return v


class UserOut(BaseModel):
    id: int
    email: EmailStr
    full_name: str
    created_at: datetime


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
