"""The settings an admin edits on the web page. The SMTP password is stored separately, encrypted."""
import re
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, Field, field_validator

ADDRESS = re.compile(r"^[^@\s,;<>\"]{1,64}@[^@\s,;<>\"]{1,190}\.[^@\s,;<>\"]{2,24}$")


class Settings(BaseModel):
    day: int = Field(1, ge=1, le=28)
    hour: int = Field(3, ge=0, le=23)
    reminder_days: int = Field(3, ge=0, le=14)
    timezone: str = "Asia/Manila"
    threshold: int = Field(85, ge=50, le=99)
    prune_images: bool = True
    prune_cache: bool = True
    smtp_host: str = Field("", max_length=253)
    smtp_port: int = Field(587, ge=1, le=65535)
    smtp_security: Literal["starttls", "ssl"] = "starttls"
    smtp_user: str = Field("", max_length=254)
    mail_from: str = ""
    mail_to: str = ""

    @field_validator("smtp_host", "smtp_user", "mail_from", "mail_to", "timezone")
    @classmethod
    def _strip(cls, value: str) -> str:
        return value.strip()

    @field_validator("timezone")
    @classmethod
    def _zone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as error:
            raise ValueError("unknown time zone, for example Asia/Manila") from error
        return value

    @field_validator("mail_from", "mail_to")
    @classmethod
    def _address(cls, value: str) -> str:
        if value and not ADDRESS.match(value):
            raise ValueError("not a valid email address")
        return value
